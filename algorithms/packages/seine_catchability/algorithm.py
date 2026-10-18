"""Этап 1. Уловистость невода (перенос fish_stock_forecast, формулы без изменений)."""
from fishcore import stepkit, views
from fishcore.catchability_seine import compute_seine_catchability, save_results

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    ctx.progress(0.1, phase="расчёт")
    ctx.log("подгонка сигмоид по видам и годам")
    res = compute_seine_catchability(ctx.water_body, b)
    ctx.progress(0.7, phase="запись результатов")
    save_results(res, ctx.out_dir)
    for f in sorted(ctx.out_dir.glob("*.nc")) + sorted(ctx.out_dir.glob("*.csv")):
        ctx.result["files"].append({"name": f.name, "title": "Коэффициенты уловистости невода", "format": f.suffix[1:]})
    ctx.add_file("seine_catchability.xlsx", "Уловистость невода (Excel)").write_bytes(views.seine_excel(res))
    ctx.add_frame("params", "Параметры сигмоид по видам и годам", res.params_frame())
    ctx.add_table(*views.catchability_tables(res.cube_frame(), "coefficients", "Коэффициенты уловистости невода c"))
    ctx.set_payload(views.seine_payload(res))
    bad = int(res.params_frame()["статус"].astype(str).str.contains("нарушено").sum()) if "статус" in res.params_frame() else 0
    ctx.metric("fits", len(res.fits), "Подогнано сигмоид")
    ctx.metric("violations", bad, "Нарушений ограничений (26)")
    ctx.save_state({"seine_c": res})
    return {"species": res.species, "years": res.years}
