"""j. Прогноз запаса и оценка ПДУ по модели (перенос fish_stock_forecast: core/forecast.py и app/services_forecast.py;
решение № 70)."""
import io

import numpy as np
import pandas as pd

from fishcore import stepkit, views
from fishcore.ages import age_title
from fishcore.bayes import run as R
from fishcore.bayes.dynamics import NumpyOps, mortality_matrix
from fishcore.data_source import load_fish_props, load_npc
from fishcore.forecast import (K_GRID_DEFAULT, MAX_HORIZON, SCENARIO_TITLES, SCENARIOS, ForecastSettings, parse_k_grid,
                               posterior_from_npz, q, run_forecast)
from fishcore.pdu_npc import filled_weights

jq = views.jq


def _k_grid(ctx):
    from fishrunner import UserError
    raw = ctx.params.get("k_scenarios")
    try:
        return parse_k_grid(K_GRID_DEFAULT if raw is None else raw)
    except ValueError as e:
        raise UserError(str(e)) from None




def _settings(ctx, ru, code, k_grid=()) -> ForecastSettings:
    p = ctx.params
    mort = (p.get("mortality") or {}).get(code) or (p.get("mortality") or {}).get(ru) or {}
    pdu_map = p.get("pdu_t") or {}
    pdu_t = pdu_map.get(code, pdu_map.get(ru))
    return ForecastSettings(horizon=int(p.get("horizon") or 5), k=float(p.get("k") if p.get("k") is not None else 1.0),
                            areas={int(y): float(v) for y, v in (p.get("areas") or {}).items() if v not in (None, "")},
                            mortality={int(y): float(v) for y, v in mort.items() if v not in (None, "")},
                            pdu_t=None if pdu_t in (None, "") else float(pdu_t),
                            seed=int(p.get("seed") if p.get("seed") is not None else 42), k_grid=tuple(k_grid))


def _hist_s_mature(post):
    vals = []
    for i in range(0, post.n_draws, 10):
        pp = {k: post.draws[k][i] for k in ("s_base", "s_juvenile_steep", "s_aging_slow")}
        s = mortality_matrix(NumpyOps, pp, post.draws["s_year_fluct"][i], post.m0, post.m1, post.cfg)
        vals.append(s[:, post.ages >= post.m0].mean())
    return float(np.median(vals)) if vals else None


