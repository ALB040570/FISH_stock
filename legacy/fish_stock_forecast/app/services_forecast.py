"""
Этап 5 для веб-интерфейса: настройки прогноза, расчёт по видам, сводка и Excel.

Настройки хранятся в results/forecast_config.json:
    {"horizon": 5, "k": 1.0, "areas": {"2025": 3250, …},
     "species": {"лещ": {"mortality": {"2025": 0.3, …}, "pdu_t": 4000}, …}}
Прогноз строится по results/zhaysan_bayes_{вид}.npz (новый расчёт этапа 4).
"""
from __future__ import annotations

import io
import json
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from core import config
from core.ages import age_title
from core.bayes import config as bc
from core.bayes import run as R
from core.bayes.dynamics import NumpyOps, mortality_matrix
from core.data_source import load_fish_props, load_npc
from core.forecast import (MAX_HORIZON, SCENARIO_TITLES, SCENARIOS, ForecastSettings, posterior_from_npz, q,
                           run_forecast)
from core.pdu_npc import filled_weights

_lock = threading.RLock()


def _j(a, digits: int = 6):
    a = np.asarray(a)
    if a.ndim == 0:
        v = a.item()
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if isinstance(v, (int, np.integer)):
            return int(v)
        v = float(v)
        return None if not np.isfinite(v) else float(f"{v:.{digits}g}")
    return [_j(x, digits) for x in a]


# ---------------------------------------------------------------- настройки


def settings_path() -> Path:
    return config.RESULTS_DIR / "forecast_config.json"


def load_raw() -> dict:
    p = settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return float(str(v).replace(",", "."))


def validate(body: dict) -> tuple[dict, list[str]]:
    """Проверить и нормализовать настройки со страницы."""
    errors, out = [], {"species": {}}
    try:
        h = int(body.get("horizon", 5))
        if not 1 <= h <= MAX_HORIZON:
            raise ValueError
        out["horizon"] = h
    except (TypeError, ValueError):
        errors.append(f"горизонт прогноза — от 1 до {MAX_HORIZON} лет")
    try:
        k = _num(body.get("k", 1.0))
        if k is None or not 0 <= k <= 10:
            raise ValueError
        out["k"] = k
    except ValueError:
        errors.append("k — число от 0 до 10")
    areas = {}
    for y, v in (body.get("areas") or {}).items():
        try:
            a = _num(v)
            if a is None:
                continue
            if a <= 0:
                raise ValueError
            areas[str(int(y))] = a
        except ValueError:
            errors.append(f"площадь {y}: положительное число, км²")
    out["areas"] = areas
    for sp, sv in (body.get("species") or {}).items():
        if sp not in bc.DEFAULTS:
            continue
        entry = {"mortality": {}}
        for y, v in (sv.get("mortality") or {}).items():
            try:
                m = _num(v)
                if m is None:
                    continue
                if not 0 < m < 1:
                    raise ValueError
                entry["mortality"][str(int(y))] = m
            except ValueError:
                errors.append(f"{sp}, смертность {y}: доля от 0 до 1")
        try:
            p = _num(sv.get("pdu_t"))
            if p is not None and p < 0:
                raise ValueError
            entry["pdu_t"] = p
        except ValueError:
            errors.append(f"{sp}: фиксированный ПДУ — неотрицательное число, т")
        out["species"][sp] = entry
    return out, errors


def save_settings(body: dict) -> dict:
    data, errors = validate(body)
    if errors:
        raise ValueError("; ".join(errors))
    with _lock:
        old = load_raw()
        merged = {**old, **{k: v for k, v in data.items() if k != "species"}}
        species = dict(old.get("species", {}))
        species.update(data.get("species", {}))
        merged["species"] = species
        p = settings_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    return settings_payload()


def reset_settings() -> dict:
    with _lock:
        p = settings_path()
        if p.exists():
            p.unlink()
    return settings_payload()


def settings_for(species: str) -> ForecastSettings:
    raw = load_raw()
    sp = raw.get("species", {}).get(species, {})
    return ForecastSettings(horizon=int(raw.get("horizon", 5)), k=float(raw.get("k", 1.0)),
                            areas={int(y): v for y, v in raw.get("areas", {}).items()},
                            mortality={int(y): v for y, v in sp.get("mortality", {}).items()},
                            pdu_t=sp.get("pdu_t"))


# ---------------------------------------------------------------- исходные данные


def _npz(species: str):
    path = R.result_path(species, "new")
    return path, (path.stat().st_mtime if path.exists() else 0.0)


@lru_cache(maxsize=16)
def _posterior(path: str, mtime: float):
    loaded = R.load_npz(Path(path)) if mtime else None
    return None if loaded is None else posterior_from_npz(*loaded)


def posterior(species: str):
    path, mtime = _npz(species)
    return _posterior(str(path), mtime)


