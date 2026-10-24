"""e. Ежегодный запас методом площадей (шт и т) по оценкам по ловам неводом (решение № 70).
Формулы те же, что в расчёте запаса по уловам fish_stock_forecast (fishcore.stock.seine_yearly)."""
from fishcore import biomass, config, stepkit, views
from fishcore.data_source import load_fish_props
from fishcore.stock import seine_yearly
from fishcore.years import select_gear_state

DATASETS = ("species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    st = stepkit.need_input(ctx, "seine_likelihood")
    years = stepkit.years_for(ctx, stepkit.in_period(ctx, st["years"]), seine_likelihood=st["years"])
    st = select_gear_state(st, years)
    method = ctx.params.get("STOCK_METHOD") or "on_stock"
    props = load_fish_props(ctx.water_body, stepkit.keep_years(b, years))
    hc = st["catch"]
    ctx.progress(0.2, phase="годовой запас")
    yearly = seine_yearly(hc, st["per_haul"], st["cube"], st["area"], method)
    t_all = biomass.tonnes(yearly, props, years, hc.species, hc.ages, fishable=False)
    t_fish = biomass.tonnes(yearly, props, years, hc.species, hc.ages, fishable=True)
    tables, payload = views.gear_stock_parts(config.GEAR_SEINE, method, years, hc.species, hc.ages, st["m1"],
                                             yearly, t_all, t_fish, hc.yearly_count())
    for t in tables:
        ctx.add_table(*t)
    ctx.set_payload(payload)
    ctx.save_state({**st, "method": method, "yearly": yearly, "tonnes_all": t_all, "tonnes_fishable": t_fish})
    return {"species": list(hc.species), "years": years, "method": method}
