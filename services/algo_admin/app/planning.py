"""План выполнения расчёта (решение № 70): версия кода, параметры (набор и версия + параметры расчёта), расчёты-входы
(основной расчёт водоёма или указанный), наборы данных (последние версии), период. Общий для сервиса и воркера."""
from __future__ import annotations

from . import params as P
from .engine import ACTIVE, CATALOG_BY_CODE, algo_info, letter

OPTIONAL_DATASETS = {"npc_stock"}      # без оценки НПЦ запас считается, сравнение с НПЦ не показывается


def algo_title(code: str, E=None) -> str:
    a = CATALOG_BY_CODE.get(code) or (algo_info(E, code) if E is not None else None) or {}
    if not a:
        return code
    return f"{a['letter']}. {a.get('title_ru', code)}" if a.get("letter") else a.get("title_ru", code)


def period_text(period) -> str:
    p = period or {}
    lo, hi = p.get("from"), p.get("to")
    if lo and hi:
        return f"{lo}–{hi}" if lo != hi else str(lo)
    if lo:
        return f"с {lo}"
    if hi:
        return f"по {hi}"
    return "все годы"


def unknown_profile_fields(E, code: str, version: str, profiles: dict) -> list[str]:
    """Поля профилей видов, которых нет в схеме профиля этой версии кода: старая версия их молча пропустит
    (например, «Оценки запаса в правдоподобии» — с версии 3.0.2, решение № 73)."""
    try:
        files = E.package_files(code, version)
    except Exception:  # noqa: BLE001 — нет пакета: проверять нечем
        return []
    if "profile_schema.json" not in files:
        return []
    import json as _json
    schema = _json.loads(files["profile_schema.json"])
    known = {row["key"] for row in schema}
    labels = {}
    try:
        from_latest = E.latest_enabled(code)
        if from_latest:
            lf = E.package_files(code, from_latest["version"])
            labels = {row["key"]: row.get("label") or row["key"]
                      for row in _json.loads(lf.get("profile_schema.json", b"[]"))}
    except Exception:  # noqa: BLE001
        pass
    keys = sorted({k for vals in (profiles or {}).values() if isinstance(vals, dict) for k in vals} - known)
    return [f"«{labels.get(k, k)}» ({k})" for k in keys]