def _context(species: str, post) -> dict:
    props = load_fish_props()
    _, pdu_df = load_npc()
    wh, filled = filled_weights(props, species, post.years, post.ages)
    y_last = post.years[-1]
    npc_last = float(pdu_df.loc[y_last, species]) if (pdu_df is not None and y_last in pdu_df.index
                                                      and species in pdu_df.columns) else 0.0
    npc_hist = [float(pdu_df.loc[y, species]) if (pdu_df is not None and y in pdu_df.index) else None
                for y in post.years]
    return {"weights_hist": wh, "weights_last": wh[-1], "weight_filled": filled,
            "fry_density": float(props.fry_density[species]),
            "area_last": float(props.lake_area_km2.get(y_last, list(props.lake_area_km2.values())[-1])),
            "areas_hist": [float(props.lake_area_km2.get(y, np.nan)) for y in post.years],
            "npc_last": npc_last, "npc_hist": npc_hist}


@lru_cache(maxsize=64)
def _compute(species: str, settings_json: str, mtime: float):
    post = posterior(species)
    s = ForecastSettings(**json.loads(settings_json))
    s.areas = {int(k): v for k, v in s.areas.items()}
    s.mortality = {int(k): v for k, v in s.mortality.items()}
    ctx = _context(species, post)
    res = run_forecast(post, s, ctx["weights_hist"], ctx["weights_last"], ctx["fry_density"], ctx["area_last"],
                       ctx["npc_last"])
    return res, ctx


def compute(species: str):
    post = posterior(species)
    if post is None:
        return None, None
    s = settings_for(species)
    key = json.dumps({"horizon": s.horizon, "k": s.k, "areas": {str(k): v for k, v in s.areas.items()},
                      "mortality": {str(k): v for k, v in s.mortality.items()}, "pdu_t": s.pdu_t,
                      "seed": s.seed}, sort_keys=True)
    with _lock:
        return _compute(species, key, _npz(species)[1])


def _hist_s_mature(post) -> float | None:
    """Средняя s половозрелых за годы истории (медиана по выборкам) — подсказка для полей смертности."""
    vals = []
    for i in range(0, post.n_draws, 10):
        p = {k: post.draws[k][i] for k in ("s_base", "s_juvenile_steep", "s_aging_slow")}
        s = mortality_matrix(NumpyOps, p, post.draws["s_year_fluct"][i], post.m0, post.m1, post.cfg)
        vals.append(s[:, post.ages >= post.m0].mean())
    return float(np.median(vals)) if vals else None


def settings_payload() -> dict:
    raw = load_raw()
    props = load_fish_props()
    _, pdu_df = load_npc()
    y_last = max(props.lake_area_km2)
    species = {}
    for sp in bc.DEFAULTS:
        post = posterior(sp)
        sv = raw.get("species", {}).get(sp, {})
        species[sp] = {
            "token": bc.TOKENS[sp], "available": post is not None,
            "finished": post.finished if post else None,
            "mortality": sv.get("mortality", {}), "pdu_t": sv.get("pdu_t"),
            "npc_last": float(pdu_df.loc[y_last, sp]) if (pdu_df is not None and y_last in pdu_df.index
                                                          and sp in pdu_df.columns) else None,
            "s_mature_hist": _hist_s_mature(post) if post is not None else None,
        }
    return {"horizon": int(raw.get("horizon", 5)), "k": float(raw.get("k", 1.0)), "areas": raw.get("areas", {}),
            "max_horizon": MAX_HORIZON, "last_year": y_last, "area_last": float(props.lake_area_km2[y_last]),
            "areas_hist": {str(y): float(v) for y, v in props.lake_area_km2.items()},
            "species_list": list(bc.DEFAULTS), "species": species,
            "scenarios": list(SCENARIOS), "scenario_titles": SCENARIO_TITLES}


# ---------------------------------------------------------------- результаты


def results_payload(species: str) -> dict:
    res, ctx = compute(species)
    if res is None:
        return {"species": species, "available": False}
    post = posterior(species)
    H = len(res.years_fc)
    sc_out = {}
    for sc in SCENARIOS:
        tot = res.total(sc)
        sc_out[sc] = {
            "total_q": _j(q(tot)), "biomass_q": _j(q(res.biomass(sc))), "fishable_q": _j(q(res.fishable(sc))),
            "pdu_t_q": _j(q(res.pdu_tonnes(sc))), "removal_t_q": _j(q(res.removal_tonnes(sc))),
            "pdu_pcs_median": _j(np.median(res.catch[sc], axis=0)),            # (H, возрасты)
            "pdu_pcs_total_q": _j(q(res.catch[sc].sum(axis=2))),
            "X_last_q": _j(q(res.X[sc][:, -1, :])),                             # (5, возрасты)
            "p_decline": res.p_decline(sc),
        }
    return {
        "species": species, "available": True, "finished": post.finished,
        "years_hist": res.years_hist, "years_fc": res.years_fc, "ages": _j(res.ages), "m0": res.m0,
        "n_draws": int(post.n_draws),
        "hist": {
            "total_q": _j(post.total_obs_q),
            "biomass_q": _j(q(res.hist_biomass)), "fishable_q": _j(q(res.hist_fishable)),
            "X_last_q": _j(post.X_q[:, -1, :]),
            "npc_pdu_t": _j(ctx["npc_hist"]),
            "total_last_draws_q": _j(q(res.hist_total[:, -1])),
        },
        "scenarios": sc_out, "scenario_titles": SCENARIO_TITLES,
        "beta_q": _j(q(res.beta)), "s_mature_q": _j(q(res.s_mature)),
        "F_q": _j(q(res.F)), "Mbar_q": _j(q(res.Mbar)),
        "weights": _j(res.weights), "weight_filled": _j(ctx["weight_filled"]),
        "settings": {"horizon": H, "k": res.settings.k, "areas": _j(res.areas_used),
                     "area_default_years": res.area_default_years, "mortality": res.mortality_used,
                     "pdu_fixed_t": res.pdu_fixed_t, "npc_last": ctx["npc_last"]},
        "notes": res.notes,
    }