def run(ctx):
    from fishrunner import UserError
    b = stepkit.bundle(ctx, "species_props", "yearly_conditions", "mean_weights")
    bdir = ctx.input_dir("bayes_cohort")
    if bdir is None:
        raise UserError("Прогноз строится по результатам математической модели: укажите вход «i. Запас по "
                        "математической модели» (по умолчанию — основной расчёт водоёма)")
    h = int(ctx.params.get("horizon") or 5)
    if not 1 <= h <= MAX_HORIZON:
        raise UserError(f"Горизонт прогноза — от 1 до {MAX_HORIZON} лет")
    k_grid = _k_grid(ctx)
    props = load_fish_props(ctx.water_body, b)
    _, pdu_df = load_npc(ctx.water_body, b)
    code_by_ru = {ru: code for code, ru in ctx.species_names.items()}
    files = sorted(bdir.glob(f"{ctx.water_body}_bayes_*.npz"))
    files = [f for f in files if not f.stem.endswith(("_prior", "_check"))]
    if not files:
        raise UserError("В результатах байесовской модели нет расчёта в режиме «расчёт» (априорная проверка не подходит)")
    wanted = ctx.params.get("species")
    out, summary, xrows, krows, kyrows = {}, [], {}, [], []
    posts = []
    for f in files:
        loaded = R.load_npz(f)
        if loaded is None:
            continue
        post = posterior_from_npz(*loaded)
        code = code_by_ru.get(post.species, post.species)
        if wanted and code not in wanted:
            continue
        posts.append((post, code))
    if not posts:
        raise UserError("Нет результатов байесовской модели для выбранных видов")
    for i, (post, code) in enumerate(posts):
        ru = post.species
        ctx.progress(i / len(posts), species=ru)
        s = _settings(ctx, ru, code, k_grid)
        wh, filled = filled_weights(props, ru, post.years, post.ages)
        y_last = post.years[-1]
        npc_last = float(pdu_df.loc[y_last, ru]) if (pdu_df is not None and y_last in pdu_df.index
                                                    and ru in pdu_df.columns and np.isfinite(pdu_df.loc[y_last, ru])) else 0.0
        npc_hist = [float(pdu_df.loc[y, ru]) if (pdu_df is not None and y in pdu_df.index and ru in pdu_df.columns) else None
                    for y in post.years]
        area_last = float(props.lake_area_km2.get(y_last, list(props.lake_area_km2.values())[-1]))
        res = run_forecast(post, s, wh, wh[-1], float(props.fry_density[ru]), area_last, npc_last)
        sc_out = {}
        for sc in SCENARIOS:
            sc_out[sc] = {
                "total_q": jq(q(res.total(sc))), "biomass_q": jq(q(res.biomass(sc))), "fishable_q": jq(q(res.fishable(sc))),
                "pdu_t_q": jq(q(res.pdu_tonnes(sc))), "removal_t_q": jq(q(res.removal_tonnes(sc))),
                "pdu_pcs_median": jq(np.median(res.catch[sc], axis=0)), "pdu_pcs_total_q": jq(q(res.catch[sc].sum(axis=2))),
                "X_last_q": jq(q(res.X[sc][:, -1, :])), "p_decline": res.p_decline(sc),
            }
        out[ru] = {
            "species": ru, "code": code, "available": True, "finished": post.finished,
            "years_hist": res.years_hist, "years_fc": res.years_fc, "ages": jq(res.ages), "m0": res.m0,
            "n_draws": int(post.n_draws),
            "hist": {"total_q": jq(post.total_obs_q), "biomass_q": jq(q(res.hist_biomass)),
                     "fishable_q": jq(q(res.hist_fishable)), "X_last_q": jq(post.X_q[:, -1, :]),
                     "npc_pdu_t": jq(npc_hist), "total_last_draws_q": jq(q(res.hist_total[:, -1]))},
            "scenarios": sc_out, "scenario_titles": SCENARIO_TITLES,
            "beta_q": jq(q(res.beta)), "s_mature_q": jq(q(res.s_mature)), "F_q": jq(q(res.F)), "Mbar_q": jq(q(res.Mbar)),
            "weights": jq(res.weights), "weight_filled": jq(filled),
            "s_mature_hist": _hist_s_mature(post),
            "settings": {"horizon": len(res.years_fc), "k": res.settings.k, "areas": jq(res.areas_used),
                         "area_default_years": res.area_default_years, "mortality": res.mortality_used,
                         "pdu_fixed_t": res.pdu_fixed_t, "npc_last": npc_last},
            "notes": res.notes,
        }
        if res.k_grid:
            ks = res.k_grid
            base_k = 1.0 if 1.0 in ks else res.settings.k
            kp = {kk: res.k_pdu_tonnes(kk) for kk in ks}
            base = float(np.median((kp[base_k] if base_k in kp else res.pdu_tonnes("baranov"))[:, 0]))
            out[ru]["k_scen"] = {
                "k": ks, "base_k": base_k, "pdu_t_q": [jq(q(kp[kk][:, 0])) for kk in ks],
                "pdu_t_median_years": [jq(np.median(kp[kk], axis=0)) for kk in ks],
                "F": [float(np.median(res.k_F[kk][:, 0])) for kk in ks],
                "total_end_q": [jq(q(res.k_total(kk)[:, -1])) for kk in ks],
                "p_decline": [res.k_p_decline(kk) for kk in ks], "p_decline_none": res.p_decline("none"),
                "total_q_years": [jq(q(res.k_total(kk))) for kk in ks],
                "fishable_q_years": [jq(q(res.k_fishable(kk))) for kk in ks]}
            for kk in ks:
                tq, fq = q(res.k_total(kk)), q(res.k_fishable(kk))
                for hh, y in enumerate(res.years_fc):
                    kyrows.append({"species": ru, "k": kk, "year": y, "total_median": float(tq[2, hh]), "total_q025": float(tq[0, hh]),
                                   "total_q975": float(tq[4, hh]), "fishable_t": float(fq[2, hh]),
                                   "pdu_t": float(np.median(kp[kk][:, hh]))})
            for j, kk in enumerate(ks):
                pq = q(kp[kk][:, 0])
                krows.append({"species": ru, "k": kk, "F": out[ru]["k_scen"]["F"][j], "pdu_t": float(pq[2]),
                              "pdu_t_q025": float(pq[0]), "pdu_t_q975": float(pq[4]),
                              "pdu_pct_base": float(pq[2]) / base * 100 if base > 0 else None,
                              "total_end": float(np.median(res.k_total(kk)[:, -1])),
                              "p_decline": res.k_p_decline(kk) * 100, "p_decline_none": res.p_decline("none") * 100})
        bq = res.pdu_tonnes("baranov")[:, 0]
        summary.append({
            "species": ru, "code": code, "total_last": float(np.median(res.hist_total[:, -1])),
            "fishable_last_t": float(np.median(res.hist_fishable[:, -1])),
            "pdu_next_t": float(np.median(bq)), "pdu_next_t_q025": float(np.quantile(bq, 0.025)),
            "pdu_next_t_q975": float(np.quantile(bq, 0.975)), "F_next": float(np.median(res.F[:, 0])),
            "pdu_fixed_t": res.pdu_fixed_t, "npc_last_t": npc_last,
            **{f"p_decline_{sc}": res.p_decline(sc) for sc in SCENARIOS},
            **{f"total_end_{sc}": float(np.median(res.total(sc)[:, -1])) for sc in SCENARIOS},
            "year_last": res.years_hist[-1], "year_first_fc": res.years_fc[0], "year_last_fc": res.years_fc[-1],
        })
        rows = []
        for sc in SCENARIOS:
            tq, bq_, pq, rq = q(res.total(sc)), q(res.fishable(sc)), q(res.pdu_tonnes(sc)), q(res.removal_tonnes(sc))
            for hh, y in enumerate(res.years_fc):
                row = {"species": ru, "scenario": sc, "scenario_title": SCENARIO_TITLES[sc], "year": y,
                       "total_median": tq[2, hh], "total_q025": tq[0, hh], "total_q975": tq[4, hh],
                       "fishable_t": bq_[2, hh], "pdu_t": pq[2, hh], "pdu_t_q025": pq[0, hh], "pdu_t_q975": pq[4, hh],
                       "removal_t": rq[2, hh], "beta": float(np.median(res.beta[:, hh])), "area_km2": res.areas_used[hh],
                       "s_mature": float(np.median(res.s_mature[:, hh])),
                       "F": float(np.median(res.F[:, hh])) if sc == "baranov" else None}
                med = np.median(res.catch[sc][:, hh, :], axis=0)
                row["pdu_pcs_by_age"] = {str(int(a)): float(v) for a, v in zip(res.ages, med) if a >= res.m0}
                rows.append(row)
        xrows[ru] = rows

    flat = [{k: v for k, v in r.items() if k != "pdu_pcs_by_age"} for rows in xrows.values() for r in rows]
    ctx.add_table("forecast", "Прогноз по сценариям", [
        {"code": "species", "title": "Вид"}, {"code": "scenario_title", "title": "Сценарий"},
        {"code": "scenario", "title": "Код сценария"}, {"code": "year", "title": "Год", "type": "integer"},
        {"code": "total_median", "title": "Численность 1–2+, медиана", "unit": "шт", "type": "number"},
        {"code": "total_q025", "title": "Численность 2,5 %", "unit": "шт", "type": "number"},
        {"code": "total_q975", "title": "Численность 97,5 %", "unit": "шт", "type": "number"},
        {"code": "fishable_t", "title": "Промысловая биомасса", "unit": "т", "type": "number"},
        {"code": "pdu_t", "title": "ПДУ, медиана", "unit": "т", "type": "number"},
        {"code": "pdu_t_q025", "title": "ПДУ 2,5 %", "unit": "т", "type": "number"},
        {"code": "pdu_t_q975", "title": "ПДУ 97,5 %", "unit": "т", "type": "number"},
        {"code": "removal_t", "title": "Изъятие β·ПДУ", "unit": "т", "type": "number"},
        {"code": "beta", "title": "β", "type": "number"}, {"code": "F", "title": "F", "type": "number"},
        {"code": "s_mature", "title": "s половозрелых", "type": "number"},
        {"code": "area_km2", "title": "Площадь", "unit": "км²", "type": "number"}], flat)
    ctx.add_table("forecast_summary", "Сводка прогноза по видам", [
        {"code": "species", "title": "Вид"},
        {"code": "total_last", "title": "Численность, последний год истории", "unit": "шт", "type": "number"},
        {"code": "fishable_last_t", "title": "Промысловая биомасса", "unit": "т", "type": "number"},
        {"code": "pdu_next_t", "title": "ПДУ F = k·M, первый год, медиана", "unit": "т", "type": "number"},
        {"code": "pdu_next_t_q025", "title": "ПДУ 2,5 %", "unit": "т", "type": "number"},
        {"code": "pdu_next_t_q975", "title": "ПДУ 97,5 %", "unit": "т", "type": "number"},
        {"code": "F_next", "title": "F", "type": "number"},
        {"code": "npc_last_t", "title": "ПДУ НПЦ последнего года", "unit": "т", "type": "number"},
        {"code": "pdu_fixed_t", "title": "Фиксированный ПДУ", "unit": "т", "type": "number"},
        {"code": "p_decline_baranov", "title": "Вероятность снижения (F = k·M)", "type": "number"},
        {"code": "p_decline_fixed", "title": "Вероятность снижения (фикс. ПДУ)", "type": "number"},
        {"code": "p_decline_none", "title": "Вероятность снижения (без промысла)", "type": "number"}], summary)

    if krows:
        y1 = summary[0]["year_first_fc"] if summary else None
        base_k = 1.0 if 1.0 in k_grid else float(ctx.params.get("k") or 1.0)
        base_title = f"{base_k:g}".replace(".", ",")
        ctx.add_table("k_scenarios", "Сценарии k: ПДУ и вероятность снижения запаса", [
            {"code": "species", "title": "Вид"}, {"code": "k", "title": "k", "type": "number"},
            {"code": "F", "title": "F, первый год", "type": "number"},
            {"code": "pdu_t", "title": f"ПДУ {y1}, медиана", "unit": "т", "type": "number"},
            {"code": "pdu_t_q025", "title": "ПДУ 2,5 %", "unit": "т", "type": "number"},
            {"code": "pdu_t_q975", "title": "ПДУ 97,5 %", "unit": "т", "type": "number"},
            {"code": "pdu_pct_base", "title": f"ПДУ, % от k = {base_title}", "unit": "%", "type": "number"},
            {"code": "total_end", "title": "Численность в конце прогноза, медиана", "unit": "шт", "type": "number"},
            {"code": "p_decline", "title": "Вероятность снижения запаса", "unit": "%", "type": "number"},
            {"code": "p_decline_none", "title": "Вероятность снижения без промысла", "unit": "%", "type": "number"}], krows)
        ctx.add_table("k_years", "Сценарии k: запас по годам прогноза", [
            {"code": "species", "title": "Вид"}, {"code": "k", "title": "k", "type": "number"}, {"code": "year", "title": "Год", "type": "integer"},
            {"code": "total_median", "title": "Численность 1–2+, медиана", "unit": "шт", "type": "number"},
            {"code": "total_q025", "title": "Численность 2,5 %", "unit": "шт", "type": "number"},
            {"code": "total_q975", "title": "Численность 97,5 %", "unit": "шт", "type": "number"},
            {"code": "fishable_t", "title": "Промысловая биомасса, медиана", "unit": "т", "type": "number"},
            {"code": "pdu_t", "title": "ПДУ, медиана", "unit": "т", "type": "number"}], kyrows)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(summary).to_excel(xw, sheet_name="Сводка", index=False)
        if krows:
            pd.DataFrame(krows).to_excel(xw, sheet_name="Сценарии k", index=False)
            pd.DataFrame(kyrows).to_excel(xw, sheet_name="Сценарии k по годам", index=False)
        for ru, rows in xrows.items():
            df = pd.DataFrame([{**{k: v for k, v in r.items() if k != "pdu_pcs_by_age"},
                                **{f"ПДУ шт, {age_title(int(a))}": v for a, v in r["pdu_pcs_by_age"].items()}}
                               for r in rows])
            df.to_excel(xw, sheet_name=ru[:31], index=False)
        views.autowidth(xw)
    ctx.add_file("forecast.xlsx", "Прогноз и ПДУ (Excel)").write_bytes(buf.getvalue())
    ctx.set_payload({"species": out, "summary": summary, "k": float(ctx.params.get("k") or 1.0), "horizon": h,
                     "scenario_titles": SCENARIO_TITLES, "k_grid": list(k_grid)})
    for r in summary:
        ctx.metric(f"pdu_next_{r['code']}", r["pdu_next_t"], f"ПДУ {r['species']}, {r['year_first_fc']} г.", "т")
    return {"species": [s for s in out]}
