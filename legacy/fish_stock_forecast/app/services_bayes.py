"""
Этап 4 для веб-интерфейса: настройки байесовской модели, запуск расчёта, результаты.

Результаты читаются из results/zhaysan_bayes_{вид}[_check|_prior].npz (numpy, без PyMC и xarray).
Старые результаты data_stock/zhaysan_bayes_2g1p_*.nc читаются через xarray, если он установлен.
"""
from __future__ import annotations

import io
import threading
from dataclasses import asdict
from functools import lru_cache

import numpy as np
import pandas as pd

from core import config
from core.ages import age_title
from core.bayes import config as bc
from core.bayes import run as R
from app import jobs

_lock = threading.RLock()
SOURCES = ("new", "check", "prior")


def _j(a, digits: int = 6):
    """numpy → JSON: вложенные списки, NaN/inf → None, округление до значащих цифр."""
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


def _total(cube: np.ndarray) -> np.ndarray:
    """(годы, возрасты) → (годы,): сумма без NaN; NaN, если все NaN."""
    all_nan = np.isnan(cube).all(axis=1)
    return np.where(all_nan, np.nan, np.nansum(cube, axis=1))


# ---------------------------------------------------------------- настройки и обзор


def _result_info(species: str, source: str) -> dict | None:
    path = R.result_path(species, source)
    loaded = _load(str(path), path.stat().st_mtime if path.exists() else 0)
    if loaded is None:
        return None
    arrays, meta = loaded
    tq = arrays["total_obs_q"]
    return {"finished": meta.get("finished"), "seconds": meta.get("seconds"), "divergences": meta.get("divergences"),
            "rhat_X_max": meta.get("rhat_X_max"), "chains": meta.get("chains"),
            "draws_per_chain": meta.get("draws_per_chain"), "last_total": _j(tq[2, -1]),
            "config_changed": _config_changed(species, source, meta)}


def _config_changed(species: str, source: str, meta: dict) -> list[str]:
    if source == "check":
        return []
    used = meta.get("config", {})
    cur = asdict(bc.get_config(species))
    return [k for k in bc.EDITABLE if k in used and used[k] != cur.get(k)]


def overview() -> dict:
    species = {}
    for sp in bc.DEFAULTS:
        species[sp] = {
            "token": bc.TOKENS[sp],
            "defaults": asdict(bc.DEFAULTS[sp]),
            "current": asdict(bc.get_config(sp)),
            "overrides": bc.overrides(sp),
            "results": {s: _result_info(sp, s) for s in SOURCES},
            "old_file": R.old_result_path(sp).name,
            "old_available": R.old_result_path(sp).exists(),
        }
    return {"species_list": list(bc.DEFAULTS), "species": species, "schema": bc.schema_payload(),
            "source_titles": R.MODE_TITLES, "job": jobs.status(), "results_dir": str(config.RESULTS_DIR),
            "pymc": _pymc_version()}


@lru_cache(maxsize=1)
def _pymc_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pymc")
    except Exception:  # noqa: BLE001
        return None


def save_config(species: str, values: dict) -> dict:
    if species not in bc.DEFAULTS:
        raise KeyError(species)
    with _lock:
        cfg = bc.save_overrides(species, values)
    return {"current": asdict(cfg), "overrides": bc.overrides(species)}


def reset_config(species: str) -> dict:
    if species not in bc.DEFAULTS:
        raise KeyError(species)
    with _lock:
        cfg = bc.reset(species)
    return {"current": asdict(cfg), "overrides": {}}


# ---------------------------------------------------------------- запуск


def run_prior(species: str) -> dict:
    """Априорная проверка в процессе сервера (секунды)."""
    from app import services_stock
    from core.data_source import load_fish_props

    if species not in bc.DEFAULTS:
        raise KeyError(species)
    with _lock:
        res, _ = services_stock.get_stage2()
        pdu = services_stock.get_pdu()
        R.run(species, "prior", log=lambda *a: None, stage23=(res, pdu, load_fish_props()))
    return results_payload(species, "prior")


def start_job(species: list[str], mode: str) -> dict:
    species = [s for s in species if s in bc.DEFAULTS]
    if not species:
        raise ValueError("не выбран вид")
    if mode not in ("new", "check"):
        raise ValueError("режим должен быть new или check")
    return jobs.start(species, mode)


# ---------------------------------------------------------------- результаты


@lru_cache(maxsize=32)
def _load(path: str, mtime: float):
    from pathlib import Path
    return R.load_npz(Path(path)) if mtime else None


