"""a. Уловистость сети по возрастам и годам (формулы fish_stock_forecast без изменений; решение № 70)."""
from fishcore import config, stepkit, views
from fishcore.catch import build_haul_catch
from fishcore.catchability_net import compute_net_catchability
from fishcore.data_source import load_fish_props

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    from fishrunner import UserError
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    if not b.catch_years():
        raise UserError("За период расчёта нет лет, где есть и уловы, и рыбы, подвергнутые биологической обработке")
    ctx.progress(0.1, phase="парабола уловистости сети")
    props = load_fish_props(ctx.water_body, b)
    hc = build_haul_catch(config.GEAR_NET, ctx.water_body, b, props)
    net_c = compute_net_catchability(ctx.water_body, b, props, hc)
    ctx.progress(0.7, phase="запись результатов")
    ctx.add_file("net_catchability.xlsx", "Уловистость сети (Excel)").write_bytes(views.net_excel(net_c))
    ctx.add_frame("params", "Параметры парабол сети по видам и годам", net_c.params_frame())
    ctx.add_table(*views.catchability_tables(net_c.cube_frame(), "coefficients", "Коэффициенты уловистости сети c"))
    ctx.set_payload(views.net_payload_parts(net_c, props, hc.years, hc.species, hc.ages, None))
    ctx.metric("fits", len(net_c.fits), "Подогнано парабол")
    ctx.save_state({"net_c": net_c, "cube": net_c.cube(), "years": list(hc.years), "species": list(hc.species),
                    "ages": hc.ages})
    return {"species": list(hc.species), "years": list(hc.years)}
