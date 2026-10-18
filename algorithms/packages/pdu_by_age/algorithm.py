"""Этап 3. ПДУ НПЦ по возрастам (перенос fish_stock_forecast, формулы без изменений)."""
from fishcore import stepkit, views
from fishcore.data_source import load_fish_props
from fishcore.export_nc import save_pdu
from fishcore.pdu_npc import compute_pdu
from fishcore.stock import compute_stock

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights", "npc_pdu")


def run(ctx):
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    prev = ctx.load_state("stock_by_catch")
    if prev is None:
        ctx.log("запас по уловам не передан цепочкой — рассчитывается внутри шага")
        props = load_fish_props(ctx.water_body, b)
        res, _, _ = compute_stock(ctx.water_body, b, props=props)
    else:
        res, props = prev["res"], prev["props"]
    ctx.progress(0.2, phase="распределение ПДУ по возрастам")
    pdu = compute_pdu(res, props, data_dir=b)
    save_pdu(pdu, ctx.out_dir)
    for f in sorted(ctx.out_dir.glob("*.nc")) + sorted(ctx.out_dir.glob("*.csv")):
        ctx.result["files"].append({"name": f.name, "title": f.stem, "format": f.suffix[1:]})
    ctx.add_file("pdu_by_age.xlsx", "ПДУ НПЦ по возрастам (Excel)").write_bytes(views.pdu_excel(pdu))
    ctx.add_table("pdu_by_age", "ПДУ НПЦ по возрастам", views.PDU_COLUMNS, views.pdu_rows(pdu))
    ctx.add_frame("pdu_summary", "Итоги по видам и годам", pdu.summary_frame())
    ctx.set_payload(views.pdu_payload(pdu))
    ctx.save_state({"res": res, "props": props, "pdu": pdu})
    return {"species": pdu.species, "years": pdu.years}
