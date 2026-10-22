"""
Проверки модели для ответа рецензентам (вызываются из scripts.run_bayes, режимы retro / prior_sens / pad /
recovery). Каждая проверка — полный расчёт NUTS (run) с изменёнными данными или настройками; результаты пишутся
в results/<вид>/<проверка>/ (вид — латинское имя: lesh, sudak, …).

    retro       — ретроспективная проверка: модель по годам ≤ year_max (по умолчанию 2021), прогноз оценок
                  по ловам следующих лет (2022–2024) теми же уравнениями; RMSE и MAE на лог-шкале,
                  покрытие 95 %-м интервалом прогноза;
    prior_sens  — чувствительность к априорным распределениям: σ смертности (s_base, s_juv, s_age, s_year)
                  и σ β увеличены в factor раз (по умолчанию 2); сравнение с основным расчётом;
    pad         — сравнение основного расчёта (дельта-логнормальное правдоподобие) с прежним логнормальным
                  правдоподобием с добавкой obs_pad к оценкам по ловам (0,1; 1; 10);
    recovery    — восстановление параметров: данные моделируются уравнениями модели и её моделью наблюдений
                  по известным параметрам (медианы основного расчёта, если он есть, иначе априорные медианы),
                  модель оценивается заново; доля истинных значений внутри 95 %-х интервалов.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from .. import config as app_config
from .config import TOKENS
from .dynamics import NumpyOps, expected_observations, mu_floor, prior_means, simulate, zero_log_lambda
from .inputs import build_inputs

YEAR_PARAMS = ("density_alpha", "s_year_fluct", "beta_1d")
MORTALITY_SIGMAS = ("s_base_sigma", "s_juv_sigma", "s_age_sigma", "s_year_sigma")


def analysis_dir(species: str, name: str, results_dir: Path | None = None) -> Path:
    d = Path(results_dir or app_config.RESULTS_DIR) / TOKENS[species] / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_csv(path: Path, rows: list[dict]) -> None:
    import pandas as pd

    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, data: dict) -> None:
    from .run import _json_default

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=_json_default), encoding="utf-8")


def _inputs(species: str, cfg, stage23):
    kw = dict(zip(("res", "pdu", "props"), stage23)) if stage23 is not None else {}
    return build_inputs(species, cfg, "new", **kw)


def _load_draws(path: Path) -> tuple[dict, dict, dict]:
    from .run import load_npz

    loaded = load_npz(path)
    if loaded is None:
        raise FileNotFoundError(path)
    arrays, meta = loaded
    return {k[5:]: v for k, v in arrays.items() if k.startswith("draw_")}, arrays, meta


def _year_param_prior(cfg, n: int, rng) -> dict:
    """Годовые параметры будущих лет — из априорных распределений."""
    from scipy.stats import truncnorm

    a = (cfg.beta_lower - cfg.beta_mu) / cfg.beta_sigma
    b = (cfg.beta_upper - cfg.beta_mu) / cfg.beta_sigma
    return {"density_alpha": rng.lognormal(0.0, cfg.density_sigma, n),
            "s_year_fluct": rng.normal(0.0, cfg.s_year_sigma, n),
            "beta_1d": truncnorm.rvs(a, b, loc=cfg.beta_mu, scale=cfg.beta_sigma, size=n, random_state=rng)}


def _total_compare(base: dict | None, other: dict, label: str, years) -> list[dict]:
    """Сравнение суммарной численности (возрасты 2..m1) по годам: медиана и ширина 95 %-го интервала."""
    rows = []
    for i, y in enumerate(years):
        r = {"variant": label, "year": int(y), "median": float(other["total_obs_q"][2, i]),
             "q025": float(other["total_obs_q"][0, i]), "q975": float(other["total_obs_q"][4, i])}
        if base is not None and i < base["total_obs_q"].shape[1]:
            bm = float(base["total_obs_q"][2, i])
            bw = float(base["total_obs_q"][4, i] - base["total_obs_q"][0, i])
            r["median_base"] = bm
            r["median_ratio"] = r["median"] / bm if bm else np.nan
            r["width_ratio"] = (r["q975"] - r["q025"]) / bw if bw else np.nan
        rows.append(r)
    return rows


def _base_arrays(species: str, results_dir: Path | None):
    from .run import load_npz, result_path

    loaded = load_npz(result_path(species, "new", "npz", results_dir))
    return None if loaded is None else loaded[0]


# ---------------------------------------------------------------- C1: ретроспективная проверка


def retro(species: str, year_max: int = 2021, stage23=None, results_dir: Path | None = None,
          cfg_changes: dict | None = None, log=print, plots: bool = True, seed: int = 0) -> dict:
    """Оценка по годам ≤ year_max, прогноз оценок по ловам следующих лет; метрики на лог-шкале."""
    from .run import mode_config, result_path, run

    cfg = replace(mode_config(species, "new"), **(cfg_changes or {}))
    out_dir = analysis_dir(species, "retro", results_dir)
    full = _inputs(species, cfg, stage23)
    tag = f"_retro{year_max}"
    meta = run(species, "new", log=log, results_dir=out_dir, cfg_changes=cfg_changes, inputs=full,
               year_max=year_max, tag=tag, plots=plots)
    draws, _, _ = _load_draws(result_path(species, "new", "npz", out_dir, tag))
    return {"run": meta, **retro_forecast(full, draws, cfg, year_max, out_dir, seed)}


def retro_metrics(species: str, year_max: int = 2021, stage23=None, results_dir: Path | None = None,
                  seed: int = 0) -> dict:
    """Пересчитать метрики ретроспективы по уже сохранённым выборкам (без MCMC)."""
    from .run import mode_config, result_path

    cfg = mode_config(species, "new")
    out_dir = analysis_dir(species, "retro", results_dir)
    full = _inputs(species, cfg, stage23)
    draws, _, _ = _load_draws(result_path(species, "new", "npz", out_dir, f"_retro{year_max}"))
    return retro_forecast(full, draws, cfg, year_max, out_dir, seed)


def retro_forecast(full, draws: dict, cfg, year_max: int, out_dir: Path, seed: int = 0) -> dict:
    """Прогноз оценок по ловам лет > year_max по выборкам, оценённым на годах ≤ year_max."""
    rng = np.random.default_rng(seed)
    c = full.consts
    n_fit = sum(1 for y in full.years if y <= year_max)
    n_fc = c.n_years - n_fit
    ho = full.year_idx >= n_fit
    if n_fc <= 0 or not ho.any():
        raise ValueError(f"после {year_max} года нет данных для проверки")
    D = len(draws["s_base"])
    delta = cfg.likelihood == "delta" and "zero_c" in draws
    ref = full.log_ref(cfg)
    gear_ho = np.asarray(full.gear[ho], int)
    preds, conds, p0_share = [], [], []
    for i in range(D):
        p = {k: draws[k][i] for k in ("s_base", "s_juvenile_steep", "s_aging_slow", "egg_survival_base",
                                       "fec_at_m0", "fec_at_m1", "X_initial_older_raw")}
        fut = _year_param_prior(cfg, n_fc, rng)
        for k in YEAR_PARAMS:
            p[k] = np.concatenate([draws[k][i][:n_fit], fut[k]])
        X = simulate(NumpyOps, p, c, cfg)["X_estimated"]
        lq = float(draws["log_q_net"][i]) if "log_q_net" in draws else 0.0
        exp_, sl = expected_observations(X, draws["q_bias"][i], full.year_idx[ho], cfg, full.gear[ho], lq)
        safe = mu_floor(NumpyOps, exp_, cfg)
        mu = np.log(safe)
        pr = np.log(draw_positive(rng, safe, float(draws["sigma_stock"][i]), cfg))
        conds.append(pr.copy())                               # при условии, что лов не пуст
        if delta:
            # дельта-логнормальное: лов пуст с вероятностью exp(−λ) — тогда оценка равна добавке obs_pad
            lam = np.exp(zero_log_lambda(np.log(safe.sum(axis=1)), gear_ho, np.asarray(draws["zero_c"][i], float),
                                         float(draws["zero_b"][i]), ref))
            p0 = np.exp(-lam)
            pr[rng.random(len(p0)) < p0] = np.log(cfg.obs_pad)
            p0_share.append(float(p0.mean()))
        preds.append(pr)
    # дельта-модель: непустые ловы сравниваются с логнормальной частью прогноза (при условии, что лов не пуст),
    # пустые — через долю пустых ловов; медиана смеси с нулями на лог-шкале смысла не имеет
    pred = np.stack(conds if delta else preds)                # (D, ловы, возрасты)
    obs = np.log(full.stock[ho][:, sl])
    med = np.median(pred, axis=0)
    lo, hi = np.quantile(pred, 0.025, axis=0), np.quantile(pred, 0.975, axis=0)
    nonzero = full.stock[ho][:, sl] > cfg.obs_pad * (1 + 1e-9)       # без нулевых уловов (только добавка)
    if delta:
        nonzero = nonzero & ~full.zero_mask[ho][:, None]

    def metrics(mask) -> dict:
        if not mask.any():
            return {"n": 0}
        e = (obs - med)[mask]
        inside = ((obs >= lo) & (obs <= hi))[mask]
        return {"n": int(mask.sum()), "rmse_log": float(np.sqrt(np.mean(e ** 2))), "mae_log": float(np.mean(np.abs(e))),
                "bias_log": float(np.mean(e)), "coverage95": float(np.mean(inside))}

    years_ho = np.asarray(full.year_idx[ho])
    gears = np.asarray(full.gear[ho])
    allm = nonzero if delta else np.ones_like(obs, bool)
    rows = [{"subset": "непустые ловы" if delta else "все", **metrics(allm)},
            {"subset": "без нулевых уловов", **metrics(nonzero)}]
    for t in sorted(set(years_ho.tolist())):
        rows.append({"subset": f"год {full.years[t]}", **metrics(allm & (years_ho == t)[:, None])})
    for g, name in ((0, "сеть"), (1, "невод")):
        rows.append({"subset": name, **metrics(allm & (gears == g)[:, None])})
    if p0_share:
        # доля пустых ловов в годах прогноза: наблюдённая и предсказанная (медиана и 95 % интервал)
        rows.append({"subset": "доля пустых ловов", "n": int(ho.sum()),
                     "zero_share_obs": float(full.zero_mask[ho].mean()),
                     "zero_share_pred": float(np.median(p0_share)),
                     "zero_share_q025": float(np.quantile(p0_share, 0.025)),
                     "zero_share_q975": float(np.quantile(p0_share, 0.975))})
    _write_csv(out_dir / f"retro{year_max}_metrics.csv", rows)
    ages = np.arange(2, c.m1 + 1)[sl]
    cells = []
    for k in range(obs.shape[0]):
        for j, a in enumerate(ages):
            cells.append({"year": full.years[years_ho[k]], "gear": "сеть" if gears[k] == 0 else "невод",
                          "age": int(a), "obs_log": obs[k, j], "pred_median_log": med[k, j], "pred_q025_log": lo[k, j],
                          "pred_q975_log": hi[k, j]})
    _write_csv(out_dir / f"retro{year_max}_hauls.csv", cells)
    res = {"year_max": year_max, "forecast_years": full.years[n_fit:], "metrics": rows}
    _write_json(out_dir / f"retro{year_max}.json", res)
    return res


# ---------------------------------------------------------------- C2: априорные распределения


def prior_sensitivity(species: str, factor: float = 2.0, stage23=None, results_dir: Path | None = None,
                      cfg_changes: dict | None = None, log=print, plots: bool = True) -> dict:
    """σ априорных распределений смертности и β × factor; сравнение с основным расчётом."""
    from .run import load_npz, mode_config, result_path, run

    cfg = replace(mode_config(species, "new"), **(cfg_changes or {}))
    changes = {k: getattr(cfg, k) * factor for k in MORTALITY_SIGMAS + ("beta_sigma",)}
    changes.update(cfg_changes or {})
    out_dir = analysis_dir(species, "sens_prior", results_dir)
    tag = f"_prior_x{factor:g}"
    meta = run(species, "new", log=log, results_dir=out_dir, stage23=stage23, cfg_changes=changes, tag=tag,
               plots=plots)
    arrays, m = load_npz(result_path(species, "new", "npz", out_dir, tag))
    base = _base_arrays(species, results_dir)
    rows = _total_compare(base, arrays, f"σ × {factor:g}", [int(y) for y in arrays["years"]])
    _write_csv(out_dir / f"compare{tag}.csv", rows)
    prow = [{"name": r["name"], "index": r["index"], "median": r["q"][2], "q025": r["q"][0], "q975": r["q"][4]}
            for r in m.get("param_rows", [])]
    _write_csv(out_dir / f"params{tag}.csv", prow)
    if base is None:
        log(f"  основного расчёта {species} нет — сравнение только с собственными интервалами")
    return {"run": meta, "changes": changes, "compare": rows}


# ---------------------------------------------------------------- C3: добавка к оценкам по ловам


def pad_sensitivity(species: str, pads=(0.1, 1.0, 10.0), stage23=None, results_dir: Path | None = None,
                    cfg_changes: dict | None = None, log=print, plots: bool = False) -> dict:
    """Расчёты с разными obs_pad и сравнение суммарной численности по годам."""
    from .run import load_npz, result_path, run

    out_dir = analysis_dir(species, "sens_pad", results_dir)
    base = _base_arrays(species, results_dir)
    rows, metas = [], {}
    for pad in pads:
        tag = f"_pad{pad:g}"
        ch = {**(cfg_changes or {}), "obs_pad": float(pad), "likelihood": "pad"}
        metas[pad] = run(species, "new", log=log, results_dir=out_dir, stage23=stage23, cfg_changes=ch, tag=tag,
                         plots=plots)
        arrays, _ = load_npz(result_path(species, "new", "npz", out_dir, tag))
        rows += _total_compare(base, arrays, f"obs_pad = {pad:g}", [int(y) for y in arrays["years"]])
    _write_csv(out_dir / "compare_pad.csv", rows)
    return {"runs": metas, "compare": rows}


# ---------------------------------------------------------------- восстановление параметров


def true_parameters(species: str, inp, cfg, results_dir: Path | None = None) -> tuple[dict, str]:
    """Истинные параметры: медианы выборок основного расчёта (если есть), иначе априорные медианы."""
    from .run import result_path

    path = result_path(species, "new", "npz", results_dir)
    try:
        draws, arrays, _ = _load_draws(path)
        if len(arrays["years"]) == inp.consts.n_years:
            p = {k: np.median(v, axis=0) for k, v in draws.items()}
            p.setdefault("log_q_net", 0.0)
            p.setdefault("zero_c", _empirical_zero_c(inp))
            p.setdefault("zero_b", 1.0)
            return p, f"медианы основного расчёта ({path.name})"
    except FileNotFoundError:
        pass
    p = prior_means(inp.consts, cfg)
    p.update({"q_bias": np.ones(inp.consts.m1), "sigma_stock": 0.5, "log_q_net": 0.0,
              "zero_c": _empirical_zero_c(inp), "zero_b": 1.0})
    return p, "априорные медианы"


def _empirical_zero_c(inp) -> np.ndarray:
    """c по орудиям из доли пустых ловов: p0 = exp(−e^c) ⇒ c = ln(−ln p0)."""
    out = np.zeros(2)
    for g in (0, 1):
        sel = np.asarray(inp.gear) == g
        share = float(inp.zero_mask[sel].mean()) if sel.any() else 0.5
        out[g] = np.log(-np.log(min(max(share, 0.01), 0.99)))
    return out


def draw_positive(rng, safe: np.ndarray, sigma: float, cfg) -> np.ndarray:
    """Ненулевые оценки по ловам при ожидании safe: логнормальные (σ — шум ln) или, у delta_pos = "gamma",
    гамма с коэффициентом вариации σ. Для "lognormal_total" — логнормальный множитель, общий для лова."""
    if cfg.likelihood == "delta" and cfg.delta_pos == "gamma":
        return rng.gamma(1.0 / sigma ** 2, safe * sigma ** 2)
    if cfg.likelihood == "delta" and cfg.delta_pos == "lognormal_total":
        return safe * np.exp(sigma * rng.standard_normal((safe.shape[0], 1)))
    return np.exp(np.log(safe) + sigma * rng.standard_normal(safe.shape))


def simulate_observations(inp, cfg, p: dict, seed: int = 0):
    """Синтетические оценки по ловам: та же схема ловов (годы, орудия), модель наблюдений модели."""
    rng = np.random.default_rng(seed)
    X = simulate(NumpyOps, p, inp.consts, cfg)["X_estimated"]
    exp_, sl = expected_observations(X, np.asarray(p["q_bias"]), inp.year_idx, cfg, inp.gear,
                                     float(p.get("log_q_net", 0.0)))
    safe = mu_floor(NumpyOps, exp_, cfg)
    mu = np.log(safe)
    stock = inp.stock.copy()
    if cfg.likelihood != "delta":
        stock[:, sl] = np.exp(mu + float(p["sigma_stock"]) * rng.standard_normal(mu.shape))
        return replace(inp, stock=stock, notes=inp.notes + ["синтетические данные (проверка восстановления)"]), X
    # дельта-логнормальное: лов пуст с вероятностью exp(−λ); ненулевые оценки — логнормальные + добавка obs_pad
    lam = np.exp(zero_log_lambda(np.log(safe.sum(axis=1)), np.asarray(inp.gear, int), np.asarray(p["zero_c"], float),
                                 float(p["zero_b"]), inp.log_ref(cfg)))
    zero = rng.random(len(lam)) < np.exp(-lam)
    stock[:, sl] = draw_positive(rng, safe, float(p["sigma_stock"]), cfg) + cfg.obs_pad
    stock[zero] = cfg.obs_pad
    return replace(inp, stock=stock, zero=zero, zero_ref=inp.log_ref(cfg),
                   notes=inp.notes + ["синтетические данные (проверка восстановления)"]), X


def recovery(species: str, stage23=None, results_dir: Path | None = None, cfg_changes: dict | None = None,
             log=print, plots: bool = False, seed: int = 0) -> dict:
    """Моделирование данных по известным параметрам, повторная оценка, покрытие истинных значений."""
    from .run import load_npz, mode_config, result_path, run

    cfg = replace(mode_config(species, "new"), **(cfg_changes or {}))
    out_dir = analysis_dir(species, "recovery", results_dir)
    inp = _inputs(species, cfg, stage23)
    truth, source = true_parameters(species, inp, cfg, results_dir)
    syn, X_true = simulate_observations(inp, cfg, truth, seed)
    log(f"  истинные параметры: {source}")
    tag = "_recovery"
    meta = run(species, "new", log=log, results_dir=out_dir, cfg_changes=cfg_changes, inputs=syn, tag=tag,
               plots=plots)
    arrays, m = load_npz(result_path(species, "new", "npz", out_dir, tag))
    X_q = arrays["X_q"]
    inside = (X_true >= X_q[0]) & (X_true <= X_q[4])
    rows = [{"quantity": "X_estimated, все возрасты", "n": int(inside.size), "coverage95": float(inside.mean())},
            {"quantity": "X_estimated, возрасты 2..m1", "n": int(inside[:, 1:].size),
             "coverage95": float(inside[:, 1:].mean())}]
    prow = []
    for r in m.get("param_rows", []):
        name, idx = r["name"], r["index"]
        if name not in truth:
            continue
        tv = np.asarray(truth[name], float)
        if idx is None:
            val = float(tv)
        elif name in ("beta_1d", "density_alpha", "s_year_fluct"):
            val = float(tv[list(syn.years).index(idx)])
        elif name == "q_bias":
            val = float(tv[int(idx) - 1])
        elif name == "zero_c":
            val = float(tv[0 if idx == "сеть" else 1])
        else:
            continue
        prow.append({"name": name, "index": idx, "true": val, "median": r["q"][2], "q025": r["q"][0],
                     "q975": r["q"][4], "inside95": bool(r["q"][0] <= val <= r["q"][4])})
    if prow:
        rows.append({"quantity": "параметры", "n": len(prow), "coverage95": float(np.mean([r["inside95"] for r in prow]))})
    _write_csv(out_dir / "recovery_coverage.csv", rows)
    _write_csv(out_dir / "recovery_params.csv", prow)
    res = {"truth_source": source, "coverage": rows}
    _write_json(out_dir / "recovery.json", res)
    return {"run": meta, **res}
