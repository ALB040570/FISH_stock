"""
Модель PyMC одного вида — сборка по настройкам SpeciesConfig.

Имена и порядок случайных величин те же, что в скриптах calc_stock_bayes_2g1p_*.py, поэтому при тех же
входных данных, настройках и seed выборка повторяет старый расчёт (режим сверки). Уравнения динамики —
общая функция dynamics.simulate.

PyMC импортируется только здесь и только при запуске расчёта.
"""
from __future__ import annotations

import numpy as np

from .config import SpeciesConfig
from .dynamics import pytensor_ops, simulate
from .inputs import BayesInputs


def build_model(inp: BayesInputs, cfg: SpeciesConfig):
    import pymc as pm
    import pytensor.tensor as pt

    c = inp.consts
    ages = np.arange(1, c.m1 + 1)
    orig_ages = np.arange(2, c.m1 + 1)
    n_obs_ages = len(orig_ages)
    coords = {"Year": inp.years, "age": ages, "Id": np.arange(len(inp.stock)),
              "age_observed": orig_ages, "age_observed_truncated": orig_ages[1:]}
    fec_m0_lower, fec_m0_upper, fec_m1_lower, fec_m1_upper = c.fec_limits(cfg)

    with pm.Model(coords=coords) as model:
        density_alpha = pm.LogNormal("density_alpha", mu=0.0, sigma=cfg.density_sigma, dims=("Year",))
        pm.Data("pdu_yearly_fish_pt", c.pdu)

        s_base = pm.LogNormal("s_base", mu=cfg.s_base_mu, sigma=cfg.s_base_sigma)
        s_juvenile_steep = pm.LogNormal("s_juvenile_steep", mu=cfg.s_juv_mu, sigma=cfg.s_juv_sigma)
        s_aging_slow = pm.LogNormal("s_aging_slow", mu=cfg.s_age_mu, sigma=cfg.s_age_sigma)
        s_year_fluct = pm.Normal("s_year_fluct", mu=0.0, sigma=cfg.s_year_sigma, dims=("Year",))
        press_base = pm.LogNormal("press_base", mu=cfg.press_mu, sigma=cfg.press_sigma, dims=("Year",))
        beta_1d = pm.TruncatedNormal("beta_1d", mu=cfg.beta_mu, sigma=cfg.beta_sigma,
                                     lower=cfg.beta_lower, upper=cfg.beta_upper, dims=("Year",))
        if cfg.unused_q_year_dev:
            pm.Normal("q_year_dev", mu=0.0, sigma=0.1, dims=("Year", "age"))
        q_raw = pm.Normal("q_raw", mu=0.0, sigma=cfg.q_sigma, dims=("age",))
        q_bias = pm.Deterministic("q_bias", pt.exp(q_raw), dims=("age",))
        egg_survival_base = pm.Beta("egg_survival_base", alpha=cfg.egg_alpha, beta=cfg.egg_beta)
        fec_at_m0 = pm.Uniform("fec_at_m0", lower=fec_m0_lower, upper=fec_m0_upper)
        fec_at_m1 = pm.Uniform("fec_at_m1", lower=fec_m1_lower, upper=fec_m1_upper)
        X_initial_older_raw = pm.LogNormal("X_initial_older_raw", mu=np.log(c.x0), sigma=cfg.x0_sigma,
                                           dims=("age_observed",))

        params = {"density_alpha": density_alpha, "s_base": s_base, "s_juvenile_steep": s_juvenile_steep,
                  "s_aging_slow": s_aging_slow, "s_year_fluct": s_year_fluct, "press_base": press_base,
                  "beta_1d": beta_1d, "egg_survival_base": egg_survival_base, "fec_at_m0": fec_at_m0,
                  "fec_at_m1": fec_at_m1, "X_initial_older_raw": X_initial_older_raw}
        out = simulate(pytensor_ops(), params, c, cfg)

        pm.Deterministic("s", out["s"], dims=("Year", "age"))
        pm.Deterministic("press_raw", out["press_raw"], dims=("Year", "age"))
        pm.Deterministic("pred_press_cube", out["pred_press_cube"], dims=("Year", "age"))
        pm.Deterministic("beta", out["beta"], dims=("Year", "age"))
        pm.Deterministic("egg_survival", out["egg_survival"])
        pm.Deterministic("theta_dyn", out["theta_dyn"], dims=("age",))
        pm.Deterministic("X_initial_older", out["X_initial_older"], dims=("age_observed",))
        pm.Deterministic("X_initial", out["X_initial"], dims=("age",))
        X_estimated = pm.Deterministic("X_estimated", out["X_estimated"], dims=("Year", "age"))

        # --- наблюдения: оценки запаса по ловам сети и невода ---
        obs_indices_pt = pt.constant(np.arange(1, n_obs_ages + 1), dtype="int64")
        X_estimated_obs = X_estimated.take(obs_indices_pt, axis=1)          # возрасты 2..m1
        idx_joint_pt = pt.constant(inp.year_idx, dtype="int64")
        X_at_date_joint = X_estimated_obs.take(idx_joint_pt, axis=0)       # (ловы, возрасты 2..m1)
        if cfg.likelihood_from == 2:
            expected_stock_joint = X_at_date_joint * q_bias[1:]
            observed, dims = inp.stock, ("Id", "age_observed")
        else:
            expected_stock_joint = X_at_date_joint[:, 1:] * q_bias[2:]
            observed, dims = inp.stock[..., 1:], ("Id", "age_observed_truncated")

        if cfg.mu_floor == "max":
            mu_stock_joint_safe = pt.maximum(expected_stock_joint, 10)
        else:
            mu_stock_joint_safe = pm.math.softplus(expected_stock_joint - 10.0) + 10.0
        mu_stock_joint = pt.log(mu_stock_joint_safe)

        sigma_stock = pm.HalfNormal("sigma_stock", sigma=cfg.sigma_stock_sd)
        pm.LogNormal("obs_stock_joint", mu=mu_stock_joint, sigma=sigma_stock, observed=observed, dims=dims)
    return model


