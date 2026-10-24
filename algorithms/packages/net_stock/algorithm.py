"""f. Ежегодный запас балансовым методом (шт и т) по оценкам по ловам сетью (решение № 66).
Формулы те же, что в расчёте запаса по уловам fish_stock_forecast (fishcore.stock.net_yearly)."""
from fishcore import biomass, config, stepkit, views
from fishcore.data_source import load_fish_props
from fishcore.stock import net_yearly
from fishcore.years import select_gear_state

DATASETS = ("species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    st = stepkit.need_input(ctx, "net_likelihood")
    years = stepkit.years_for(ctx, stepkit.in_period(ctx, st["years"]), net_likelihood=st["years"])
    st = select_gear_state(st, years)
    # «по улову» зависит от числа сетей одной ячеи и формулы запаса — те же, с которыми считался вход d
    cfg = st.get("config") or {}
    for k in ("NET_PANELS_MODE", "NET_STOCK_FORMULA"):
        if cfg.get(k) is not None:
            setattr(config, k, cfg[k])
    if cfg.get("NET_PANELS_BY_CATCH_TYPE"):
        config.NET_PANELS_BY_CATCH_TYPE.update(cfg["NET_PANELS_BY_CATCH_TYPE"])
    method = ctx.params.get("STOCK_METHOD") or "on_stock"
    props = load_fish_props(ctx.water_body, stepkit.keep_years(b, years))
    hc = st["catch"]
    ctx.progress(0.2, phase="годовой запас")
    yearly = net_yearly(hc, st["per_haul"], st["sigma"], st["area"], st["speed"], st["length"], method)
    t_all = biomass.tonnes(yearly, props, years, hc.species, hc.ages, fishable=False)
    t_fish = biomass.tonnes(yearly, props, years, hc.species, hc.ages, fishable=True)
    tables, payload = views.gear_stock_parts(config.GEAR_NET, method, years, hc.species, hc.ages, st["m1"],
                                             yearly, t_all, t_fish, hc.yearly_count())
    for t in tables:
        ctx.add_table(*t)
    ctx.set_payload(payload)
    ctx.save_state({**st, "method": method, "yearly": yearly, "tonnes_all": t_all, "tonnes_fishable": t_fish})
    return {"species": list(hc.species), "years": years, "method": method}
