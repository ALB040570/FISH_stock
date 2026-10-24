"""g. Ежегодный запас, усреднённый по неводу и сети (шт и т) — окончательный запас (решение № 70).
Формулы те же, что в расчёте запаса по уловам fish_stock_forecast (fishcore.stock.combine_gears)."""
import io

import numpy as np
import pandas as pd

from fishcore import biomass, config, stepkit, views
from fishcore.ages import age_label
from fishcore.data_source import load_fish_props, load_npc
from fishcore.stock import MEAN, StockResult, combine_gears
from fishcore.years import select_gear_state

DATASETS = ("species_props", "yearly_conditions", "mean_weights")
NET, SEINE = config.GEAR_NET, config.GEAR_SEINE


def run(ctx):
    from fishrunner import UserError
    stepkit.apply_fixed(ctx.params)
    b = stepkit.bundle(ctx, *DATASETS)
    se = stepkit.need_input(ctx, "seine_stock")
    ne = stepkit.need_input(ctx, "net_stock")
    if se["method"] != ne["method"]:
        raise UserError("Годовой запас неводом и сетью посчитан разными способами (по запасам / по улову) — "
                        "выберите входы, посчитанные одним способом")
    years = stepkit.years_for(ctx, stepkit.in_period(ctx, se["years"]), seine_stock=se["years"], net_stock=ne["years"])
    se, ne = select_gear_state(se, years), select_gear_state(ne, years)
    stepkit.check_species(se["species"], ne["species"], "запаса неводом и сетью")
    by = stepkit.keep_years(b, years)
    props = load_fish_props(ctx.water_body, by)
    m = se["method"]
    species, ages = list(se["species"]), se["ages"]
    res = StockResult(ctx.water_body, years, species, ages, dict(se["m1"]),
                      {NET: ne["catch"], SEINE: se["catch"]},
                      {(NET, "with_ages"): ne["cube"], (SEINE, "with_ages"): se["cube"]},
                      {"with_ages": ne["sigma"]}, method=m)
    res.per_haul = {(NET, "with_ages"): ne["per_haul"], (SEINE, "with_ages"): se["per_haul"]}
    res.yearly = {(NET, "with_ages", m): ne["yearly"], (SEINE, "with_ages", m): se["yearly"]}
    ctx.progress(0.2, phase="окончательный запас")
    res.yearly[(MEAN, "with_ages", m)] = combine_gears([ne["yearly"], se["yearly"]],
                                                       [ne["catch"].yearly_count(), se["catch"].yearly_count()])
    npc_stock, _ = load_npc(ctx.water_body, by)
    if npc_stock is not None:
        res.npc_stock = np.array([[npc_stock.loc[y, s] * config.NPC_STOCK_MULTIPLIER
                                   if (y in npc_stock.index and s in npc_stock.columns) else np.nan
                                   for s in species] for y in years])
    else:
        ctx.note("Нет набора «Оценка запаса НПЦ» — сравнение с НПЦ не показывается")
    cube = res.yearly[(MEAN, "with_ages", m)]
    tonnes = {MEAN: (biomass.tonnes(cube, props, years, species, ages, False),
                     biomass.tonnes(cube, props, years, species, ages, True)),
              NET: (ne["tonnes_all"], ne["tonnes_fishable"]), SEINE: (se["tonnes_all"], se["tonnes_fishable"])}
    ctx.progress(0.6, phase="запись результатов")
    for code, title, cols, rows in views.stock_tables(res):
        ctx.add_table(code, title, cols, rows)
    trows = []
    tot = {g: res.yearly_total(g, "with_ages", m) for g in (NET, SEINE, MEAN)}
    for si, fish in enumerate(species):
        for yi, y in enumerate(years):
            for g in (NET, SEINE, MEAN):
                trows.append({"year": int(y), "species": fish, "gear": g, "stock": views.num(tot[g][yi, si]),
                              "tonnes_all": views.num(tonnes[g][0][yi, si]), "tonnes_fishable": views.num(tonnes[g][1][yi, si])})
    ctx.add_table("tonnes", "Запас по уловам, шт и т",
                  [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
                   {"code": "gear", "title": "Орудие"}, {"code": "stock", "title": "Запас", "unit": "шт", "type": "number"},
                   {"code": "tonnes_all", "title": "Запас, все возрасты", "unit": "т", "type": "number"},
                   {"code": "tonnes_fishable", "title": "Промысловый запас", "unit": "т", "type": "number"}], trows)
    ctx.add_frame("totals", "Годовой запас (итоги)", res.totals_frame())
    ctx.add_file("combined_stock.xlsx", "Запас по уловам (Excel)").write_bytes(_excel(res, trows))
    ctx.set_payload({"stock": views.stock_payload(res),
                     "tonnes": {fish: {g: {"all": views.jq(tonnes[g][0][:, si], 3), "fishable": views.jq(tonnes[g][1][:, si], 3)}
                                       for g in (NET, SEINE, MEAN)} for si, fish in enumerate(species)}})
    ctx.save_state({"res": res, "props": props, "method": m, "tonnes": tonnes})
    return {"species": species, "years": years, "method": m}


def _excel(res, trows) -> bytes:
    buf = io.BytesIO()
    m = res.method
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        res.totals_frame().to_excel(xw, sheet_name="Годовой запас (итоги)", index=False)
        pd.DataFrame(trows).rename(columns={"year": "год", "species": "вид", "gear": "орудие", "stock": "запас, шт",
                                            "tonnes_all": "запас, т", "tonnes_fishable": "промысловый запас, т"}
                                   ).to_excel(xw, sheet_name="Запас в тоннах", index=False)
        rows = []
        for g in (NET, SEINE, MEAN):
            cube = res.yearly[(g, "with_ages", m)]
            for si, fish in enumerate(res.species):
                for yi, year in enumerate(res.years):
                    row = {"орудие": g, "вид": fish, "год": year}
                    for ai, a in enumerate(res.ages):
                        if 2 <= a <= res.m1[fish]:
                            row[f"возраст {age_label(a)}"] = cube[yi, si, ai]
                    rows.append(row)
        pd.DataFrame(rows).to_excel(xw, sheet_name="По возрастам", index=False)
        views.autowidth(xw)
    return buf.getvalue()
