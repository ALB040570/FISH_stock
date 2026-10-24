"""i. Запас по математической модели — байесовская когортная модель (перенос fish_stock_forecast, уравнения без
изменений; решение № 70)."""
import copy
import json
from pathlib import Path

from fishcore import config, stepkit, views
from fishcore.bayes import config as bc
from fishcore.bayes import parallel as P
from fishcore.bayes import run as R
from fishcore.data_source import load_fish_props
from fishcore.years import select_gear_state, select_pdu, select_stock

DATASETS = ("species_props", "yearly_conditions", "mean_weights", "npc_pdu")
RUN_KEYS = ("draws", "tune", "chains", "target_accept", "max_treedepth", "seed")


def _profiles(ctx) -> dict:
    """Профиль водоёма {код вида: {параметр: значение}}: из параметров запуска или файл профиля пакета."""
    prof = ctx.params.get("species_profiles")
    if prof:
        return prof
    f = Path(__file__).parent / "profiles" / f"{ctx.water_body}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {}


def run(ctx):
    from fishrunner import UserError
    b = stepkit.bundle(ctx, *DATASETS)
    # входы (решение № 70): оценки по ловам — c и d, окончательный запас — g, ПДУ в штуках — h
    c = stepkit.need_input(ctx, "seine_likelihood")
    d = stepkit.need_input(ctx, "net_likelihood")
    g = stepkit.need_input(ctx, "combined_stock")
    h = stepkit.need_input(ctx, "pdu_by_age")
    years = stepkit.years_for(ctx, stepkit.in_period(ctx, g["res"].years), seine_likelihood=c["years"],
                              net_likelihood=d["years"], combined_stock=g["res"].years, pdu_by_age=h["pdu"].years)
    res = copy.copy(select_stock(g["res"], years))
    c, d = select_gear_state(c, years), select_gear_state(d, years)
    stepkit.check_species(c["species"], res.species, "оценок по ловам неводом")
    stepkit.check_species(d["species"], res.species, "оценок по ловам сетью")
    res.catches = {**res.catches, config.GEAR_SEINE: c["catch"], config.GEAR_NET: d["catch"]}
    res.per_haul = {**res.per_haul, (config.GEAR_SEINE, "with_ages"): c["per_haul"],
                    (config.GEAR_NET, "with_ages"): d["per_haul"]}
    pdu = select_pdu(h["pdu"], years)
    props = load_fish_props(ctx.water_body, stepkit.keep_years(b, years))

    profiles = _profiles(ctx)
    code_by_ru = {ru: code for code, ru in ctx.species_names.items()}
    bc.register_tokens(code_by_ru)
    wanted = ctx.params.get("species") or [code_by_ru.get(s, s) for s in res.species if code_by_ru.get(s, s) in profiles]
    if not wanted:
        raise UserError("В параметрах алгоритма нет значений ни для одного вида данных водоёма. "
                        "Добавьте виды в набор параметров: Расчёты запасов рыб → Параметры алгоритмов.")
    missing = [s for s in wanted if s not in profiles]
    if missing:
        raise UserError("В параметрах алгоритма нет значений для видов: " + ", ".join(ctx.species_names.get(s, s) for s in missing)
                        + " (Расчёты запасов рыб → Параметры алгоритмов → Добавить вид)")
    run_over = {k: ctx.params[k] for k in RUN_KEYS if ctx.params.get(k) is not None}
    runtime = {}
    for code in wanted:
        ru = ctx.species_names.get(code, code)
        if ru not in res.species:
            raise UserError(f"Вид «{ru}» отсутствует в окончательном запасе (расчёт g)")
        values = {**profiles[code], **run_over}
        errs = bc.validate(ru, values)
        if errs:
            raise UserError(f"Профиль вида «{ru}»: " + "; ".join(errs))
        runtime[ru] = values
    bc.set_runtime(runtime)
    mode = ctx.params.get("mode") or "new"
    payload, rows, per_species = {}, [], {}
    n = len(runtime)
    species = list(runtime)
    # виды независимы: считаются одновременно, если позволяет лимит ядер (FISH_CALC_CORES), иначе по очереди;
    # у каждого вида свои seed и цепи — результаты те же, что при расчёте по очереди (решение № 64)
    chains = max([int(v.get("chains") or 4) for v in runtime.values()] or [4])

    def on_progress(frac, info):
        now = [ru for ru in species if 0 < frac.get(ru, 0) < 1 or ru in info]
        cur = info.get(now[0], {}) if len(now) == 1 else {}
        ctx.progress(sum(frac.values()) / max(1, n), species=", ".join(now) or None,
                     **({k: v for k, v in cur.items() if k != "species"} if cur else {"phase": "выборка" if now else None}))

    ctx.log(f"видов: {n}, режим {mode}")
    metas = P.run_tasks([(ru, {"species": ru, "mode": mode, "results_dir": str(ctx.out_dir), "stage23": (res, pdu, props)})
                         for ru in species], "fishcore.bayes.parallel:fit_species", on_progress, ctx.log, ctx.check_cancel,
                        chains=chains)
    for ru in species:
        meta = metas[ru]
        loaded = R.load_npz(R.result_path(ru, mode, "npz", ctx.out_dir))
        a, m = loaded
        payload[ru] = views.bayes_payload(ru, a, m, mode)
        rows += views.bayes_rows(ru, a)
        per_species[ru] = (a, m)
        ctx.metric(f"divergences_{code_by_ru.get(ru, ru)}", meta.get("divergences"), f"Расходимости: {ru}")
        ctx.metric(f"rhat_{code_by_ru.get(ru, ru)}", meta.get("rhat_X_max"), f"R̂ max: {ru}")
        dg = meta.get("diagnostics") or {}
        for k, t in (("ess_bulk_min_params", "ESS bulk min"), ("ess_tail_min_params", "ESS tail min"), ("ebfmi_min", "E-BFMI min")):
            if dg.get(k) is not None:
                ctx.metric(f"{k}_{code_by_ru.get(ru, ru)}", dg[k], f"{t}: {ru}")
        # критерии сходимости методики: R̂ ≤ 1,01; ESS bulk и tail ≥ 400; нет расходимостей; E-BFMI > 0,3
        bad = []
        rh = max([v for v in (dg.get("rhat_max_params"), dg.get("rhat_max_X"), meta.get("rhat_X_max")) if v is not None], default=None)
        if rh is not None and rh > 1.01:
            bad.append(f"R̂ {rh:.3f} > 1,01")
        ess = min([v for v in (dg.get("ess_bulk_min_params"), dg.get("ess_tail_min_params")) if v is not None], default=None)
        if ess is not None and ess < 400:
            bad.append(f"ESS {ess:.0f} < 400")
        if meta.get("divergences"):
            bad.append(f"расходимостей {meta['divergences']}")
        if dg.get("ebfmi_min") is not None and dg["ebfmi_min"] <= 0.3:
            bad.append(f"E-BFMI {dg['ebfmi_min']:.2f} ≤ 0,3")
        if bad:
            ctx.note(f"{ru}: критерии сходимости не выполнены — " + ", ".join(bad) +
                     "; медианы можно использовать осторожно, интервалы приближённые")
    for f in sorted(ctx.out_dir.glob("*_bayes_*")):
        ctx.result["files"].append({"name": f.name, "title": f.stem, "format": f.suffix[1:]})
    ctx.add_file("bayes_cohort.xlsx", "Байесовская модель (Excel)").write_bytes(views.bayes_excel(per_species))
    ctx.add_table("bayes_totals", "Численность 1–2+ по байесовской модели", views.BAYES_COLUMNS, rows)
    ctx.set_payload({"mode": mode, "species": payload})
    ctx.save_state({"res": res, "props": props, "pdu": pdu, "mode": mode, "species": list(runtime), "runtime": runtime})
    return {"species": list(runtime), "mode": mode}
