"""Этап 2. Уловистость сети и запас по уловам (перенос fish_stock_forecast, формулы без изменений)."""
from fishcore import stepkit, views
from fishcore.catchability_seine import compute_seine_catchability
from fishcore.data_source import load_fish_props
from fishcore.export_nc import save_stage2
from fishcore.stock import compute_stock

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    prev = ctx.load_state("seine_catchability")
    if prev is None:
        ctx.log("уловистость невода не передана цепочкой — рассчитывается внутри шага")
        seine_c = compute_seine_catchability(ctx.water_body, b)
    else:
        seine_c = prev["seine_c"]
    ctx.progress(0.1, phase="уловистость сети, модель баланса, запас по ловам")
    props = load_fish_props(ctx.water_body, b)
    res, net_c, _ = compute_stock(ctx.water_body, b, props=props, seine_c=seine_c)
    if "npc_stock" not in ctx.tables:
        ctx.note("Нет набора «Оценка запаса НПЦ» — сравнение с НПЦ не показывается")
    ctx.progress(0.7, phase="запись результатов")
    saved = save_stage2(res, net_c, ctx.out_dir)
    for f in sorted(ctx.out_dir.glob("*.nc")) + sorted(ctx.out_dir.glob("*.csv")):
        ctx.result["files"].append({"name": f.name, "title": f.stem, "format": f.suffix[1:]})
    ctx.add_file("stock_by_catch.xlsx", "Запас по уловам и уловистость сети (Excel)").write_bytes(views.stock_excel(res, net_c))
    for code, title, cols, rows in views.stock_tables(res):
        ctx.add_table(code, title, cols, rows)
    ctx.add_table(*views.catchability_tables(net_c.cube_frame(), "net_coefficients", "Коэффициенты уловистости сети c"))
    for code, title, cols, rows, desc in views.catch_by_age_tables(res):     # формула (20) — для мониторинга
        ctx.add_table(code, title, cols, rows, desc)
    ctx.add_frame("net_params", "Параметры парабол сети", net_c.params_frame())
    ctx.add_frame("totals", "Годовой запас (итоги)", res.totals_frame())
    ctx.set_payload({"net": views.net_payload(res, net_c, props), "stock": views.stock_payload(res)})
    ctx.save_state({"res": res, "net_c": net_c, "props": props})
    return {"species": res.species, "years": res.years}