@lru_cache(maxsize=16)
def _old(path: str, mtime: float) -> dict | None:
    if not mtime:
        return None
    try:
        import xarray as xr
    except ImportError:
        return {"error": "для сравнения со старым расчётом нужен xarray"}
    try:
        with xr.open_dataset(path) as ds:
            ds = ds.load()
        out = {"years": [int(y) for y in ds["Year"].values], "ages": [int(a) for a in ds["age"].values]}
        for k in ("X_median", "X_q25", "X_q75", "s_median", "pred_press_median", "beta_median", "q_bias_median"):
            if k in ds:
                out[k] = np.asarray(ds[k].values, float)
        out["divergences"] = int(ds.attrs.get("total_divergences", -1))
        if "rhat_X" in ds:
            out["rhat_X_max"] = float(np.nanmax(ds["rhat_X"].values))
        return out
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _old_payload(species: str, years: list[int]) -> dict | None:
    """Старый расчёт из data_stock, приведённый к годам нового."""
    path = R.old_result_path(species)
    old = _old(str(path), path.stat().st_mtime if path.exists() else 0)
    if old is None:
        return None
    if "error" in old:
        return {"error": old["error"], "file": path.name}
    idx = [old["years"].index(y) if y in old["years"] else None for y in years]
    ages = old["ages"]
    older = [i for i, a in enumerate(ages) if a >= 2]

    def rows(cube):
        cube = np.asarray(cube, float)
        return np.array([cube[i] if i is not None else np.full(cube.shape[1:], np.nan) for i in idx])

    out = {"file": path.name, "ages": ages, "divergences": old.get("divergences"), "rhat_X_max": old.get("rhat_X_max")}
    for k in ("X_median", "s_median", "pred_press_median"):
        if k in old:
            out[k] = _j(rows(old[k]))
    for k, key in (("X_median", "total_median"), ("X_q25", "total_q25"), ("X_q75", "total_q75")):
        if k in old:
            out[key] = _j(rows(old[k][:, older].sum(axis=1)[:, None])[:, 0])
    if "beta_median" in old:
        b = old["beta_median"]
        out["beta"] = _j(rows(b[:, [1 if b.shape[1] > 1 else 0]])[:, 0])
    if "q_bias_median" in old:
        out["q_bias"] = _j(old["q_bias_median"])
    return out


def results_payload(species: str, source: str = "new") -> dict:
    if species not in bc.DEFAULTS:
        raise KeyError(species)
    if source not in SOURCES:
        raise KeyError(source)
    path = R.result_path(species, source)
    loaded = _load(str(path), path.stat().st_mtime if path.exists() else 0)
    base = {"species": species, "source": source, "source_title": R.MODE_TITLES[source], "file": path.name}
    if loaded is None:
        return {**base, "available": False}
    a, meta = loaded
    years = [int(y) for y in a["years"]]
    X_q = a["X_q"]
    obs_mean = a["obs_stock_mean"]
    deaths = {
        "natural": _j(a["dead_natural_pcs"].sum(axis=1)),
        "predators": _j(a["dead_predators_pcs"].sum(axis=1)),
        "catch": _j(np.nansum(a["pdu_raw"], axis=1)),
        "poaching": _j(a["dead_brac_pcs"].sum(axis=1)),
        "recruits": _j(X_q[2][:, 0]),
    }
    keep_meta = {k: meta.get(k) for k in (
        "mode", "mode_title", "started", "finished", "seconds", "chains", "draws_per_chain", "tune", "divergences",
        "divergences_by_chain", "treedepth_hits", "step_size", "acceptance_rate", "rhat_X_max", "numpy_check",
        "notes", "n_obs", "dropped", "check_vs_old", "m0", "m1", "m2", "fec_bounds", "monotonic_violations",
        "cap_active_cells", "diagnostics")}
    return {
        **base, "available": True, "meta": keep_meta, "param_rows": meta.get("param_rows", []),
        "config_used": meta.get("config", {}), "config_changed": _config_changed(species, source, meta),
        "years": years, "model_ages": _j(a["model_ages"]), "obs_ages": _j(a["obs_ages"]),
        "quantiles": _j(a["quantiles"]),
        "total_obs_q": _j(a["total_obs_q"]), "total_all_q": _j(a["total_all_q"]),
        "X_q": _j(X_q), "s_q": _j(a["s_q"]), "pred_q": _j(a["pred_q"]), "beta1d_q": _j(a["beta1d_q"]),
        "q_bias_q": _j(a["q_bias_q"]), "theta_q": _j(a["theta_q"]), "density_alpha_q": _j(a["density_alpha_q"]),
        "rhat_X": _j(a["rhat_X"]) if "rhat_X" in a else None,
        "cap_active_frac": _j(a["cap_active_frac"]) if "cap_active_frac" in a else None,
        "deaths": deaths,
        "data": {
            "final_by_age": _j(a["yearly_final"]), "net_by_age": _j(a["yearly_net"]),
            "seine_by_age": _j(a["yearly_seine"]),
            "final_total": _j(_total(a["yearly_final"])), "net_total": _j(_total(a["yearly_net"])),
            "seine_total": _j(_total(a["yearly_seine"])), "npc_total": _j(a["npc_total"]),
            "obs_mean_net": _j(obs_mean[0]), "obs_mean_seine": _j(obs_mean[1]),
            "pdu_by_age": _j(a["pdu_raw"]), "x0": _j(a["x0"]),
        },
        "old": _old_payload(species, years) if source != "prior" else None,
    }


