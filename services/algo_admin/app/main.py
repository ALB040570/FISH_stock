"""
Сервис 3. Администрирование алгоритмов расчёта (решение № 70).

Каталог алгоритмов a–k (версии кода, включение/отключение), параметры алгоритмов (наборы с версиями), расчёты —
алгоритм с входами, периодом и параметрами, один результат на расчёт (новый затирает прежний), основной /
альтернативный результат, устаревание, журнал расчёта, очередь с воркерами, результаты, выгрузка, отчёт водоёма.
"""
from __future__ import annotations

import io
import json
import zipfile

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, current_user, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import now_iso, read_json

from . import classifiers
from . import params as P
from .clients import Clients
from .engine import ACTIVE, CATALOG, CATALOG_BY_CODE, ORDER_ALL, STEP_ORDER, Engine, algo_info, default_values, letter
from .planning import algo_title, period_text, plan

app = create_app("algo_admin", "Администрирование алгоритмов расчёта",
                 "Каталог алгоритмов, параметры алгоритмов, расчёты, очередь, результаты, журнал.")
ST = app.state.settings
ROOT = ST.service_dir()
E = Engine(ROOT)
CLIENTS = Clients(ST)


def audit(user, action, otype, oid, details=None):
    app.state.audit.log(user, action, otype, oid, details)


E.seed_builtin()


# ================================================================ каталог
@app.get("/catalog", tags=["каталог"])
def catalog(user: User = Depends(require("catalog.view"))):
    """Алгоритмы каталога a–k по порядку; у планируемых (k) нет версий."""
    out = []
    for a in CATALOG:
        code = a["code"]
        base = {"code": code, "letter": a["letter"], "title_ru": a["title_ru"], "title_kk": a.get("title_kk", ""),
                "planned": bool(a.get("planned")), "inputs": a.get("inputs", []), "order": ORDER_ALL[code]}
        if a.get("planned") or not E.catalog.exists(code):
            out.append({**base, "description": a.get("description", ""), "versions": [], "latest": None, "manifest": None,
                        "classification": _classification({"code": code})})
            continue
        meta = E.catalog.get(code)
        vs = E.versions(code)
        latest = next((v for v in vs if v["enabled"]), None)
        out.append({**meta, **base, "description": (latest or (vs[0] if vs else {})).get("manifest", {}).get("description", meta.get("description")),
                    "versions": [{k: v.get(k) for k in ("version", "checksum", "enabled", "source", "created_at",
                                                        "created_by", "report")} for v in vs],
                    "latest": latest["version"] if latest else None,
                    "manifest": latest["manifest"] if latest else (vs[0]["manifest"] if vs else None),
                    "classification": _classification(meta)})
    # алгоритмы, опубликованные математиком в «Моделировании алгоритмов», — после a–k
    for meta in sorted((m for m in E.catalog.list() if m["code"] not in CATALOG_BY_CODE), key=lambda m: m["code"]):
        vs = E.versions(meta["code"])
        latest = next((v for v in vs if v["enabled"]), None)
        out.append({**meta, "letter": "", "planned": False, "order": 100,
                    "inputs": ((latest or {}).get("manifest") or {}).get("requires", {}).get("steps", []),
                    "versions": [{k: v.get(k) for k in ("version", "checksum", "enabled", "source", "created_at",
                                                        "created_by", "report")} for v in vs],
                    "latest": latest["version"] if latest else None,
                    "manifest": latest["manifest"] if latest else (vs[0]["manifest"] if vs else None),
                    "classification": _classification(meta)})
    return out


@app.get("/catalog/{code}", tags=["каталог"])
def catalog_item(code: str, user: User = Depends(require("catalog.view"))):
    a = E.catalog.get(code)
    if not a:
        raise not_found("Алгоритм")
    return {**a, "letter": letter(code), "classification": _classification(a), "versions": E.versions(code)}


def _classification(a: dict) -> dict:
    return a.get("classification") or classifiers.DEFAULT_CLASSIFICATION.get(a["code"]) or \
        {"model_type": None, "stock_methods": []}


@app.get("/classifiers", tags=["каталог"])
def get_classifiers(user: User = Depends(require("catalog.view"))):
    """Тип модели, методы расчёта запаса, значения параметров (классификатор ТОФИ)."""
    return classifiers.ALL


class ClassificationIn(BaseModel):
    model_type: str | None = None
    stock_methods: list[str] = []


@app.put("/catalog/{code}/classification", tags=["каталог"])
def set_classification(code: str, body: ClassificationIn, user: User = Depends(require("catalog.manage"))):
    a = E.catalog.get(code)
    if not a:
        raise not_found("Алгоритм")
    d = body.model_dump()
    errs = classifiers.check(d)
    if errs:
        raise AppError("catalog.classification", "Классификация задана неверно", 422, errs)
    E.catalog.update(code, {"classification": d}, actor=user.id)
    audit(user, "catalog.classification", "algorithm", code, d)
    return {**E.catalog.get(code), "classification": d}


