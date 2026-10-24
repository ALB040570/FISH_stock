"""d. Правдоподобие балансовым методом для уловов сетью: σ балансовой модели и оценка запаса по каждому лову
(решение № 66). Формулы те же, что в расчёте запаса по уловам fish_stock_forecast (fishcore.stock)."""
from fishcore import config, stepkit, views
from fishcore.catch import build_haul_catch
from fishcore.data_source import load_fish_props
from fishcore.stock import gear_inputs, net_per_haul, net_sigma
from fishcore.years import select_fits, year_index

DATASETS = ("catches", "age_samples", "species_props", "yearly_conditions", "mean_weights")


def run(ctx):
    from fishrunner import UserError
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    nc = stepkit.need_input(ctx, "net_catchability")
    years = stepkit.years_for(ctx, b.catch_years(), net_catchability=nc["years"])
    b = stepkit.keep_years(b, years)
    ctx.progress(0.05, phase="улов по ловам и возрастам")
    props = load_fish_props(ctx.water_body, b)
    hc = build_haul_catch(config.GEAR_NET, ctx.water_body, b, props)
    stepkit.check_species(nc["species"], hc.species, "расчёта уловистости сети")
    if list(hc.years) != years:
        raise UserError("Годы уловов не совпадают с годами периода расчёта")
    cube = nc["cube"][year_index(nc["years"], hc.years)]
    area, speed, hours, length = gear_inputs(props, hc.years, hc.species)
    ctx.progress(0.1, phase="балансовая модель (σ)")
    sigma = net_sigma(cube, hours, length, speed)
    ctx.progress(0.7, phase="запас по каждому лову")
    per = net_per_haul(hc, sigma, area, speed, length)
    m1 = dict(props.m1)
    if not len(hc.meta):
        ctx.note("У водоёма за период нет ловов сетью — оценок по ловам нет; в окончательном запасе будет оценка невода")
    ctx.add_table(*views.per_haul_table(hc, per, m1, "Оценки запаса по ловам сетью, шт"))
    srows = []
    for si, fish in enumerate(hc.species):
        for yi, y in enumerate(hc.years):
            for ai, a in enumerate(hc.ages):
                if config.NET_MIN_AGE <= a <= m1[fish]:
                    srows.append({"year": int(y), "species": fish, "age": int(a), "c": views.num(cube[yi, si, ai]),
                                  "sigma": views.num(sigma[yi, si, ai])})
    ctx.add_table("sigma", "Доля σ рыб первого круга, попавших в сеть",
                  [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
                   {"code": "age", "title": "Возраст j", "type": "integer"}, {"code": "c", "title": "c сети", "type": "number"},
                   {"code": "sigma", "title": "σ", "type": "number"}], srows)
    for code, title, cols, rows, desc in views.catch_by_age_tables_hc([hc]):
        ctx.add_table(code, title, cols, rows, desc)
    net_c = select_fits(nc["net_c"], hc.years)
    ctx.set_payload({**views.likelihood_payload(hc, per, m1, hc.years),
                     "net": views.net_payload_parts(net_c, props, hc.years, hc.species, hc.ages, sigma),
                     "formula": config.NET_STOCK_FORMULA,
                     "panels": {"mode": config.NET_PANELS_MODE, "by_type": dict(config.NET_PANELS_BY_CATCH_TYPE)}})
    ctx.metric("hauls", int(len(hc.meta)), "Ловов сетью")
    # настройки, от которых зависит годовой запас сетью «по улову» (алгоритм f), — вместе с результатом
    cfg = {"NET_PANELS_MODE": config.NET_PANELS_MODE, "NET_STOCK_FORMULA": config.NET_STOCK_FORMULA,
           "NET_PANELS_BY_CATCH_TYPE": dict(config.NET_PANELS_BY_CATCH_TYPE)}
    ctx.save_state({"gear": config.GEAR_NET, "catch": hc, "per_haul": per, "cube": cube, "sigma": sigma, "area": area,
                    "speed": speed, "hours": hours, "length": length, "years": list(hc.years),
                    "species": list(hc.species), "ages": hc.ages, "m1": m1, "config": cfg})
    return {"species": list(hc.species), "years": list(hc.years), "hauls": int(len(hc.meta))}