# ---------------------------------------------------------------- Excel


def results_excel(species: str, source: str = "new") -> bytes:
    path = R.result_path(species, source)
    loaded = R.load_npz(path)
    if loaded is None:
        raise FileNotFoundError(path.name)
    a, meta = loaded
    years = [int(y) for y in a["years"]]
    ages = [int(v) for v in a["model_ages"]]
    qn = ["2,5 %", "25 %", "медиана", "75 %", "97,5 %"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        rows = []
        for yi, y in enumerate(years):
            r = {"год": y}
            for k, n in enumerate(qn):
                r[f"возрасты 1–2 и старше, {n}"] = a["total_obs_q"][k, yi]
            for k, n in enumerate(qn):
                r[f"все возрасты, {n}"] = a["total_all_q"][k, yi]
            r["окончательный запас по уловам"] = _total(a["yearly_final"])[yi]
            r["оценка НПЦ"] = a["npc_total"][yi]
            rows.append(r)
        pd.DataFrame(rows).to_excel(xw, sheet_name="Численность по годам", index=False)
        for k, n in ((2, "Медиана по возрастам"), (0, "2,5 % по возрастам"), (4, "97,5 % по возрастам")):
            df = pd.DataFrame(a["X_q"][k], index=years, columns=[age_title(j) for j in ages])
            df.index.name = "год"
            df.to_excel(xw, sheet_name=n)
        df = pd.DataFrame(a["s_q"][2], index=years, columns=[age_title(j) for j in ages]); df.index.name = "год"
        df.to_excel(xw, sheet_name="Смертность s (медиана)")
        df = pd.DataFrame(a["pred_q"][2], index=years, columns=[age_title(j) for j in ages]); df.index.name = "год"
        df.to_excel(xw, sheet_name="Хищники (медиана)")
        prow = []
        for r in meta.get("param_rows", []):
            q = r["q"]
            prow.append({"параметр": r["label"], "индекс": r["index"], "2,5 %": q[0], "25 %": q[1], "медиана": q[2],
                         "75 %": q[3], "97,5 %": q[4], "R-hat": r["rhat"]})
        pd.DataFrame(prow).to_excel(xw, sheet_name="Параметры", index=False)
        pd.DataFrame({"год": years, "естественная гибель": a["dead_natural_pcs"].sum(axis=1),
                      "хищники": a["dead_predators_pcs"].sum(axis=1), "ПДУ": np.nansum(a["pdu_raw"], axis=1),
                      "браконьерство (β − 1)·ПДУ": a["dead_brac_pcs"].sum(axis=1),
                      "пополнение (0–1 год)": a["X_q"][2][:, 0]}).to_excel(xw, sheet_name="Баланс гибели", index=False)
        info = {k: meta.get(k) for k in ("mode_title", "started", "finished", "seconds", "chains", "draws_per_chain",
                                         "tune", "divergences", "rhat_X_max", "numpy_check", "n_obs", "dropped")}
        info.update({f"настройка: {k}": v for k, v in meta.get("config", {}).items()})
        pd.DataFrame({"показатель": list(info), "значение": [str(v) for v in info.values()]}).to_excel(
            xw, sheet_name="Расчёт", index=False)
        from app.services_stock import _autowidth
        _autowidth(xw)
    return buf.getvalue()

