"""Проверки байесовской модели (перенос fish_stock_forecast 22.10.2026: core/bayes/analyses.py, core/net_sensitivity.py).

Как в статье: ретроспективный прогноз, чувствительность к априорным распределениям, к учёту пустых ловов,
восстановление параметров на синтетических данных и чувствительность балансового метода к его параметрам.
Кроме последней, каждая проверка — полный расчёт NUTS с теми же профилем вида и настройками выборки, что у шага
«Байесовская когортная модель» этой цепочки; его результат — основа для сравнения. Формулы и настройки — эталона.
"""
import shutil

from fishcore import stepkit
from fishcore.bayes import analyses as A
from fishcore.bayes import config as bc
from fishcore.bayes import parallel as P
from fishcore.bayes import run as R
from fishcore.net_sensitivity import species_table

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights", "npc_pdu")
RUN_KEYS = ("draws", "tune", "chains", "target_accept", "max_treedepth", "seed")
CHECKS = ("check_net", "check_retro", "check_prior", "check_pad", "check_recovery")


def _n(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def run(ctx):
    from fishrunner import UserError
    stepkit.bundle(ctx, *DATASETS)
    bdir = ctx.input_dir("bayes_cohort")
    prev = ctx.load_state("bayes_cohort") if bdir is not None else None
    if prev is None:
        raise UserError("Проверки строятся по результатам байесовской модели: добавьте шаг «Байесовская когортная модель» "
                        "в цепочку расчёта перед проверками")
    res, props, pdu = prev["res"], prev["props"], prev["pdu"]
    stage23 = (res, pdu, props)
    bc.register_tokens({ru: code for code, ru in ctx.species_names.items()})
    done = [ru for ru in prev.get("species", []) if R.result_path(ru, "new", "npz", bdir).exists()]
    run_over = {k: ctx.params[k] for k in RUN_KEYS if ctx.params.get(k) is not None}
    runtime = {ru: {**(prev.get("runtime") or {}).get(ru, {}), **run_over} for ru in prev.get("species", [])}
    bc.set_runtime(runtime)
    for ru in done:                                        # основа сравнения — расчёт модели этой цепочки
        for ext in ("npz", "nc"):
            src = R.result_path(ru, "new", ext, bdir)
            if src.exists():
                shutil.copy(src, R.result_path(ru, "new", ext, ctx.out_dir))
    code_by_ru = {ru: code for code, ru in ctx.species_names.items()}

    def pick(key, default):
        codes = ctx.params.get(key)
        names = default if not codes else [ctx.species_names.get(c, c) for c in codes]
        return [ru for ru in names if ru in done]

    on = {k: ctx.params.get(k, True) is not False for k in CHECKS}
    if not any(on.values()):
        raise UserError("Не выбрана ни одна проверка")
    if not done and any(on[k] for k in CHECKS if k != "check_net"):
        raise UserError("В результатах байесовской модели нет расчёта в режиме «расчёт» — проверять нечего")
    plan = []
    if on["check_retro"]:
        plan += [("retro", ru) for ru in pick("retro_species", done)]
    if on["check_prior"]:
        plan += [("prior", ru) for ru in pick("prior_species", done)]
    if on["check_pad"]:
        pads = [float(x) for x in (ctx.params.get("pads") or (0.1, 1.0, 10.0))]
        plan += [("pad", ru) for ru in pick("pad_species", ["лещ", "судак", "плотва", "сазан"])]
    if on["check_recovery"]:
        plan += [("recovery", ru) for ru in pick("recovery_species", ["лещ", "судак"])]
    total = len(plan) + (1 if on["check_net"] else 0)
    year_max = int(ctx.params.get("year_max") or 2021)
    factor = float(ctx.params.get("prior_factor") or 2.0)
    payload = {"species": done, "net": None, "retro": {}, "prior": {}, "pad": {}, "recovery": {},
               "year_max": year_max, "prior_factor": factor, "runs": {}}
    step = 0

    # ---- чувствительность балансового метода (без MCMC, по всем видам водоёма)
    if on["check_net"]:
        y = sorted(props.net_hours)[-1]
        hours = float(props.net_hours[y])
        width = float(props.net_length.get(y, list(props.net_length.values())[-1]))
        rows = []
        for ru in res.species:
            if ru in props.cruise_speed and ru in props.k_net:
                rows += species_table(ru, float(props.cruise_speed[ru]) * 3600.0, float(props.k_net[ru]), hours, width)
        for r in rows:
            r["stock_factor"] = _n(r["stock_factor"])
        payload["net"] = {"year": y, "rows": rows}
        ctx.add_table("net_sensitivity", "Чувствительность балансового метода к его параметрам", [
            {"code": "species", "title": "Вид"}, {"code": "parameter", "title": "Параметр"},
            {"code": "value", "title": "Значение", "type": "number"},
            {"code": "rel_change", "title": "Изменение", "type": "number"},
            {"code": "stock_factor", "title": "Множитель запаса", "type": "number"}], rows)
        step += 1

    retro_rows, prior_rows, pad_rows, rec_rows = [], [], [], []
    # каждая проверка вида (и каждый вариант пустых ловов) — независимый расчёт модели: они идут одновременно в
    # пределах лимита ядер (FISH_CALC_CORES), иначе по очереди; seed и настройки те же (решение № 63)
    kw = dict(stage23=stage23, results_dir=str(ctx.out_dir), plots=False)
    tasks = []
    for name, ru in plan:
        if name == "retro":
            tasks.append((f"retro-{ru}", {"name": name, "species": ru, "kw": {**kw, "year_max": year_max}}))
        elif name == "prior":
            tasks.append((f"prior-{ru}", {"name": name, "species": ru, "kw": {**kw, "factor": factor}}))
        elif name == "pad":
            tasks += [(f"pad{p:g}-{ru}", {"name": name, "species": ru, "kw": {**kw, "pads": (p,)}}) for p in pads]
        else:
            tasks.append((f"recovery-{ru}", {"name": name, "species": ru, "kw": kw}))
    done0 = step
    chains = max([int((runtime.get(ru) or {}).get("chains") or 4) for _, ru in plan] or [4])

    def on_progress(frac, info):
        now = [k for k in frac if 0 < frac[k] < 1 or k in info]
        ctx.progress((done0 + sum(frac.values()) / max(1, len(tasks)) * len(plan)) / max(1, total),
                     check=", ".join(now) or None, phase="выборка" if now else None)

    outs = P.run_tasks(tasks, "fishcore.bayes.parallel:check_species", on_progress, ctx.log, ctx.check_cancel, chains=chains)
    for name, ru in plan:
        if name == "retro":
            out = outs[f"retro-{ru}"]
            payload["retro"][ru] = {"metrics": out["metrics"], "forecast_years": out["forecast_years"]}
            retro_rows += [{"species": ru, **m} for m in out["metrics"]]
            meta = out["run"]
        elif name == "prior":
            out = outs[f"prior-{ru}"]
            payload["prior"][ru] = out["compare"]
            prior_rows += [{"species": ru, **m} for m in out["compare"]]
            meta = out["run"]
        elif name == "pad":
            parts = [outs[f"pad{p:g}-{ru}"] for p in pads]          # как один расчёт по вариантам подряд
            out = {"runs": {k: v for o in parts for k, v in o["runs"].items()}, "compare": [r for o in parts for r in o["compare"]]}
            A._write_csv(A.analysis_dir(ru, "sens_pad", ctx.out_dir) / "compare_pad.csv", out["compare"])
            payload["pad"][ru] = out["compare"]
            pad_rows += [{"species": ru, **m} for m in out["compare"]]
            meta = next(iter(out["runs"].values()), {})
        else:
            out = outs[f"recovery-{ru}"]
            payload["recovery"][ru] = {"coverage": out["coverage"], "truth_source": out["truth_source"]}
            rec_rows += [{"species": ru, **m} for m in out["coverage"]]
            meta = out["run"]
        dg = (meta or {}).get("diagnostics") or {}
        payload["runs"].setdefault(name, {})[ru] = {"rhat": dg.get("rhat_max_params"), "ess_bulk": dg.get("ess_bulk_min_params"),
                                                    "ess_tail": dg.get("ess_tail_min_params"), "divergences": (meta or {}).get("divergences"),
                                                    "ebfmi": dg.get("ebfmi_min")}
        step += 1

    num = lambda c, t: {"code": c, "title": t, "type": "number"}  # noqa: E731
    sp = {"code": "species", "title": "Вид"}
    if retro_rows:
        ctx.add_table("retro", f"Ретроспективный прогноз: подгонка по {year_max} г., прогноз следующих лет", [
            sp, {"code": "subset", "title": "Ловы"}, {"code": "n", "title": "n", "type": "integer"},
            num("rmse_log", "RMSE (лог)"), num("bias_log", "Смещение (лог)"), num("coverage95", "Покрытие 95 %"),
            num("zero_share_obs", "Пустых, факт"), num("zero_share_pred", "Пустых, прогноз")], retro_rows)
    if prior_rows:
        ctx.add_table("prior_sensitivity", f"Чувствительность к априорным: σ смертности и β × {factor:g}", [
            sp, {"code": "year", "title": "Год", "type": "integer"}, num("median_base", "Медиана, основной расчёт"),
            num("median", "Медиана"), num("median_ratio", "Отношение медиан"), num("width_ratio", "Отношение ширины 95 %")], prior_rows)
    if pad_rows:
        ctx.add_table("pad_sensitivity", "Учёт пустых ловов: логнормальное правдоподобие с константой", [
            sp, {"code": "variant", "title": "Вариант"}, {"code": "year", "title": "Год", "type": "integer"},
            num("median_base", "Медиана, основной расчёт"), num("median", "Медиана"), num("median_ratio", "Отношение медиан")], pad_rows)
    if rec_rows:
        ctx.add_table("recovery", "Восстановление на синтетических данных: доля истинных значений в 95 % интервале", [
            sp, {"code": "quantity", "title": "Величина"}, {"code": "n", "title": "n", "type": "integer"},
            num("coverage95", "Покрытие 95 %")], rec_rows)
    for f in sorted(ctx.out_dir.rglob("*.csv")):
        ctx.result["files"].append({"name": str(f.relative_to(ctx.out_dir)), "title": f.stem, "format": "csv"})
    ctx.set_payload(payload)
    return {"checks": [k for k, v in on.items() if v], "runs": len(plan)}