def summary_payload() -> dict:
    rows = []
    for sp in bc.DEFAULTS:
        res, ctx = compute(sp)
        if res is None:
            rows.append({"species": sp, "token": bc.TOKENS[sp], "available": False})
            continue
        b = res.pdu_tonnes("baranov")[:, 0]
        rows.append({
            "species": sp, "token": bc.TOKENS[sp], "available": True,
            "total_last": float(np.median(res.hist_total[:, -1])),
            "fishable_last_t": float(np.median(res.hist_fishable[:, -1])),
            "total_end": {sc: float(np.median(res.total(sc)[:, -1])) for sc in SCENARIOS},
            "p_decline": {sc: res.p_decline(sc) for sc in SCENARIOS},
            "pdu_next_t": _j(q(b)), "F_next": float(np.median(res.F[:, 0])),
            "pdu_fixed_t": res.pdu_fixed_t, "npc_last_t": ctx["npc_last"],
        })
    raw = load_raw()
    first = None
    for r in rows:
        if r.get("available"):
            res, _ = compute(r["species"])
            first = (res.years_hist[-1], res.years_fc[0], res.years_fc[-1])
            break
    return {"rows": rows, "k": float(raw.get("k", 1.0)), "horizon": int(raw.get("horizon", 5)),
            "years": first, "scenario_titles": SCENARIO_TITLES}


def excel() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        summ = summary_payload()
        srows = []
        for r in summ["rows"]:
            if not r.get("available"):
                srows.append({"вид": r["species"], "примечание": "нет нового расчёта байесовской модели"})
                continue
            p = r["pdu_next_t"]
            row = {"вид": r["species"], "численность, последний год истории, шт": r["total_last"],
                   "промысловая биомасса, т": r["fishable_last_t"],
                   "ПДУ F = k·M, первый год прогноза, т (медиана)": p[2],
                   "ПДУ F = k·M, 2,5 %": p[0], "ПДУ F = k·M, 97,5 %": p[4], "F": r["F_next"],
                   "ПДУ НПЦ последнего года, т": r["npc_last_t"], "фиксированный ПДУ, т": r["pdu_fixed_t"]}
            for sc in SCENARIOS:
                row[f"численность в конце прогноза: {SCENARIO_TITLES[sc]}"] = r["total_end"][sc]
                row[f"вероятность снижения: {SCENARIO_TITLES[sc]}"] = r["p_decline"][sc]
            srows.append(row)
        pd.DataFrame(srows).to_excel(xw, sheet_name="Сводка", index=False)
        for sp in bc.DEFAULTS:
            res, ctx = compute(sp)
            if res is None:
                continue
            rows = []
            for sc in SCENARIOS:
                tq, bq, pq = q(res.total(sc)), q(res.fishable(sc)), q(res.pdu_tonnes(sc))
                rq = q(res.removal_tonnes(sc))
                for h, y in enumerate(res.years_fc):
                    row = {"сценарий": SCENARIO_TITLES[sc], "год": y,
                           "численность 1–2+, медиана": tq[2, h], "2,5 %": tq[0, h], "97,5 %": tq[4, h],
                           "промысловая биомасса, т": bq[2, h], "ПДУ, т": pq[2, h], "ПДУ 2,5 %": pq[0, h],
                           "ПДУ 97,5 %": pq[4, h], "изъятие β·ПДУ, т": rq[2, h],
                           "β": float(np.median(res.beta[:, h])),
                           "площадь, км²": res.areas_used[h],
                           "s половозрелых": float(np.median(res.s_mature[:, h])),
                           "s задана": res.mortality_used[h] is not None}
                    if sc == "baranov":
                        row["F"] = float(np.median(res.F[:, h]))
                        row["M̄"] = float(np.median(res.Mbar[:, h]))
                    med = np.median(res.catch[sc][:, h, :], axis=0)
                    for a, v in zip(res.ages, med):
                        if a >= res.m0:
                            row[f"ПДУ шт, {age_title(int(a))}"] = v
                    rows.append(row)
            pd.DataFrame(rows).to_excel(xw, sheet_name=sp[:31], index=False)
        from app.services_stock import _autowidth
        _autowidth(xw)
    return buf.getvalue()
