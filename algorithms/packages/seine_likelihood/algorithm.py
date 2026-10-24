"""c. Правдоподобие методом площадей для уловов неводом: оценка запаса по каждому лову (решение № 66).
Формула та же, что в расчёте запаса по уловам fish_stock_forecast (fishcore.stock.seine_per_haul)."""
from fishcore import config, stepkit, views
from fishcore.catch import build_haul_catch
from fishcore.data_source import load_fish_props
from fishcore.stock import gear_inputs, seine_per_haul
from fishcore.years import year_index

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    from fishrunner import UserError
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    sc = stepkit.need_input(ctx, "seine_catchability")
    years = stepkit.years_for(ctx, b.catch_years(), seine_catchability=sc["years"])
    b = stepkit.keep_years(b, years)
    ctx.progress(0.1, phase="улов по ловам и возрастам")
    props = load_fish_props(ctx.water_body, b)
    hc = build_haul_catch(config.GEAR_SEINE, ctx.water_body, b, props)
    stepkit.check_species(sc["species"], hc.species, "расчёта уловистости невода")
    if list(hc.years) != years:
        raise UserError("Годы уловов не совпадают с годами периода расчёта")
    cube = sc["cube"][year_index(sc["years"], hc.years)]
    area, _, _, _ = gear_inputs(props, hc.years, hc.species)
    ctx.progress(0.4, phase="запас по каждому лову")
    per = seine_per_haul(hc, cube, area)
    m1 = dict(props.m1)
    if not len(hc.meta):
        ctx.note("У водоёма за период нет ловов неводом — оценок по ловам нет; в окончательном запасе будет оценка сети")
    ctx.add_table(*views.per_haul_table(hc, per, m1, "Оценки запаса по ловам неводом, шт"))
    for code, title, cols, rows, desc in views.catch_by_age_tables_hc([hc]):
        ctx.add_table(code, title, cols, rows, desc)
    ctx.set_payload(views.likelihood_payload(hc, per, m1, hc.years))
    ctx.metric("hauls", int(len(hc.meta)), "Ловов неводом")
    ctx.save_state({"gear": config.GEAR_SEINE, "catch": hc, "per_haul": per, "cube": cube, "area": area,
                    "years": list(hc.years), "species": list(hc.species), "ages": hc.ages, "m1": m1})
    return {"species": list(hc.species), "years": list(hc.years), "hauls": int(len(hc.meta))}