def sample(model, cfg: SpeciesConfig, callback=None):
    """NUTS с настройками вида (как в скриптах: init="adapt_diag", seed, target_accept, max_treedepth)."""
    import pymc as pm

    kw = dict(draws=cfg.draws, tune=cfg.tune, random_seed=cfg.seed, init="adapt_diag",
              target_accept=cfg.target_accept, max_treedepth=cfg.max_treedepth, progressbar=False)
    if cfg.chains:
        kw["chains"] = cfg.chains
    if callback is not None:
        kw["callback"] = callback
    with model:
        return pm.sample(**kw)


# ---------------------------------------------------------------- извлечение результатов


KEEP_VARS = ("density_alpha", "s_base", "s_juvenile_steep", "s_aging_slow", "s_year_fluct", "press_base",
             "beta_1d", "q_raw", "q_bias", "egg_survival_base", "egg_survival", "fec_at_m0", "fec_at_m1",
             "X_initial_older_raw", "sigma_stock", "s", "pred_press_cube", "beta", "theta_dyn", "X_estimated")


def _group(idata, name):
    """Группа результатов как xarray.Dataset: InferenceData (arviz < 1) или DataTree (arviz ≥ 1)."""
    grp = getattr(idata, name, None)
    if grp is None:
        grp = idata[name]
    return grp.to_dataset() if hasattr(grp, "to_dataset") else grp


def extract_draws(idata) -> tuple[dict, dict]:
    """Массивы (цепь, выборка, …) нужных величин и статистика выборки."""
    post = _group(idata, "posterior")
    draws = {k: np.asarray(post[k].values, float) for k in KEEP_VARS if k in post.data_vars}
    stats = {}
    try:
        ss = _group(idata, "sample_stats")
        div = np.asarray(ss["diverging"].values, bool)
        stats["divergences"] = int(div.sum())
        stats["divergences_by_chain"] = div.sum(axis=1).astype(int).tolist()
        if "reached_max_treedepth" in ss.data_vars:
            stats["treedepth_hits"] = int(np.asarray(ss["reached_max_treedepth"].values, bool).sum())
        if "step_size" in ss.data_vars:
            stats["step_size"] = float(np.nanmean(ss["step_size"].values))
        if "acceptance_rate" in ss.data_vars:
            stats["acceptance_rate"] = float(np.nanmean(ss["acceptance_rate"].values))
    except Exception as e:  # noqa: BLE001 — статистика не обязательна
        stats["stats_error"] = str(e)
    return draws, stats
