"""
Представления результатов для интерфейса и выгрузки (перенос app/services*.py из fish_stock_forecast
без состояния и без сравнения со старым проектом). Формулы расчёта здесь не участвуют.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from . import config
from .ages import age_label, age_title
from .net_model import zone0_substeps
from .stock import GEARS, MEAN, METHOD_TITLES, METHODS, VARIANT_TITLES, VARIANTS


def num(x):
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def arr(a):
    return [num(v) for v in np.asarray(a).tolist()]


def ints(a):
    return [None if not np.isfinite(v) else int(round(v)) for v in np.asarray(a, float).tolist()]


def jq(a, digits: int = 6):
    a = np.asarray(a)
    if a.ndim == 0:
        v = a.item()
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if isinstance(v, (int, np.integer)):
            return int(v)
        v = float(v)
        return None if not np.isfinite(v) else float(f"{v:.{digits}g}")
    return [jq(x, digits) for x in a]


def autowidth(xw):
    for ws in xw.book.worksheets:
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 40)


# ---------------------------------------------------------------- этап 1: невод
def seine_payload(res) -> dict:
    fits = {}
    for (fish, year), r in res.fits.items():
        fits.setdefault(fish, {})[str(year)] = {
            "ages": arr(r.ages.astype(int)), "observed": arr(r.observed), "fitted": arr(r.fitted),
            "weights": arr(r.weights), "c": arr(r.catchability),
            "a": num(r.fit.a), "j50": num(r.fit.j50), "j50_rule": num(r.j50_rule),
            "b": num(r.fit.b), "Z": num(r.fit.Z), "r2": num(r.fit.r2),
            "c_mean": num(r.c_mean), "m0": r.m0, "m1": r.m1,
            "n_sample": r.n_sample, "total_catch": num(r.total_catch), "n_hauls": r.n_hauls,
            "source": r.source, "status": r.status,
            "first_lower_active": r.fit.first_lower_active,
            "lower_active": r.fit.lower_active, "upper_active": r.fit.upper_active,
            "observed_is_catch": r.source.startswith("годовой улов"),
        }
    return {"waterbody": res.waterbody, "years": res.years, "species": res.species,
            "c_lower": config.SEINE_C_LOWER, "c_lower_first": config.SEINE_C_LOWER_FIRST,
            "c_upper": config.SEINE_C_UPPER, "fits": fits}


def seine_excel(res) -> bytes:
    params = res.params_frame()
    cube = res.cube_frame().pivot_table(index=["вид", "год"], columns="возраст", values="c", sort=False)
    labels = [age_label(a) for a in res.all_ages]
    cube = cube.reindex(columns=[c for c in labels if c in cube.columns])
    cube = cube.reindex(pd.MultiIndex.from_product([res.species, res.years], names=["вид", "год"]))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        params.to_excel(xw, sheet_name="Параметры сигмоид", index=False)
        cube.to_excel(xw, sheet_name="Коэффициенты c(вид,год,возр)")
        autowidth(xw)
    return buf.getvalue()


# ---------------------------------------------------------------- этап 2: сеть и запас
def net_payload(res, net_c, props) -> dict:
    return net_payload_parts(net_c, props, res.years, res.species, res.ages, res.sigma.get("with_ages"))


def net_payload_parts(net_c, props, years, species, ages, sigma=None) -> dict:
    """Параметры парабол сети для мониторинга; sigma (годы, виды, группы) — доля балансовой модели, если посчитана
    (алгоритм d); у алгоритма a её нет — поле пустое (решение № 70)."""
    years, species = list(years), list(species)
    fits = {}
    for (fish, year), r in net_c.fits.items():
        if year not in years or fish not in species:
            continue
        yi, si = years.index(year), species.index(fish)
        idx = [int(np.where(ages == a)[0][0]) for a in r.ages]
        p = r.parabola
        fits.setdefault(fish, {})[str(year)] = {
            "ages": arr(r.ages.astype(int)), "observed": arr(r.observed), "c": arr(r.catchability),
            "sigma": arr(sigma[yi, si, idx]) if sigma is not None else None,
            "peak": num(p.peak), "c0": num(p.c0), "a1": num(p.a1), "a2": num(p.a2),
            "c_mean": num(r.c_mean), "m0": r.m0, "m1": r.m1,
            "n_sample": r.n_sample, "total_catch": num(r.total_catch), "n_hauls": r.n_hauls,
            "source": r.source, "status": r.status, "observed_is_catch": r.source.startswith("годовой улов"),
            "hours": num(float(props.net_hours[year])), "net_length": num(float(props.net_length[year])),
            "speed": num(float(props.cruise_speed[fish]) * 3600),
            "c_lower": num(r.c_mean * config.NET_C_LOWER_FRAC), "substeps": zone0_substeps(float(props.net_length[year]), float(props.cruise_speed[fish]) * 3600),
        }
    # нижняя граница c сети — своя у каждого вида (c̄/3), она в каждой подгонке; общей нет
    return {"waterbody": net_c.waterbody, "years": years, "species": species,
            "c_lower": None, "c_lower_frac": config.NET_C_LOWER_FRAC, "c_upper": config.NET_C_UPPER, "fits": fits,
            "panels": {"mode": config.NET_PANELS_MODE, "by_type": dict(config.NET_PANELS_BY_CATCH_TYPE)}}


def stock_payload(res) -> dict:
    species = {}
    for si, fish in enumerate(res.species):
        m1 = res.m1[fish]
        age_idx = [i for i, a in enumerate(res.ages) if 2 <= a <= m1]
        block = {"ages": [int(res.ages[i]) for i in age_idx], "variants": {}}
        vm = res.variant_methods()
        for v in [x for x in VARIANTS if any(x == a for a, _ in vm)]:
            vb = {}
            for meth in [m for a, m in vm if a == v]:
                mb = {"totals": {}, "by_age": {}}
                for g in (*GEARS, MEAN):
                    mb["totals"][g] = ints(res.yearly_total(g, v, meth)[:, si])
                    mb["by_age"][g] = [ints(res.yearly[(g, v, meth)][yi, si, age_idx]) for yi in range(len(res.years))]
                vb[meth] = mb
            vb["hauls"] = {g: ints(res.per_haul_total(g, v)[:, si]) for g in GEARS}
            block["variants"][v] = vb
        block["n_hauls"] = {g: arr(res.catches[g].yearly_count()[:, si]) for g in GEARS}
        block["npc"] = ints(res.npc_stock[:, si]) if res.npc_stock is not None else None
        species[fish] = block
    hauls = {}
    for g in GEARS:
        m = res.catches[g].meta
        hauls[g] = {"year": m["Year"].astype(int).tolist(), "date": m["Date"].astype(str).tolist(),
                    "place": m["Place"].astype(str).tolist(), "type": m["CatchType"].astype(str).tolist()}
    return {"waterbody": res.waterbody, "years": res.years, "species_list": res.species, "species": species,
            "hauls": hauls, "gears": {"net": config.GEAR_NET, "seine": config.GEAR_SEINE, "mean": MEAN},
            "variant_titles": VARIANT_TITLES, "method_titles": METHOD_TITLES, "method": res.method,
            "methods": sorted({m for _, m in res.variant_methods()}, key=METHODS.index),
            "variants_list": sorted({v for v, _ in res.variant_methods()}, key=VARIANTS.index),
            "combine_how": config.COMBINE_GEARS, "net_formula": config.NET_STOCK_FORMULA}


def stock_excel(res, net_c) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        res.totals_frame().to_excel(xw, sheet_name="Годовой запас (итоги)", index=False)
        for v in [x for x in VARIANTS if (MEAN, x, res.method) in res.yearly or (MEAN, x, "on_stock") in res.yearly]:
            rows = []
            meth = "on_stock" if (MEAN, v, "on_stock") in res.yearly else res.method
            for g in (*GEARS, MEAN):
                cube = res.yearly[(g, v, meth)]
                for si, fish in enumerate(res.species):
                    for yi, year in enumerate(res.years):
                        row = {"орудие": g, "вид": fish, "год": year}
                        for ai, a in enumerate(res.ages):
                            if 2 <= a <= res.m1[fish]:
                                row[f"возраст {age_label(a)}"] = cube[yi, si, ai]
                        rows.append(row)
            name = "По возрастам, c по возр." if v == "with_ages" else "По возрастам, c средняя"
            pd.DataFrame(rows).to_excel(xw, sheet_name=name, index=False)
        for g in GEARS:
            hc = res.catches[g]
            df = hc.meta.copy()
            tot = res.per_haul_total(g, "with_ages")
            for si, fish in enumerate(res.species):
                df[f"{fish}, запас шт"] = tot[:, si]
            df.to_excel(xw, sheet_name=f"Оценки по ловам ({g})", index=False)
        net_c.params_frame().to_excel(xw, sheet_name="Параметры парабол сети", index=False)
        cube = net_c.cube_frame().pivot_table(index=["вид", "год"], columns="возраст", values="c", sort=False)
        cube = cube.reindex(columns=[c for c in (age_label(a) for a in res.ages) if c in cube.columns])
        cube.to_excel(xw, sheet_name="Уловистость сети c")
        autowidth(xw)
    return buf.getvalue()


def stock_tables(res) -> list[tuple[str, str, list[dict], list[dict]]]:
    """Плоские таблицы для дашбордов."""
    out = []
    rows = []
    for v, meth in res.variant_methods():
        if True:
            for g in (*GEARS, MEAN):
                tot = res.yearly_total(g, v, meth)
                for si, fish in enumerate(res.species):
                    for yi, year in enumerate(res.years):
                        rows.append({"year": year, "species": fish, "gear": g, "variant": v, "method": meth,
                                     "stock": num(tot[yi, si])})
    out.append(("yearly_stock", "Годовой запас по уловам, шт",
                [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
                 {"code": "gear", "title": "Орудие"}, {"code": "variant", "title": "Уловистость"},
                 {"code": "method", "title": "Метод"}, {"code": "stock", "title": "Запас", "unit": "шт", "type": "number"}],
                rows))
    rows = []
    cube = res.yearly[(MEAN, "with_ages", "on_stock" if (MEAN, "with_ages", "on_stock") in res.yearly else res.method)]
    for si, fish in enumerate(res.species):
        for yi, year in enumerate(res.years):
            for ai, a in enumerate(res.ages):
                if 2 <= a <= res.m1[fish]:
                    rows.append({"year": year, "species": fish, "age": int(a), "age_title": age_title(int(a)),
                                 "stock": num(cube[yi, si, ai])})
    out.append(("stock_by_age", "Окончательный запас по возрастам (сеть и невод), шт",
                [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
                 {"code": "age", "title": "Возраст j", "type": "integer"}, {"code": "age_title", "title": "Возраст"},
                 {"code": "stock", "title": "Запас", "unit": "шт", "type": "number"}], rows))
    if res.npc_stock is not None:
        rows = [{"year": y, "species": s, "npc_stock": num(res.npc_stock[yi, si])}
                for si, s in enumerate(res.species) for yi, y in enumerate(res.years)]
        out.append(("npc_stock", "Оценка запаса НПЦ, шт",
                    [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
                     {"code": "npc_stock", "title": "Запас НПЦ", "unit": "шт", "type": "number"}], rows))
    return out


def catchability_tables(cube_frame: pd.DataFrame, code: str, title: str):
    rows = [{"species": r["вид"], "year": int(r["год"]), "age": r["возраст"], "c": num(r["c"])}
            for r in cube_frame.to_dict(orient="records")]
    return (code, title, [{"code": "species", "title": "Вид"}, {"code": "year", "title": "Год", "type": "integer"},
                          {"code": "age", "title": "Возраст"}, {"code": "c", "title": "Уловистость c", "type": "number"}],
            rows)


# ---------------------------------------------------------------- этап 3: ПДУ НПЦ по возрастам
def pdu_payload(pdu) -> dict:
    dist = pdu.distributed_t()
    bio = pdu.fishable_biomass_t()
    expl = pdu.exploitation()
    species = {}
    for si, fish in enumerate(pdu.species):
        idx = [i for i, a in enumerate(pdu.ages) if 2 <= a <= pdu.m1[fish]]
        species[fish] = {
            "m0": pdu.m0[fish], "m1": pdu.m1[fish], "ages": [int(pdu.ages[i]) for i in idx],
            "weight_filled": [bool(pdu.weight_filled[si, i]) for i in idx],
            "pdu_t": arr(pdu.pdu_t[:, si]), "distributed_t": arr(dist[:, si]), "left_t": arr(pdu.left_t[:, si]),
            "pieces_total": ints(pdu.pieces[:, si].sum(axis=1)), "biomass_t": arr(bio[:, si]),
            "iterations": [int(v) for v in pdu.iterations[:, si]],
            "stop_reason": [pdu.stop_reason[yi][si] for yi in range(len(pdu.years))],
            "by_year": [{
                "stock": ints(pdu.stock[yi, si, idx]), "weight": arr(pdu.weights[yi, si, idx]),
                "pieces": ints(pdu.pieces[yi, si, idx]),
                "tonnes": arr(pdu.pieces[yi, si, idx] * pdu.weights[yi, si, idx] / 1e6),
                "exploitation": arr(expl[yi, si, idx]), "capped": [bool(v) for v in pdu.capped[yi, si, idx]],
            } for yi in range(len(pdu.years))],
        }
    return {"waterbody": pdu.waterbody, "years": pdu.years, "species_list": pdu.species, "species": species,
            "cap": config.PDU_CAP}


def pdu_rows(pdu) -> list[dict]:
    expl = pdu.exploitation()
    rows = []
    for si, fish in enumerate(pdu.species):
        for yi, year in enumerate(pdu.years):
            for ai, a in enumerate(pdu.ages):
                if not (2 <= a <= pdu.m1[fish]):
                    continue
                rows.append({"species": fish, "year": year, "age": int(a), "age_title": age_title(int(a)),
                             "stock": num(pdu.stock[yi, si, ai]), "weight_g": num(pdu.weights[yi, si, ai]),
                             "weight_filled": bool(pdu.weight_filled[si, ai]), "pdu_pcs": num(pdu.pieces[yi, si, ai]),
                             "pdu_t": num(pdu.pieces[yi, si, ai] * pdu.weights[yi, si, ai] / 1e6),
                             "exploitation": num(expl[yi, si, ai]), "capped": bool(pdu.capped[yi, si, ai])})
    return rows


PDU_COLUMNS = [
    {"code": "species", "title": "Вид"}, {"code": "year", "title": "Год", "type": "integer"},
    {"code": "age", "title": "Возраст j", "type": "integer"}, {"code": "age_title", "title": "Возраст"},
    {"code": "stock", "title": "Окончательный запас", "unit": "шт", "type": "number"},
    {"code": "weight_g", "title": "Средний вес", "unit": "г", "type": "number"},
    {"code": "weight_filled", "title": "Вес взят от младшего возраста", "type": "boolean"},
    {"code": "pdu_pcs", "title": "ПДУ", "unit": "шт", "type": "number"},
    {"code": "pdu_t", "title": "ПДУ", "unit": "т", "type": "number"},
    {"code": "exploitation", "title": "Доля изъятия", "type": "number"},
    {"code": "capped", "title": "Ограничение 75 %", "type": "boolean"},
]


def pdu_excel(pdu) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pdu.summary_frame().to_excel(xw, sheet_name="Итоги по годам", index=False)
        rename = {c["code"]: c["title"] + (f", {c['unit']}" if c.get("unit") else "") for c in PDU_COLUMNS}
        pd.DataFrame(pdu_rows(pdu)).rename(columns=rename).to_excel(xw, sheet_name="По возрастам", index=False)
        autowidth(xw)
    return buf.getvalue()


# ---------------------------------------------------------------- этап 4: байесовская модель
def _total(by_age):
    by_age = np.asarray(by_age, float)
    return np.where(np.isnan(by_age).all(axis=1), np.nan, np.nansum(by_age, axis=1))


def bayes_payload(species: str, a: dict, meta: dict, source: str) -> dict:
    years = [int(y) for y in a["years"]]
    X_q = a["X_q"]
    obs_mean = a["obs_stock_mean"]
    deaths = {
        "natural": jq(a["dead_natural_pcs"].sum(axis=1)), "predators": jq(a["dead_predators_pcs"].sum(axis=1)),
        "catch": jq(np.nansum(a["pdu_raw"], axis=1)), "poaching": jq(a["dead_brac_pcs"].sum(axis=1)),
        "recruits": jq(X_q[2][:, 0]),
    }
    keep_meta = {k: meta.get(k) for k in (
        "mode", "mode_title", "started", "finished", "seconds", "chains", "draws_per_chain", "tune", "divergences",
        "divergences_by_chain", "treedepth_hits", "step_size", "acceptance_rate", "rhat_X_max", "numpy_check",
        "notes", "n_obs", "dropped", "m0", "m1", "m2", "fec_bounds", "monotonic_violations", "monotonic_ok",
        "cap_active_cells", "diagnostics", "config_short")}
    return {
        "species": species, "source": source, "available": True, "meta": keep_meta,
        "param_rows": meta.get("param_rows", []), "config_used": meta.get("config", {}),
        "years": years, "model_ages": jq(a["model_ages"]), "obs_ages": jq(a["obs_ages"]),
        "quantiles": jq(a["quantiles"]), "total_obs_q": jq(a["total_obs_q"]), "total_all_q": jq(a["total_all_q"]),
        "X_q": jq(X_q), "s_q": jq(a["s_q"]), "pred_q": jq(a["pred_q"]), "beta1d_q": jq(a["beta1d_q"]),
        "q_bias_q": jq(a["q_bias_q"]), "theta_q": jq(a["theta_q"]), "density_alpha_q": jq(a["density_alpha_q"]),
        "rhat_X": jq(a["rhat_X"]) if "rhat_X" in a else None,
        # с версии 2.0.0: поправка уловистости сети q_net, доля лет-возрастов с ограничением изъятия
        "log_q_net_q": jq(a["log_q_net_q"]) if "log_q_net_q" in a else None,
        "cap_active_frac": jq(a["cap_active_frac"]) if "cap_active_frac" in a else None,
        "press_base_q": jq(a["press_base_q"]) if "press_base_q" in a else None,
        "deaths": deaths,
        "data": {
            "final_by_age": jq(a["yearly_final"]), "net_by_age": jq(a["yearly_net"]),
            "seine_by_age": jq(a["yearly_seine"]), "final_total": jq(_total(a["yearly_final"])),
            "net_total": jq(_total(a["yearly_net"])), "seine_total": jq(_total(a["yearly_seine"])),
            "npc_total": jq(a["npc_total"]), "obs_mean_net": jq(obs_mean[0]), "obs_mean_seine": jq(obs_mean[1]),
            "pdu_by_age": jq(a["pdu_raw"]), "x0": jq(a["x0"]),
        },
    }


def bayes_rows(species: str, a: dict) -> list[dict]:
    years = [int(y) for y in a["years"]]
    rows = []
    for yi, y in enumerate(years):
        rows.append({"species": species, "year": y,
                     "total_q025": num(a["total_obs_q"][0, yi]), "total_q25": num(a["total_obs_q"][1, yi]),
                     "total_median": num(a["total_obs_q"][2, yi]), "total_q75": num(a["total_obs_q"][3, yi]),
                     "total_q975": num(a["total_obs_q"][4, yi]),
                     "by_catch": num(_total(a["yearly_final"])[yi]),
                     "npc": num(a["npc_total"][yi]) if a["npc_total"] is not None and a["npc_total"].ndim else None})
    return rows


BAYES_COLUMNS = [
    {"code": "species", "title": "Вид"}, {"code": "year", "title": "Год", "type": "integer"},
    {"code": "total_median", "title": "Численность 1–2+, медиана", "unit": "шт", "type": "number"},
    {"code": "total_q025", "title": "2,5 %", "unit": "шт", "type": "number"},
    {"code": "total_q25", "title": "25 %", "unit": "шт", "type": "number"},
    {"code": "total_q75", "title": "75 %", "unit": "шт", "type": "number"},
    {"code": "total_q975", "title": "97,5 %", "unit": "шт", "type": "number"},
    {"code": "by_catch", "title": "Окончательный запас по уловам", "unit": "шт", "type": "number"},
    {"code": "npc", "title": "Оценка НПЦ", "unit": "шт", "type": "number"},
]


def bayes_excel(per_species: dict[str, tuple[dict, dict]]) -> bytes:
    qn = ["2,5 %", "25 %", "медиана", "75 %", "97,5 %"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for species, (a, meta) in per_species.items():
            years = [int(y) for y in a["years"]]
            ages = [int(v) for v in a["model_ages"]]
            rows = []
            for yi, y in enumerate(years):
                r = {"год": y}
                for k, n in enumerate(qn):
                    r[f"возрасты 1–2 и старше, {n}"] = a["total_obs_q"][k, yi]
                r["окончательный запас по уловам"] = _total(a["yearly_final"])[yi]
                r["оценка НПЦ"] = a["npc_total"][yi]
                rows.append(r)
            pd.DataFrame(rows).to_excel(xw, sheet_name=f"{species} — численность"[:31], index=False)
            df = pd.DataFrame(a["X_q"][2], index=years, columns=[age_title(j) for j in ages])
            df.index.name = "год"
            df.to_excel(xw, sheet_name=f"{species} — по возрастам"[:31])
            prow = [{"параметр": r["label"], "индекс": r["index"], "2,5 %": r["q"][0], "медиана": r["q"][2],
                     "97,5 %": r["q"][4], "R-hat": r["rhat"]} for r in meta.get("param_rows", [])]
            pd.DataFrame(prow).to_excel(xw, sheet_name=f"{species} — параметры"[:31], index=False)
        autowidth(xw)
    return buf.getvalue()


def catch_by_age_tables(res) -> list[tuple[str, str, list[dict], list[dict], str]]:
    """Улов по ловам и возрастам Y_ijd = Y_id · q_ij(t_d) (формула (20)) и доли возрастной пробы q_ij(t).
    Только чтение уже рассчитанного массива: формулы и результаты этапа не меняются."""
    return catch_by_age_tables_hc([res.catches[g] for g in GEARS])


def catch_by_age_tables_hc(catches: list) -> list[tuple[str, str, list[dict], list[dict], str]]:
    """То же по списку уловов орудий (алгоритмы c и d — по одному орудию)."""
    ages = [int(a) for a in catches[0].ages]
    age_cols = [{"code": f"a{a}", "title": f"j = {a}", "unit": "шт", "type": "number"} for a in ages]
    rows = []
    for hc in catches:
        g = hc.gear
        if not len(hc.meta):
            continue
        tot = hc.totals()
        m = hc.meta.reset_index(drop=True)
        for d in range(len(m)):
            for si, fish in enumerate(hc.species):
                if np.isnan(tot[d, si]):
                    continue
                r = {"haul": int(m.at[d, "Id"]), "gear": g, "year": int(m.at[d, "Year"]), "date": str(m.at[d, "Date"])[:10],
                     "place": None if pd.isna(m.at[d, "Place"]) else str(m.at[d, "Place"]),
                     "catch_type": None if pd.isna(m.at[d, "CatchType"]) else str(m.at[d, "CatchType"]),
                     "species": fish, "total": num(tot[d, si])}
                for ai, a in enumerate(ages):
                    v = hc.values[d, si, ai]
                    r[f"a{a}"] = None if np.isnan(v) else round(float(v), 4)
                rows.append(r)
    t1 = ("catch_by_age", "Улов по ловам и возрастам, шт",
          [{"code": "haul", "title": "Лов №", "type": "integer"}, {"code": "gear", "title": "Орудие"},
           {"code": "year", "title": "Год", "type": "integer"}, {"code": "date", "title": "Дата"},
           {"code": "place", "title": "Место лова"}, {"code": "catch_type", "title": "Тип лова"},
           {"code": "species", "title": "Вид"}, {"code": "total", "title": "Улов вида в лове", "unit": "шт", "type": "number"},
           *age_cols], rows,
          "Y_ijd = Y_id · q_ij(t_d): улов вида в лове, разложенный по возрастным группам по долям возрастной пробы "
          "года лова.")
    hc = catches[0]
    srows = []
    for yi, y in enumerate(hc.years):
        for si, fish in enumerate(hc.species):
            if not hc.sample_raw[yi, si].any() and not hc.shares[yi, si].any():
                continue
            r = {"year": int(y), "species": fish, "n_sample": num(hc.sample_raw[yi, si].sum())}
            for ai, a in enumerate(ages):
                r[f"q{a}"] = round(float(hc.shares[yi, si, ai]), 6)
                r[f"n{a}"] = num(hc.sample_raw[yi, si, ai])
            srows.append(r)
    t2 = ("age_shares", "Доли возрастной пробы q_ij(t)",
          [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
           {"code": "n_sample", "title": "Рыб в пробе", "unit": "шт", "type": "number"},
           *[{"code": f"q{a}", "title": f"q, j = {a}", "type": "number"} for a in ages],
           *[{"code": f"n{a}", "title": f"проба, j = {a}", "unit": "шт", "type": "number"} for a in ages]], srows,
          f"q_ij(t) — доля возрастной группы j в сглаженной пробе года t: к группам j ≤ m1 прибавляется в сумме "
          f"{config.AGE_PSEUDOCOUNT_TOTAL:g} условн. рыба (поровну); если в пробе меньше {config.AGE_POOL_MIN_SAMPLE} рыб, "
          f"к ней прибавляются пробы соседних лет (± {config.AGE_POOL_NEIGHBOURS}).")
    return [t1, t2]


# ---------------------------------------------------------------- алгоритмы каталога (решение № 70)
def net_excel(net_c) -> bytes:
    params = net_c.params_frame()
    cube = net_c.cube_frame().pivot_table(index=["вид", "год"], columns="возраст", values="c", sort=False)
    labels = [age_label(a) for a in net_c.all_ages]
    cube = cube.reindex(columns=[c for c in labels if c in cube.columns])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        params.to_excel(xw, sheet_name="Параметры парабол сети", index=False)
        cube.to_excel(xw, sheet_name="Коэффициенты c(вид,год,возр)")
        autowidth(xw)
    return buf.getvalue()


def age_mask(species, ages, m1) -> np.ndarray:
    """(виды, группы) — группы от 2 до m1 вида (как StockResult.age_mask)."""
    return np.array([[2 <= a <= m1[s] for a in ages] for s in species])


def per_haul_totals(per: np.ndarray, species, ages, m1) -> np.ndarray:
    """(ловы, виды) — оценка запаса по лову, сумма групп 2..m1; NaN — вид в лове не учитывался."""
    m = age_mask(species, ages, m1)[None, :, :]
    all_nan = np.all(np.isnan(np.where(m, per, np.nan)), axis=2)
    return np.where(all_nan, np.nan, np.nansum(np.where(m, per, 0.0), axis=2))


def yearly_totals(cube: np.ndarray, species, ages, m1) -> np.ndarray:
    """(годы, виды) — годовой запас по сумме групп 2..m1; NaN, если данных нет."""
    m = age_mask(species, ages, m1)[None, :, :]
    all_nan = np.all(np.isnan(np.where(m, cube, np.nan)), axis=2)
    return np.where(all_nan, np.nan, np.nansum(np.where(m, cube, 0.0), axis=2))


def hauls_meta(hc) -> dict:
    m = hc.meta
    return {"id": m["Id"].astype(int).tolist() if len(m) else [], "year": m["Year"].astype(int).tolist(),
            "date": m["Date"].astype(str).tolist(), "place": m["Place"].astype(str).tolist(),
            "type": m["CatchType"].astype(str).tolist(),
            "area_ha": [num(x) for x in m["Area"].tolist()] if "Area" in m else None}


def per_haul_table(hc, per, m1, title: str):
    """Таблица «оценки запаса по ловам»: лов, год, дата, место, тип лова, вид, запас по группам и всего."""
    ages = [int(a) for a in hc.ages]
    tot = per_haul_totals(per, hc.species, hc.ages, m1)
    m = hc.meta.reset_index(drop=True)
    rows = []
    for d in range(len(m)):
        for si, fish in enumerate(hc.species):
            if np.isnan(tot[d, si]):
                continue
            r = {"haul": int(m.at[d, "Id"]), "year": int(m.at[d, "Year"]), "date": str(m.at[d, "Date"])[:10],
                 "place": None if pd.isna(m.at[d, "Place"]) else str(m.at[d, "Place"]),
                 "catch_type": None if pd.isna(m.at[d, "CatchType"]) else str(m.at[d, "CatchType"]),
                 "species": fish, "stock": num(tot[d, si])}
            for ai, a in enumerate(ages):
                if 2 <= a <= m1[fish]:
                    v = per[d, si, ai]
                    r[f"a{a}"] = None if np.isnan(v) else num(v)
            rows.append(r)
    cols = [{"code": "haul", "title": "Лов №", "type": "integer"}, {"code": "year", "title": "Год", "type": "integer"},
            {"code": "date", "title": "Дата"}, {"code": "place", "title": "Место лова"},
            {"code": "catch_type", "title": "Тип лова"}, {"code": "species", "title": "Вид"},
            {"code": "stock", "title": "Запас по лову", "unit": "шт", "type": "number"},
            *[{"code": f"a{a}", "title": f"j = {a}", "unit": "шт", "type": "number"} for a in ages]]
    return "per_haul", title, cols, rows


def likelihood_payload(hc, per, m1, years) -> dict:
    tot = per_haul_totals(per, hc.species, hc.ages, m1)
    return {"gear": hc.gear, "years": list(years), "species": list(hc.species), "hauls": hauls_meta(hc),
            "totals": {fish: ints(tot[:, si]) for si, fish in enumerate(hc.species)},
            "n_hauls": {fish: arr(hc.yearly_count()[:, si]) for si, fish in enumerate(hc.species)}}


def gear_stock_parts(gear: str, method: str, years, species, ages, m1, cube, t_all, t_fish, counts):
    """Таблицы и представление годового запаса одного орудия (алгоритмы e, f)."""
    tot = yearly_totals(cube, species, ages, m1)
    rows, brows = [], []
    for si, fish in enumerate(species):
        for yi, y in enumerate(years):
            rows.append({"year": int(y), "species": fish, "gear": gear, "method": method, "stock": num(tot[yi, si]),
                         "tonnes_all": num(t_all[yi, si]), "tonnes_fishable": num(t_fish[yi, si]),
                         "hauls": num(counts[yi, si])})
            for ai, a in enumerate(ages):
                if 2 <= a <= m1[fish]:
                    brows.append({"year": int(y), "species": fish, "age": int(a), "age_title": age_title(int(a)),
                                  "stock": num(cube[yi, si, ai])})
    t1 = ("yearly", f"Годовой запас ({gear}), шт и т",
          [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
           {"code": "gear", "title": "Орудие"}, {"code": "method", "title": "Способ"},
           {"code": "stock", "title": "Запас", "unit": "шт", "type": "number"},
           {"code": "tonnes_all", "title": "Запас, все возрасты", "unit": "т", "type": "number"},
           {"code": "tonnes_fishable", "title": "Промысловый запас", "unit": "т", "type": "number"},
           {"code": "hauls", "title": "Ловов", "type": "number"}], rows)
    t2 = ("by_age", f"Годовой запас ({gear}) по возрастам, шт",
          [{"code": "year", "title": "Год", "type": "integer"}, {"code": "species", "title": "Вид"},
           {"code": "age", "title": "Возраст j", "type": "integer"}, {"code": "age_title", "title": "Возраст"},
           {"code": "stock", "title": "Запас", "unit": "шт", "type": "number"}], brows)
    sp = {}
    for si, fish in enumerate(species):
        idx = [i for i, a in enumerate(ages) if 2 <= a <= m1[fish]]
        sp[fish] = {"ages": [int(ages[i]) for i in idx], "totals": ints(tot[:, si]),
                    "by_age": [ints(cube[yi, si, idx]) for yi in range(len(years))],
                    "tonnes_all": jq(t_all[:, si], 3), "tonnes_fishable": jq(t_fish[:, si], 3),
                    "n_hauls": arr(counts[:, si])}
    payload = {"gear": gear, "method": method, "method_title": METHOD_TITLES.get(method, method),
               "years": [int(y) for y in years], "species": sp}
    return [t1, t2], payload