@app.get("/catalog/{code}/versions/{version}/package.zip", tags=["каталог"])
def package(code: str, version: str, user: User = Depends(require("catalog.files"))):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    return Response(E.package_zip(code, version), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{code}-{version}.zip"'})


@app.get("/catalog/{code}/versions/{version}/files", tags=["каталог"])
def package_files(code: str, version: str, path: str | None = None, user: User = Depends(require("catalog.files"))):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    files = E.package_files(code, version)
    if path:
        if path not in files:
            raise not_found("Файл")
        return {"path": path, "text": files[path].decode("utf-8", errors="replace")}
    return [{"path": k, "size": len(v)} for k, v in sorted(files.items())]


def _toggle(code, version, enabled, user):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    E.set_enabled(code, version, enabled, user.id)
    audit(user, "catalog.enable" if enabled else "catalog.disable", "algorithm", code, {"version": version})
    return catalog_item(code, user)


@app.post("/catalog/{code}/versions/{version}/enable", tags=["каталог"])
def enable(code: str, version: str, user: User = Depends(require("catalog.manage"))):
    return _toggle(code, version, True, user)


@app.post("/catalog/{code}/versions/{version}/disable", tags=["каталог"])
def disable(code: str, version: str, user: User = Depends(require("catalog.manage"))):
    return _toggle(code, version, False, user)


@app.post("/internal/catalog/publish", tags=["каталог"], include_in_schema=False)
async def internal_publish(package: UploadFile = File(...), report: str = Form("{}"), author: str = Form(""),
                           user: User = Depends(current_user)):
    """Публикация проверенной версии из сервиса «Моделирование алгоритмов»."""
    if not user.is_service:
        raise AppError("auth.forbidden", "Только для сервисов", 403)
    data = await package.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    manifest = json.loads(files["manifest.json"])
    try:
        v = E.publish(manifest, files, actor=author or "algo_model", source="algo_model", report=json.loads(report))
    except ValueError as e:
        raise AppError("catalog.exists", str(e), 409)
    if not E.default_set(manifest["code"]):
        E._seed_default_set(manifest["code"], manifest, files)
    return {"ok": True, "version": v}


# ================================================================ параметры алгоритма
def _latest_manifest(code: str):
    v = E.latest_enabled(code) or (E.versions(code) or [None])[0]
    if not v:
        raise AppError("param_set.algorithm", "У алгоритма нет версий", 400)
    return v["manifest"], v["version"]


def _profile_schema(code: str):
    v = E.latest_enabled(code)
    if not v:
        return None
    files = E.package_files(code, v["version"])
    schema = json.loads(files["profile_schema.json"]) if "profile_schema.json" in files else None
    for row in schema or []:
        if row.get("type") == "float" and classifiers.value_kind(row.get("key")):
            row["value_kind"] = classifiers.value_kind(row["key"])
    return schema


def _set_usage(sid: str) -> list[dict]:
    return [{"id": c["id"], "title": c.get("title"), "water_body": c["water_body"]}
            for c in E.calc_list() if c.get("param_set") == sid]


def _set_pub(s: dict) -> dict:
    return {**s, "letter": letter(s["algorithm"]), "algorithm_title": algo_title(s["algorithm"]),
            "used_by": len(_set_usage(s["id"]))}


def _sets(algorithm=None):
    out = [s for s in E.param_sets.list() if not s.get("deleted") and (not algorithm or s["algorithm"] == algorithm)]
    return sorted(out, key=lambda s: (STEP_ORDER.get(s["algorithm"], 99), not s.get("is_default"), s.get("name", "")))


@app.get("/param-sets", tags=["параметры алгоритма"])
def list_sets(algorithm: str | None = None, user: User = Depends(require("run.view"))):
    """Наборы параметров (названия и версии видны всем, кто видит расчёты; значения — profile.view)."""
    return [_set_pub(s) for s in _sets(algorithm)]


@app.get("/param-sets/species-defaults/{species}", tags=["параметры алгоритма"])
def species_defaults(species: str, user: User = Depends(require("profile.view"))):
    """Значения для вида, добавляемого в набор параметров модели (алгоритм i): для видов эталона — значения эталона
    (оз. Жайсан), для остальных — общие значения модели. Научную пригодность подтверждает математик."""
    from dataclasses import asdict
    from fishcore.bayes import config as bc
    names = CLIENTS.species_names()
    if species not in names:
        raise not_found("Вид")
    ru = names[species]
    d = asdict(bc.base_config(ru))
    return {"species": species, "name": ru, "source": "reference" if ru in bc.DEFAULTS else "general",
            "values": {k: d[k] for k in sorted(bc.EDITABLE)}}


@app.get("/param-sets/{sid}", tags=["параметры алгоритма"])
def get_set(sid: str, version: int | None = None, user: User = Depends(require("profile.view"))):
    s = E.param_sets.get(sid)
    if not s or s.get("deleted"):
        raise not_found("Набор параметров")
    m, mv = _latest_manifest(s["algorithm"])
    n = version or s.get("current_version")
    return {**_set_pub(s), "version": n, "values": E.set_values(sid, n),
            "versions": list(reversed(E.param_sets.list_versions(sid))),
            "parameters": [p for p in m.get("parameters", []) if p.get("category") != "calc"],
            "algorithm_version": mv, "schema": _profile_schema(s["algorithm"]) if s["algorithm"] == "bayes_cohort" else None,
            "defaults": default_values(m), "usage": _set_usage(sid)}


class SetIn(BaseModel):
    algorithm: str | None = None
    name: str
    description: str = ""
    values: dict | None = None
    base: str | None = None             # «Создать на основе…» — значения текущей версии этого набора
    comment: str = ""


def _validate_set(code: str, values: dict) -> tuple[dict, list[str]]:
    m, _ = _latest_manifest(code)
    names = CLIENTS.species_names()
    out, errors = P.check_set(m, values, set(names))
    if code == "bayes_cohort":
        from fishcore.bayes import config as bc  # пакеты алгоритмов доступны сервису (algorithms/)
        for sp, vals in (out.get("species_profiles") or {}).items():
            errors += [f"{names.get(sp, sp)}: {e}" for e in bc.validate(names.get(sp, sp), vals)]
    return out, errors


@app.post("/param-sets", tags=["параметры алгоритма"], status_code=201)
def create_set(body: SetIn, user: User = Depends(require("profile.edit"))):
    base = E.param_sets.get(body.base) if body.base else None
    code = (base or {}).get("algorithm") or body.algorithm
    if not code or not E.catalog.exists(code):
        raise AppError("param_set.algorithm", "Укажите алгоритм каталога", 400)
    if not body.name.strip():
        raise AppError("param_set.name", "Укажите название набора", 400)
    if any(s["name"].strip().lower() == body.name.strip().lower() for s in _sets(code)):
        raise AppError("param_set.name", "Набор с таким названием у алгоритма уже есть", 409)
    values = body.values if body.values is not None else (E.set_values(base["id"]) if base else default_values(_latest_manifest(code)[0]))
    out, errors = _validate_set(code, values)
    if errors:
        raise AppError("param_set.invalid", "Параметры заданы с ошибками", 422, errors)
    s = E.param_sets.create({"algorithm": code, "name": body.name.strip(), "description": body.description,
                             "is_default": False, "system": False, "based_on": (base or {}).get("id")}, actor=user.id)
    E.param_sets.add_version(s["id"], {"values.json": json.dumps(out, ensure_ascii=False).encode()},
                             {"comment": body.comment or (f"на основе «{base['name']}»" if base else "создание")}, user.id)
    audit(user, "param_set.create", "param_set", s["id"], {"algorithm": code, "name": body.name})
    return get_set(s["id"], user=user)


@app.put("/param-sets/{sid}", tags=["параметры алгоритма"])
def update_set(sid: str, body: SetIn, user: User = Depends(require("profile.edit"))):
    s = E.param_sets.get(sid)
    if not s or s.get("deleted"):
        raise not_found("Набор параметров")
    if s.get("system"):
        raise AppError("param_set.system", "Набор «По умолчанию» не меняется — создайте набор на его основе", 400)
    changes = {}
    if body.name.strip() and body.name.strip() != s["name"]:
        if any(x["id"] != sid and x["name"].strip().lower() == body.name.strip().lower() for x in _sets(s["algorithm"])):
            raise AppError("param_set.name", "Набор с таким названием у алгоритма уже есть", 409)
        changes["name"] = body.name.strip()
    if body.description != s.get("description", ""):
        changes["description"] = body.description
    if changes:
        E.param_sets.update(sid, changes, actor=user.id)
    if body.values is not None:
        out, errors = _validate_set(s["algorithm"], body.values)
        if errors:
            raise AppError("param_set.invalid", "Параметры заданы с ошибками", 422, errors)
        if out != E.set_values(sid):
            v = E.param_sets.add_version(sid, {"values.json": json.dumps(out, ensure_ascii=False).encode()},
                                         {"comment": body.comment}, user.id)
            audit(user, "param_set.version", "param_set", sid, {"version": v["n"]})
    return get_set(sid, user=user)


@app.delete("/param-sets/{sid}", tags=["параметры алгоритма"])
def delete_set(sid: str, user: User = Depends(require("profile.edit"))):
    s = E.param_sets.get(sid)
    if not s or s.get("deleted"):
        raise not_found("Набор параметров")
    if s.get("system"):
        raise AppError("param_set.system", "Набор «По умолчанию» удалить нельзя", 400)
    used = _set_usage(sid)
    if used:
        raise AppError("param_set.used", "Набор используется в расчётах — сначала выберите в них другой набор", 409,
                       [u["title"] for u in used])
    E.param_sets.delete(sid)
    audit(user, "param_set.delete", "param_set", sid)
    return {"ok": True}


# ================================================================ расчёты
class CalcIn(BaseModel):
    algorithm: str
    water_body: str
    title: str = ""
    version: str | None = None          # None — последняя включённая версия на момент запуска
    period: dict | None = None          # {"from": год, "to": год}; пусто — все годы
    inputs: dict = {}                   # {алгоритм-вход: "main" | id расчёта}
    param_set: str | None = None        # пусто — набор «По умолчанию»
    param_version: int | None = None    # пусто — текущая версия набора (закрепляется при сохранении)
    calc_params: dict = {}              # параметры расчёта (виды модели и прогноза)
    comment: str = ""
    run: bool = False                   # сразу поставить в очередь


def _calc(cid):
    c = E.calc(cid)
    if not c:
        raise not_found("Расчёт")
    return c


def _wb_names() -> dict:
    try:
        return {k: v.get("name_ru", k) for k, v in CLIENTS.water_bodies().items()}
    except AppError:
        return {}


def _norm_period(p) -> dict | None:
    if not p:
        return None
    try:
        lo = int(p["from"]) if p.get("from") not in (None, "") else None
        hi = int(p["to"]) if p.get("to") not in (None, "") else None
    except (TypeError, ValueError):
        raise AppError("calc.period", "Период — годы числами", 422)
    if lo and hi and lo > hi:
        raise AppError("calc.period", "Начало периода позже конца", 422)
    return {"from": lo, "to": hi} if (lo or hi) else None


def _definition(body: CalcIn, cur: dict | None = None) -> dict:
    code = body.algorithm
    a = algo_info(E, code)
    if not a:
        raise AppError("calc.algorithm", "Алгоритм не найден в каталоге", 404)
    if a.get("planned"):
        raise AppError("calc.algorithm", f"Алгоритм «{algo_title(code)}» ещё не реализован (планируется)", 400)
    wbs = _wb_names()
    if wbs and body.water_body not in wbs:
        raise AppError("calc.water_body", "Водоём не найден в справочнике", 404)
    if body.version and not E.find_version(code, body.version):
        raise AppError("calc.version", f"Версии {body.version} нет в каталоге", 422)
    m, _ = _latest_manifest(code)
    deps = m.get("requires", {}).get("steps", [])
    inputs = {}
    for dep in deps:
        ref = (body.inputs or {}).get(dep) or "main"
        if ref != "main":
            ic = E.calc(ref)
            if not ic or ic["algorithm"] != dep or ic["water_body"] != body.water_body:
                raise AppError("calc.input", f"Вход «{algo_title(dep)}»: выберите расчёт этого алгоритма для того же водоёма", 422)
        inputs[dep] = ref
    sid = body.param_set or (E.default_set(code) or {}).get("id")
    s = E.param_sets.get(sid) if sid else None
    if not s or s.get("deleted") or s["algorithm"] != code:
        raise AppError("calc.param_set", "Выберите параметры алгоритма (набор этого алгоритма)", 422)
    pv = body.param_version or s.get("current_version")
    if not any(v["n"] == pv for v in E.param_sets.list_versions(sid)):
        raise AppError("calc.param_set", f"У набора нет версии {pv}", 422)
    period = _norm_period(body.period)
    title = body.title.strip() or (f"{algo_title(code)} — {wbs.get(body.water_body, body.water_body)}, {period_text(period)}"
                                   + ("" if s.get("is_default") else f" · {s['name']}"))
    return {"algorithm": code, "water_body": body.water_body, "title": title, "version": body.version or None,
            "period": period, "inputs": inputs, "param_set": sid, "param_version": pv,
            "calc_params": body.calc_params or {}, "comment": body.comment}


def _stale_map(water_bodies) -> dict:
    cur = {}
    for wb in set(water_bodies):
        try:
            cur[wb] = CLIENTS.current_datasets(wb)
        except AppError:
            cur[wb] = {}
    return E.staleness(cur) if cur else {}


def _pub(c: dict, stale: dict | None = None, wbs: dict | None = None) -> dict:
    s = E.param_sets.get(c.get("param_set")) if c.get("param_set") else None
    mains = E.mains().get(c["water_body"]) or {}
    inp = {}
    for dep, ref in (c.get("inputs") or {}).items():
        rid = E.resolve_input(c, dep)
        ic = E.calc(rid) if rid else None
        inp[dep] = {"ref": ref, "calc_id": rid, "title": (ic or {}).get("title"), "letter": letter(dep),
                    "has_result": bool((ic or {}).get("result")), "state": (ic or {}).get("state")}
    return {**{k: v for k, v in c.items() if k not in ("worker",)}, "letter": letter(c["algorithm"]),
            "algorithm_title": algo_title(c["algorithm"], E), "is_main": (mains.get(c["algorithm"]) or {}).get("calc_id") == c["id"],
            "param_set_name": (s or {}).get("name"), "param_set_current": (s or {}).get("current_version"),
            "param_set_default": bool((s or {}).get("is_default")), "inputs_resolved": inp,
            "stale": (stale or {}).get(c["id"], []), "has_result": bool(c.get("result")),
            "water_body_name": (wbs or {}).get(c["water_body"], c["water_body"]), "period_text": period_text(c.get("period")),
            "version_effective": E.calc_version(c)}


@app.get("/calcs", tags=["расчёты"])
def list_calcs(water_body: str | None = None, algorithm: str | None = None, user: User = Depends(require("run.view"))):
    cs = [c for c in E.calc_list() if (not water_body or c["water_body"] == water_body)
          and (not algorithm or c["algorithm"] == algorithm)]
    stale = _stale_map(c["water_body"] for c in cs)
    wbs = _wb_names()
    cs.sort(key=lambda c: (c["water_body"], STEP_ORDER.get(c["algorithm"], 99), c.get("created_at", "")))
    return [_pub(c, stale, wbs) for c in cs]


@app.post("/calcs", tags=["расчёты"], status_code=201)
def create_calc(body: CalcIn, user: User = Depends(require("run.execute"))):
    d = _definition(body)
    c = E.calcs.create({**d, "state": "new"}, actor=user.id)
    E.add_journal(c["id"], {"action": "create", "by": user.id, "by_name": user.name, "message": "расчёт создан"})
    audit(user, "calc.create", "calculation", c["id"], {"algorithm": d["algorithm"], "water_body": d["water_body"]})
    if body.run:
        return run_calc(c["id"], user)
    return get_calc(c["id"], user)


@app.get("/calcs/{cid}", tags=["расчёты"])
def get_calc(cid: str, user: User = Depends(require("run.view"))):
    c = _calc(cid)
    stale = _stale_map([c["water_body"]])
    q = E.queue()
    pos = next((i + 1 for i, x in enumerate(q) if x["id"] == cid), None)
    try:
        _, errors, warnings = plan(E, CLIENTS, c)
    except AppError as e:
        errors, warnings = [e.message], []
    dependents = [{"id": x["id"], "title": x.get("title"), "letter": letter(x["algorithm"])}
                  for x in E.calc_list() if x["water_body"] == c["water_body"]
                  and any(E.resolve_input(x, dep) == cid for dep in (x.get("inputs") or {}))]
    return {**_pub(c, stale, _wb_names()), "queue_position": pos, "check": {"errors": errors, "warnings": warnings},
            "dependents": dependents}


@app.put("/calcs/{cid}", tags=["расчёты"])
def update_calc(cid: str, body: CalcIn, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    if c.get("state") in ACTIVE:
        raise AppError("calc.active", "Расчёт выполняется или в очереди — изменить можно после него", 400)
    if body.algorithm != c["algorithm"] or body.water_body != c["water_body"]:
        raise AppError("calc.fixed", "Алгоритм и водоём расчёта не меняются — создайте новый расчёт", 400)
    d = _definition(body)
    if not body.title.strip():
        d["title"] = c.get("title") or d["title"]
    changed = {k: v for k, v in d.items() if c.get(k) != v}
    E.calcs.update(cid, d, actor=user.id)
    if changed:
        E.add_journal(cid, {"action": "edit", "by": user.id, "by_name": user.name, "message": "изменены: " + ", ".join(changed)})
    audit(user, "calc.update", "calculation", cid, {"changed": list(changed)})
    if body.run:
        return run_calc(cid, user)
    return get_calc(cid, user)


@app.delete("/calcs/{cid}", tags=["расчёты"])
def delete_calc(cid: str, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    if c.get("state") in ACTIVE:
        raise AppError("calc.active", "Расчёт выполняется или в очереди — сначала отмените его", 400)
    users = [x.get("title") for x in E.calc_list() if x["id"] != cid and cid in (x.get("inputs") or {}).values()]
    if users:
        raise AppError("calc.used", "Расчёт указан входом в других расчётах — сначала выберите в них другой вход", 409, users)
    E.calcs.delete(cid)
    if E.main_of(c["water_body"], c["algorithm"]) == cid:
        E.set_main(c["water_body"], c["algorithm"], None, user.id, user.name)
    audit(user, "calc.delete", "calculation", cid)
    return {"ok": True}


@app.post("/calcs/{cid}/check", tags=["расчёты"])
def check_calc(cid: str, user: User = Depends(require("run.view"))):
    p, errors, warnings = plan(E, CLIENTS, _calc(cid))
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "plan": {k: v for k, v in p.items() if k != "params"} if p else {}}


def _queue(c: dict, user: User) -> None:
    E.update_calc(c["id"], state="queued", queued_at=now_iso(), queued_by=user.id, queued_by_name=user.name,
                  message=None, cancel_requested=False, progress=None)


@app.post("/calcs/{cid}/run", tags=["расчёты"])
def run_calc(cid: str, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    if c.get("state") in ACTIVE:
        raise AppError("calc.active", "Расчёт уже в очереди или выполняется", 400)
    _, errors, _ = plan(E, CLIENTS, c)
    if errors:
        raise AppError("calc.invalid", "Расчёт нельзя запустить", 422, errors)
    _queue(c, user)
    audit(user, "calc.run", "calculation", cid, {"algorithm": c["algorithm"], "water_body": c["water_body"]})
    return get_calc(cid, user)


@app.post("/calcs/{cid}/cancel", tags=["расчёты"])
def cancel(cid: str, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    if c.get("state") not in ACTIVE:
        raise AppError("calc.finished", "Расчёт не выполняется", 400)
    if c["state"] == "queued":
        E.update_calc(cid, state="cancelled" if not c.get("result") else "done", message="Отменён до начала выполнения",
                      finished_at=c.get("finished_at"))
        E.add_journal(cid, {"action": "run", "status": "cancelled", "message": "отменён до начала выполнения",
                            "by": user.id, "by_name": user.name})
    else:
        E.update_calc(cid, cancel_requested=True)
    audit(user, "calc.cancel", "calculation", cid)
    return get_calc(cid, user)


@app.post("/calcs/{cid}/main", tags=["расчёты"])
def set_main(cid: str, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    if not c.get("result"):
        raise AppError("calc.no_result", "Основным можно сделать только расчёт с результатом", 400)
    prev = E.main_of(c["water_body"], c["algorithm"])
    E.set_main(c["water_body"], c["algorithm"], cid, user.id, user.name)
    E.add_journal(cid, {"action": "main", "by": user.id, "by_name": user.name, "message": "сделан основным"})
    if prev and prev != cid and E.calc(prev):
        E.add_journal(prev, {"action": "main", "by": user.id, "by_name": user.name,
                             "message": f"стал альтернативным (основной — «{c.get('title')}»)"})
    audit(user, "calc.set_main", "calculation", cid, {"water_body": c["water_body"], "algorithm": c["algorithm"]})
    return get_calc(cid, user)


class RecalcIn(BaseModel):
    water_body: str | None = None
    ids: list[str] = []


@app.post("/calcs/recalc-stale", tags=["расчёты"])
def recalc_stale(body: RecalcIn, user: User = Depends(require("run.execute"))):
    """Поставить в очередь устаревшие расчёты (водоёма или указанные) по порядку алгоритмов a → j; зависимые
    расчёты ждут свои входы."""
    cs = [c for c in E.calc_list() if not body.water_body or c["water_body"] == body.water_body]
    stale = _stale_map(c["water_body"] for c in cs)
    ids = [c["id"] for c in cs if c["id"] in stale and (not body.ids or c["id"] in body.ids)]
    picked = sorted((E.calc(i) for i in ids), key=lambda c: STEP_ORDER.get(c["algorithm"], 99))
    queued, skipped = [], []
    for c in picked:
        if c.get("state") in ACTIVE:
            continue
        _, errors, _ = plan(E, CLIENTS, c)
        if errors:
            skipped.append({"id": c["id"], "title": c.get("title"), "errors": errors})
            continue
        _queue(c, user)
        queued.append({"id": c["id"], "title": c.get("title")})
    audit(user, "calc.recalc_stale", "calculation", body.water_body or "*", {"queued": len(queued)})
    return {"queued": queued, "skipped": skipped}


def _result_dir(c):
    d = E.result_dir(c["id"])
    if not c.get("result") or not (d / "out" / "result.json").exists():
        raise AppError("calc.no_result", "У расчёта нет результата", 404)
    return d


@app.get("/calcs/{cid}/result", tags=["расчёты"])
def calc_result(cid: str, user: User = Depends(require("results.view"))):
    c = _calc(cid)
    d = _result_dir(c)
    return {"calc": _pub(c), **(read_json(d / "out" / "result.json") or {})}


@app.get("/calcs/{cid}/log", tags=["расчёты"])
def calc_log(cid: str, user: User = Depends(require("results.view"))):
    c = _calc(cid)
    base = E.calcs.obj_dir(cid)
    log = (base / "last_log.txt").read_text(encoding="utf-8") if (base / "last_log.txt").exists() else ""
    tb = None
    if user.role in ("admin", "mathematician") and c.get("state") == "failed" and (base / "last_traceback.txt").exists():
        tb = (base / "last_traceback.txt").read_text(encoding="utf-8")
    return {"log": log[-200_000:], "state": c.get("state"), "message": c.get("message"), "traceback": tb}


@app.get("/calcs/{cid}/journal", tags=["расчёты"])
def calc_journal(cid: str, user: User = Depends(require("run.view"))):
    _calc(cid)
    return list(reversed(E.journal(cid)))


@app.get("/calcs/{cid}/files/{name}", tags=["расчёты"])
def calc_file(cid: str, name: str, user: User = Depends(require("results.view"))):
    d = _result_dir(_calc(cid))
    f = d / "out" / name
    if "/" in name or "\\" in name or name.startswith(".") or not f.is_file() or name == "state.pkl":
        raise not_found("Файл")
    return FileResponse(f, filename=name)


@app.get("/calcs/{cid}/export.zip", tags=["расчёты"])
def export_zip(cid: str, user: User = Depends(require("results.view"))):
    c = _calc(cid)
    d = _result_dir(c)
    folder = f"{letter(c['algorithm'])}_{c['algorithm']}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("calc.json", json.dumps({k: v for k, v in c.items() if k != "worker"}, ensure_ascii=False, indent=1))
        z.writestr("journal.json", json.dumps(E.journal(cid), ensure_ascii=False, indent=1))
        for f in sorted((d / "out").rglob("*")):
            if f.is_file() and f.name != "state.pkl":
                z.write(f, f"{folder}/{f.relative_to(d / 'out')}")
        if (d / "log.txt").exists():
            z.write(d / "log.txt", f"{folder}/log.txt")
    audit(user, "calc.export", "calculation", cid)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="calc_{cid}.zip"'})


@app.get("/queue", tags=["расчёты"])
def queue(user: User = Depends(require("run.view"))):
    wbs = _wb_names()
    running = [_pub(c, None, wbs) for c in E.calc_list() if c.get("state") == "running"]
    return {"queued": [_pub(c, None, wbs) for c in E.queue()], "running": running}


# ================================================================ водоёмы: основные расчёты, сводка, отчёт
def _main_calcs(wb: str) -> dict:
    out = {}
    for code, m in (E.mains().get(wb) or {}).items():
        c = E.calc(m["calc_id"])
        if c:
            out[code] = c
    return out


def _payload(c):
    d = E.result_dir(c["id"])
    return read_json(d / "out" / "result.json") or {}


def _pdu_summary(mains):
    """ПДУ приложения (F = k·M) основного расчёта прогноза j."""
    c = mains.get("forecast_pdu")
    if not c or not c.get("result"):
        return None
    rows = (_payload(c).get("tables", {}).get("forecast_summary") or {}).get("rows", [])
    return {"source": "forecast", "calc_id": c["id"],
            "rows": [{"species": x["species"], "pdu_t": x["pdu_next_t"], "year": x.get("year_first_fc")} for x in rows]}


def _pdu_npc_summary(mains):
    """ПДУ НПЦ (официальный) последнего года из основного расчёта h — для ролей без права на результаты модели."""
    c = mains.get("pdu_by_age")
    if not c or not c.get("result"):
        return None
    pl = _payload(c).get("payload") or {}
    years = pl.get("years") or []
    if not years:
        return None
    rows = [{"species": k, "pdu_t": (v.get("pdu_t") or [None])[-1], "year": years[-1]}
            for k, v in (pl.get("species") or {}).items()]
    return {"source": "npc", "calc_id": c["id"], "rows": sorted(rows, key=lambda x: -(x["pdu_t"] or 0))}


def _brief(c, stale=None):
    return {"id": c["id"], "title": c.get("title"), "algorithm": c["algorithm"], "letter": letter(c["algorithm"]),
            "state": c.get("state"), "finished_at": (c.get("result") or {}).get("finished_at") or c.get("finished_at"),
            "stale": (stale or {}).get(c["id"], [])}


@app.get("/water-bodies/status", tags=["сводка"])
def wb_status(user: User = Depends(require("run.view"))):
    """По водоёмам: расчёты, основные расчёты алгоритмов, устаревшие, активные, ПДУ (для карты и «Потока»)."""
    calcs = E.calc_list()
    wbs = sorted({c["water_body"] for c in calcs} | set(E.mains()))
    stale = _stale_map(wbs)
    out = {}
    for wb in wbs:
        cs = [c for c in calcs if c["water_body"] == wb]
        mains = _main_calcs(wb)
        done = sorted((c for c in cs if c.get("result")), key=lambda c: c["result"]["finished_at"], reverse=True)
        failed = sorted((c for c in cs if c.get("state") == "failed"), key=lambda c: c.get("finished_at") or "", reverse=True)
        s = {"calcs": len(cs), "with_result": len(done),
             "active": [_brief(c) for c in cs if c.get("state") in ACTIVE],
             "main": {code: _brief(c, stale) for code, c in mains.items()},
             "stale": sorted({c["id"] for c in mains.values() if c["id"] in stale}),
             "last_done": _brief(done[0]) if done else None,
             "last_failed": _brief(failed[0]) if failed and (not done or (failed[0].get("finished_at") or "") >
                                                              done[0]["result"]["finished_at"]) else None}
        s["pdu_npc"] = _pdu_npc_summary(mains)
        # ПДУ приложения (F = k·M) — результат модели; без права — ПДУ НПЦ (№ 62)
        s["pdu"] = _pdu_summary(mains) if user.can("results.summary") else s["pdu_npc"]
        out[wb] = s
    return out


@app.get("/water-bodies/{water_body}/mains", tags=["сводка"])
def wb_mains(water_body: str, user: User = Depends(require("run.view"))):
    """Основные расчёты водоёма по алгоритмам a–j (для шапки мониторинга)."""
    mains = _main_calcs(water_body)
    stale = _stale_map([water_body]) if mains else {}
    return {code: {**_brief(c, stale), "period_text": period_text(c.get("period")),
                   "param_set_name": (E.param_sets.get(c.get("param_set")) or {}).get("name")}
            for code, c in mains.items()}


@app.get("/water-bodies/{water_body}/main-result", tags=["сводка"])
def main_result(water_body: str, algorithm: str, user: User = Depends(require("run.view"))):
    """Результат основного расчёта алгоритма для мониторинга (результат — с правом results.view)."""
    cid = E.main_of(water_body, algorithm)
    c = E.calc(cid) if cid else None
    if not c:
        return {"calc": None, "result": None}
    stale = _stale_map([water_body])
    out = {"calc": {**_brief(c, stale), "period_text": period_text(c.get("period")), "inputs": (c.get("result") or {}).get("inputs"),
                    "param_set_name": (E.param_sets.get(c.get("param_set")) or {}).get("name"),
                    "result_id": (c.get("result") or {}).get("result_id")}, "result": None}
    if c.get("result") and user.can("results.view"):
        out["result"] = _payload(c)
    return out


@app.get("/water-bodies/{water_body}/report.{fmt}", tags=["сводка"])
def report(water_body: str, fmt: str, lang: str = "ru", user: User = Depends(require("results.view"))):
    """Отчёт водоёма (Word/PDF) по основным расчётам алгоритмов."""
    from . import report as rep
    mains = {code: c for code, c in _main_calcs(water_body).items() if c.get("result")}
    if not mains:
        raise AppError("report.no_calcs", "У водоёма нет основных расчётов с результатом", 400)
    stale = _stale_map([water_body])
    results = {code: _payload(c) for code, c in mains.items()}
    info = [{**_brief(c, stale), "version": c["result"].get("version"), "period_text": period_text(c.get("period")),
             "param_set_name": c["result"].get("param_set_name"), "param_version": c["result"].get("param_version"),
             "datasets": c["result"].get("datasets") or {}, "by_name": c["result"].get("by_name"),
             "warnings": c["result"].get("warnings") or []}
            for code, c in sorted(mains.items(), key=lambda kv: STEP_ORDER.get(kv[0], 99))]
    wb = CLIENTS.water_bodies().get(water_body, {"name_ru": water_body})
    if fmt == "docx":
        data, mt = rep.docx_report(water_body, info, results, wb), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "pdf":
        data, mt = rep.pdf_report(water_body, info, results, wb), "application/pdf"
    else:
        raise AppError("report.format", "Формат отчёта: docx или pdf", 400)
    audit(user, "wb.report", "water_body", water_body, {"format": fmt})
    return Response(data, media_type=mt, headers={"Content-Disposition": f'attachment; filename="pdu_report_{water_body}.{fmt}"'})
