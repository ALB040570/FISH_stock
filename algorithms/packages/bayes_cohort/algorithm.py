"""Этап 4. Байесовская когортная модель (перенос fish_stock_forecast, уравнения без изменений)."""
import json
from pathlib import Path

from fishcore import stepkit, views
from fishcore.bayes import config as bc
from fishcore.bayes import run as R
from fishcore.data_source import load_fish_props
from fishcore.pdu_npc import compute_pdu
from fishcore.stock import compute_stock

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights", "npc_pdu")
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
    prev3 = ctx.load_state("pdu_by_age")
    if prev3 is not None:
        res, props, pdu = prev3["res"], prev3["props"], prev3["pdu"]
    else:
        prev2 = ctx.load_state("stock_by_catch")
        if prev2 is not None:
            res, props = prev2["res"], prev2["props"]
        else:
            ctx.log("этапы 2–3 не переданы цепочкой — рассчитываются внутри шага")
            props = load_fish_props(ctx.water_body, b)
            res, _, _ = compute_stock(ctx.water_body, b, props=props)
        pdu = compute_pdu(res, props, data_dir=b)

    profiles = _profiles(ctx)
    code_by_ru = {ru: code for code, ru in ctx.species_names.items()}
    wanted = ctx.params.get("species") or [code_by_ru.get(s, s) for s in res.species if code_by_ru.get(s, s) in profiles]
    if not wanted:
        raise UserError("Для водоёма нет профиля параметров байесовской модели ни для одного вида. "
                        "Заполните профиль водоёма (Каталог → Профили водоёмов).")
    missing = [s for s in wanted if s not in profiles]
    if missing:
        raise UserError("Нет профиля параметров для видов: " + ", ".join(ctx.species_names.get(s, s) for s in missing))
    run_over = {k: ctx.params[k] for k in RUN_KEYS if ctx.params.get(k) is not None}
    runtime = {}
    for code in wanted:
        ru = ctx.species_names.get(code, code)
        if ru not in res.species:
            raise UserError(f"Вид «{ru}» отсутствует в данных этапов 1–3")
        values = {**profiles[code], **run_over}
        errs = bc.validate(ru, values)
        if errs:
            raise UserError(f"Профиль вида «{ru}»: " + "; ".join(errs))
        runtime[ru] = values
    bc.set_runtime(runtime)
    mode = ctx.params.get("mode") or "new"
    payload, rows, per_species = {}, [], {}
    n = len(runtime)
    for i, ru in enumerate(runtime):
        def progress(d, i=i, ru=ru):
            frac = None
            if d.get("total") and d.get("chains"):
                done = sum(d["chains"].values()) / max(1, len(d["chains"]))
                frac = (i + min(1.0, done / d["total"])) / n
            ctx.progress(frac if frac is not None else i / n, species=ru, **d)
        ctx.log(f"вид {ru} ({i + 1} из {n}), режим {mode}")
        meta = R.run(ru, mode, progress=progress, log=ctx.log, results_dir=ctx.out_dir, stage23=(res, pdu, props))
        loaded = R.load_npz(R.result_path(ru, mode, "npz", ctx.out_dir))
        a, m = loaded
        payload[ru] = views.bayes_payload(ru, a, m, mode)
        rows += views.bayes_rows(ru, a)
        per_species[ru] = (a, m)
        ctx.metric(f"divergences_{code_by_ru.get(ru, ru)}", meta.get("divergences"), f"Расходимости: {ru}")
        ctx.metric(f"rhat_{code_by_ru.get(ru, ru)}", meta.get("rhat_X_max"), f"R̂ max: {ru}")
        if meta.get("rhat_X_max") and meta["rhat_X_max"] > 1.05:
            ctx.note(f"{ru}: R̂ = {meta['rhat_X_max']:.3f} > 1,05 — цепи не сошлись, увеличьте число шагов настройки")
    for f in sorted(ctx.out_dir.glob("*_bayes_*")):
        ctx.result["files"].append({"name": f.name, "title": f.stem, "format": f.suffix[1:]})
    ctx.add_file("bayes_cohort.xlsx", "Байесовская модель (Excel)").write_bytes(views.bayes_excel(per_species))
    ctx.add_table("bayes_totals", "Численность 1–2+ по байесовской модели", views.BAYES_COLUMNS, rows)
    ctx.set_payload({"mode": mode, "species": payload})
    ctx.save_state({"res": res, "props": props, "pdu": pdu, "mode": mode, "species": list(runtime)})
    return {"species": list(runtime), "mode": mode}
