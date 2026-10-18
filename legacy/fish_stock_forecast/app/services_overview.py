"""Страница «Обзор»: сводка по видам и состояние шагов расчёта."""
from __future__ import annotations

from datetime import datetime

import numpy as np

from core.bayes import config as bc
from app import services, services_bayes, services_forecast, services_stock


def _f(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def overview_payload() -> dict:
    res, _ = services_stock.get_stage2()
    pdu = services_stock.get_pdu()
    years = list(res.years)
    y_last = years[-1]
    total = res.combined_total("with_ages", "on_stock")          # (годы, виды)
    fishable = pdu.fishable_biomass_t()
    bov = services_bayes.overview()["species"]
    fc = {r["species"]: r for r in services_forecast.summary_payload()["rows"]}
    fc_raw = services_forecast.load_raw()

    rows = []
    for sp in bc.DEFAULTS:
        si = list(res.species).index(sp) if sp in res.species else None
        new = bov[sp]["results"]["new"]
        f = fc.get(sp, {})
        rows.append({
            "species": sp, "token": bc.TOKENS[sp],
            "stock_series": [_f(v) for v in total[:, si]] if si is not None else None,
            "stock_last": _f(total[-1, si]) if si is not None else None,
            "npc_stock_last": _f(res.npc_stock[-1, si]) if (si is not None and res.npc_stock is not None) else None,
            "fishable_last_t": _f(fishable[-1, si]) if si is not None else None,
            "npc_pdu_last_t": _f(pdu.pdu_t[-1, si]) if si is not None else None,
            "bayes": None if new is None else {"finished": new["finished"], "divergences": new["divergences"],
                                               "rhat": new["rhat_X_max"], "seconds": new["seconds"]},
            "forecast": None if not f.get("available") else {
                "pdu_next_t": f["pdu_next_t"], "total_end": f["total_end"], "p_decline": f["p_decline"]},
        })

    n_bayes = sum(1 for r in rows if r["bayes"])
    dates = [r["bayes"]["finished"] for r in rows if r["bayes"] and r["bayes"]["finished"]]
    fc_years = None
    for r in rows:
        if r["forecast"]:
            res_fc, _ = services_forecast.compute(r["species"])
            fc_years = [res_fc.years_fc[0], res_fc.years_fc[-1]]
            break
    steps = [
        {"num": 1, "href": "/catchability/seine", "title": "Уловистость невода",
         "status": f"рассчитана {services._state['computed_at']}" if services._state["computed_at"] else "не рассчитана",
         "ok": services._state["result"] is not None},
        {"num": 2, "href": "/catchability/net", "title": "Уловистость сети",
         "status": f"рассчитана {services_stock._state['computed_at']}", "ok": True},
        {"num": 3, "href": "/stock", "title": "Запас по уловам",
         "status": f"рассчитан {services_stock._state['computed_at']}", "ok": True},
        {"num": 4, "href": "/pdu", "title": "ПДУ по возрастам",
         "status": f"рассчитан {services_stock._state['computed_at']}", "ok": True},
        {"num": 5, "href": "/bayes", "title": "Байесовская модель",
         "status": f"рассчитано видов: {n_bayes} из {len(rows)}"
                   + (f", последний {datetime.fromisoformat(max(dates)).strftime('%d.%m.%Y %H:%M')}" if dates else ""),
         "ok": n_bayes == len(rows), "partial": 0 < n_bayes < len(rows)},
        {"num": 6, "href": "/forecast", "title": "Прогноз и ПДУ",
         "status": (f"горизонт {int(fc_raw.get('horizon', 5))} лет, k = {float(fc_raw.get('k', 1.0)):g}; "
                    f"видов с прогнозом: {n_bayes} из {len(rows)}"),
         "ok": n_bayes == len(rows), "partial": 0 < n_bayes < len(rows)},
    ]
    return {"years": years, "last_year": y_last, "forecast_years": fc_years, "rows": rows, "steps": steps,
            "k": float(fc_raw.get("k", 1.0))}