def plan(E, clients, c: dict, names: dict | None = None, current: dict | None = None):
    """(план, ошибки, предупреждения)."""
    errors, warnings = [], []
    code = c["algorithm"]
    a = algo_info(E, code)
    if not a:
        return {}, [f"Алгоритм «{code}» не найден в каталоге"], warnings
    if a.get("planned"):
        return {}, [f"Алгоритм «{algo_title(code)}» ещё не реализован (планируется)"], warnings
    v = c.get("version")
    if v and not E.find_version(code, v):
        warnings.append(f"Версия {v} удалена из каталога — используется последняя включённая")
        v = None
    if v:
        vv = next((x for x in E.versions(code) if x["version"] == v), None)
        if vv and not vv["enabled"]:
            errors.append(f"Версия {v} алгоритма отключена в каталоге")
    else:
        lv = E.latest_enabled(code)
        if not lv:
            return {}, [f"У алгоритма «{algo_title(code)}» нет включённых версий"], warnings
        v = lv["version"]
    m = E.manifest(code, v)
    names = names if names is not None else clients.species_names()
    # параметры
    sid = c.get("param_set")
    s = E.param_sets.get(sid) if sid else None
    pv = None
    if not s or s.get("deleted"):
        errors.append("Не выбраны параметры алгоритма (набор удалён или не указан)")
        set_vals = {}
    elif s.get("algorithm") != code:
        errors.append("Набор параметров относится к другому алгоритму")
        set_vals = {}
    else:
        pv = c.get("param_version") or s.get("current_version")
        set_vals = E.set_values(sid, pv)
        if c.get("param_version") and s.get("current_version") and c["param_version"] < s["current_version"]:
            warnings.append(f"У набора параметров «{s['name']}» есть новая версия {s['current_version']} "
                            f"(расчёт использует версию {c['param_version']})")
    prm, errs = P.merge_calc(m, set_vals, c.get("calc_params"), set(names))
    errors += errs
    current = current if current is not None else clients.current_datasets(c["water_body"])
    if code == "bayes_cohort" and not errors:
        prof = prm.get("species_profiles") or {}
        if not prm.get("species"):
            data_sp = (((current.get("catches") or {}).get("summary") or {}).get("species")) or []
            miss = [names.get(x, x) for x in data_sp if x not in prof]
            if miss:
                warnings.append("Видов нет в параметрах алгоритма, они не будут рассчитаны: " + ", ".join(miss)
                                + " (Параметры алгоритмов → набор → «Добавить вид»)")
        else:
            miss = [names.get(x, x) for x in prm["species"] if x not in prof]
            if miss:
                errors.append("В параметрах алгоритма нет значений для видов: " + ", ".join(miss))
        unknown = unknown_profile_fields(E, code, v, prof)
        if unknown:
            warnings.append(f"Версия кода {v} не знает полей профиля: {', '.join(unknown)} — они не будут учтены "
                            "(выберите последнюю версию алгоритма в расчёте)")
    # расчёты-входы
    inputs = {}
    for dep in m.get("requires", {}).get("steps", []):
        ref = (c.get("inputs") or {}).get(dep) or "main"
        rid = E.resolve_input(c, dep)
        if not rid:
            pend = E.pending_input(c, dep)
            if pend:
                warnings.append(f"Расчёт-вход {letter(dep)} выполняется — расчёт начнётся после него")
                inputs[dep] = {"calc_id": pend["id"], "result_id": None, "title": pend.get("title"), "main": True,
                               "years": None, "pending": True}
                continue
            errors.append(f"Нет основного расчёта «{algo_title(dep)}» для водоёма — выполните его или выберите расчёт")
            continue
        ic = E.calc(rid)
        if not ic:
            errors.append(f"Расчёт-вход «{algo_title(dep)}» удалён — выберите другой")
            continue
        if ic["algorithm"] != dep or ic["water_body"] != c["water_body"]:
            errors.append(f"Вход «{algo_title(dep)}»: расчёт другого алгоритма или водоёма")
            continue
        if ic.get("state") in ACTIVE:
            warnings.append(f"Расчёт-вход {letter(dep)} выполняется — расчёт начнётся после него")
        elif not ic.get("result"):
            errors.append(f"У расчёта-входа «{ic.get('title') or algo_title(dep)}» нет результата — выполните его")
            continue
        r = ic.get("result") or {}
        inputs[dep] = {"calc_id": rid, "result_id": r.get("result_id"), "title": ic.get("title"), "main": ref == "main",
                       "years": r.get("years")}
        yrs = r.get("years") or []
        p = c.get("period") or {}
        if yrs and ((p.get("from") and int(p["from"]) < min(yrs)) or (p.get("to") and int(p["to"]) > max(yrs))):
            warnings.append(f"Расчёт-вход {letter(dep)} рассчитан за {min(yrs)}–{max(yrs)} — расчёт будет выполнен за общие годы")
    # наборы данных — последние версии
    datasets = {}
    for t in m.get("requires", {}).get("datasets", []):
        if t in current:
            datasets[t] = {"dataset_id": current[t]["dataset_id"], "version": current[t]["version"]}
        elif t not in OPTIONAL_DATASETS:
            errors.append(f"Для водоёма не загружен набор данных «{t}»")
    return {"version": v, "checksum": E.find_version(code, v)["checksum"], "params": prm, "param_set": sid,
            "param_set_name": (s or {}).get("name"), "param_version": pv, "period": c.get("period") or None,
            "datasets": datasets, "inputs": inputs}, errors, warnings
