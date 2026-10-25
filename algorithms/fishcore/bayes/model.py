"""
Модель PyMC одного вида — сборка по настройкам SpeciesConfig.

Имена случайных величин те же, что в скриптах calc_stock_bayes_2g1p_*.py; параметр press_base исключён
(γ = γ_max / j — постоянная), добавлены ln q_net (поправка уловистости сети), дельта-логнормальное
правдоподобие (пустые ловы — отдельная вероятность exp(−λ)) и, по настройке, нецентрированная запись годовых
эффектов. Поэтому режим сверки повторяет старый расчёт приближённо, а не выборка в выборку.
Уравнения динамики — общая функция dynamics.simulate.

PyMC импортируется только здесь и только при запуске расчёта.
"""
from __future__ import annotations

import numpy as np

from .config import SpeciesConfig, uses_q_net
from .dynamics import pytensor_ops, simulate, zero_log_lambda
from .inputs import BayesInputs


def build_model(inp: BayesInputs, cfg: SpeciesConfig):
    import pymc as pm
    import pytensor.tensor as pt

    c = inp.consts
    ages = np.arange(1, c.m1 + 1)
    orig_ages = np.arange(2, c.m1 + 1)
    n_obs_ages = len(orig_ages)
    coords = {"Year": inp.years, "age": ages, "Id": np.arange(len(inp.stock)),
              "age_observed": orig_ages}
    fec_m0_lower, fec_m0_upper, fec_m1_lower, fec_m1_upper = c.fec_limits(cfg)

    with pm.Model(coords=coords) as model:
        density_alpha = pm.LogNormal("density_alpha", mu=0.0, sigma=cfg.density_sigma, dims=("Year",))
        pm.Data("pdu_yearly_fish_pt", c.pdu)

        s_base = pm.LogNormal("s_base", mu=cfg.s_base_mu, sigma=cfg.s_base_sigma)
        s_juvenile_steep = pm.LogNormal("s_juvenile_steep", mu=cfg.s_juv_mu, sigma=cfg.s_juv_sigma)
        s_aging_slow = pm.LogNormal("s_aging_slow", mu=cfg.s_age_mu, sigma=cfg.s_age_sigma)
        if cfg.noncentered:
            # нецентрированная запись: стандартные величины z и масштабирование (то же априорное распределение)
            s_year_fluct_z = pm.Normal("s_year_fluct_z", mu=0.0, sigma=1.0, dims=("Year",))
            s_year_fluct = pm.Deterministic("s_year_fluct", s_year_fluct_z * cfg.s_year_sigma, dims=("Year",))
            beta_1d_z = pm.TruncatedNormal("beta_1d_z", mu=0.0, sigma=1.0,
                                           lower=(cfg.beta_lower - cfg.beta_mu) / cfg.beta_sigma,
                                           upper=(cfg.beta_upper - cfg.beta_mu) / cfg.beta_sigma, dims=("Year",))
            beta_1d = pm.Deterministic("beta_1d", cfg.beta_mu + cfg.beta_sigma * beta_1d_z, dims=("Year",))
        else:
            s_year_fluct = pm.Normal("s_year_fluct", mu=0.0, sigma=cfg.s_year_sigma, dims=("Year",))
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
                  "s_aging_slow": s_aging_slow, "s_year_fluct": s_year_fluct,
                  "beta_1d": beta_1d, "egg_survival_base": egg_survival_base, "fec_at_m0": fec_at_m0,
                  "fec_at_m1": fec_at_m1, "X_initial_older_raw": X_initial_older_raw}
        out = simulate(pytensor_ops(), params, c, cfg)

        pm.Deterministic("s", out["s"], dims=("Year", "age"))
        pm.Deterministic("pred_press_cube", pt.as_tensor_variable(out["pred_press_cube"]), dims=("Year", "age"))
        pm.Deterministic("beta", out["beta"], dims=("Year", "age"))
        pm.Deterministic("egg_survival", out["egg_survival"])
        pm.Deterministic("theta_dyn", out["theta_dyn"], dims=("age",))
        pm.Deterministic("X_initial_older", out["X_initial_older"], dims=("age_observed",))
        pm.Deterministic("X_initial", out["X_initial"], dims=("age",))
        X_estimated = pm.Deterministic("X_estimated", out["X_estimated"], dims=("Year", "age"))
        pm.Deterministic("removal_ratio", out["removal_ratio"], dims=("Year", "age"))

        # --- наблюдения: оценки запаса по ловам сети и невода ---
        obs_indices_pt = pt.constant(np.arange(1, n_obs_ages + 1), dtype="int64")
        X_estimated_obs = X_estimated.take(obs_indices_pt, axis=1)          # возрасты 2..m1
        idx_joint_pt = pt.constant(inp.year_idx, dtype="int64")
        X_at_date_joint = X_estimated_obs.take(idx_joint_pt, axis=0)       # (ловы, возрасты 2..m1)
        if uses_q_net(cfg):
            # поправка уловистости сети: невод — опорное орудие, у ловов сети ожидание × q_net
            log_q_net = pm.Normal("log_q_net", mu=0.0, sigma=cfg.q_net_sigma)
            pm.Deterministic("q_net", pt.exp(log_q_net))
            is_net = pt.constant((np.asarray(inp.gear) == 0).astype("float64"))
            X_at_date_joint = X_at_date_joint * pt.exp(log_q_net * is_net)[:, None]
        k = cfg.likelihood_from - 2                      # первый столбец правдоподобия (оценки — возрасты 2..m1)
        model.add_coord("age_likelihood", orig_ages[k:])
        expected_stock_joint = X_at_date_joint[:, k:] * q_bias[k + 1:]
        observed, dims = inp.stock[..., k:], ("Id", "age_likelihood")

        if cfg.mu_floor == "max":
            mu_stock_joint_safe = pt.maximum(expected_stock_joint, 10)
        else:
            mu_stock_joint_safe = pm.math.softplus(expected_stock_joint - 10.0) + 10.0
        mu_stock_joint = pt.log(mu_stock_joint_safe)

        sigma_stock = pm.HalfNormal("sigma_stock", sigma=cfg.sigma_stock_sd)
        if cfg.likelihood != "delta":
            pm.LogNormal("obs_stock_joint", mu=mu_stock_joint, sigma=sigma_stock, observed=observed, dims=dims)
            return model

        # дельта-логнормальное правдоподобие:
        #   ненулевой лов h: Y_ha ~ LogNormal(ln μ_ha, σ) без добавки obs_pad, × P(лов не пуст) = 1 − exp(−λ_h);
        #   пустой лов (рыбы вида нет): P = exp(−λ_h); ln λ_h = c_орудия + b · (ln Σ_a μ_ha − ln N̄).
        zero = inp.zero_mask
        pos_idx = np.flatnonzero(~zero)
        model.add_coord("Id_pos", np.arange(len(pos_idx)))
        model.add_coord("gear", ["сеть", "невод"])
        obs_pos = np.maximum(observed[pos_idx] - cfg.obs_pad, cfg.obs_pad)
        if cfg.delta_pos == "gamma":
            # гамма с постоянным коэффициентом вариации sigma_stock: форма 1/σ², среднее μ
            shape = 1.0 / sigma_stock ** 2
            pm.Gamma("obs_stock_joint", alpha=shape, beta=shape / mu_stock_joint_safe[pos_idx], observed=obs_pos,
                     dims=("Id_pos", dims[1]))
        elif cfg.delta_pos == "lognormal_total":
            # сумма оценок лова по возрастам правдоподобия; возрастной состав задаёт модель
            pm.LogNormal("obs_stock_joint", mu=pt.log(mu_stock_joint_safe[pos_idx].sum(axis=1)), sigma=sigma_stock,
                         observed=obs_pos.sum(axis=1), dims=("Id_pos",))
        else:
            pm.LogNormal("obs_stock_joint", mu=mu_stock_joint[pos_idx], sigma=sigma_stock, observed=obs_pos,
                         dims=("Id_pos", dims[1]))
        zero_c = pm.Normal("zero_c", mu=0.0, sigma=cfg.zero_c_sigma, dims=("gear",))
        zero_b = pm.Normal("zero_b", mu=cfg.zero_b_mu, sigma=cfg.zero_b_sigma)
        log_lam = zero_log_lambda(pt.log(mu_stock_joint_safe.sum(axis=1)), pt.constant(np.asarray(inp.gear, "int64")),
                                  zero_c, zero_b, inp.log_ref(cfg))
        p_present = pt.clip(-pt.expm1(-pt.exp(log_lam)), 1e-12, 1.0 - 1e-12)
        pm.Bernoulli("obs_present", p=p_present, observed=(~zero).astype("int64"), dims=("Id",))
    return model


def sample(model, cfg: SpeciesConfig, callback=None):
    """NUTS с настройками вида (init — из настроек, в скриптах "adapt_diag"; seed, target_accept, max_treedepth)."""
    import pymc as pm

    kw = dict(draws=cfg.draws, tune=cfg.tune, random_seed=cfg.seed, init=cfg.init,
              target_accept=cfg.target_accept, max_treedepth=cfg.max_treedepth, progressbar=False)
    if cfg.init == "multistart":
        kw["init"] = "jitter+adapt_diag"
        kw["initvals"] = best_start(model, cfg)
    if cfg.chains:
        kw["chains"] = cfg.chains
    if callback is not None:
        kw["callback"] = callback
    with model:
        return pm.sample(**kw)


def best_start(model, cfg: SpeciesConfig) -> dict:
    """Максимум апостериорной плотности из cfg.init_starts случайных точек (find_MAP); возвращает лучшую точку.
    Нужен, когда у апостериорного распределения несколько мод и цепи из одной точки застревают в худшей."""
    import pymc as pm
    from pymc.initial_point import make_initial_point_fn

    logp = model.compile_logp()
    start_fn = make_initial_point_fn(model=model, jitter_rvs=set(model.free_RVs), return_transformed=True)
    best, best_lp = None, -np.inf
    for k in range(cfg.init_starts):
        with model:
            mp = pm.find_MAP(start=start_fn(cfg.seed + k), progressbar=False, include_transformed=True, maxeval=20000)
        point = {v.name: mp[v.name] for v in model.value_vars}
        lp = float(logp(point))
        if np.isfinite(lp) and lp > best_lp:
            best, best_lp = point, lp
    return best


def free_names(model) -> list[str]:
    """Имена свободных (оцениваемых) случайных величин модели — для диагностики."""
    return [rv.name for rv in model.free_RVs]


# ---------------------------------------------------------------- извлечение результатов


KEEP_VARS = ("density_alpha", "s_base", "s_juvenile_steep", "s_aging_slow", "s_year_fluct",
             "beta_1d", "q_raw", "q_bias", "log_q_net", "egg_survival_base", "egg_survival", "fec_at_m0", "fec_at_m1",
             "X_initial_older_raw", "sigma_stock", "zero_c", "zero_b", "s", "pred_press_cube", "beta", "theta_dyn", "X_estimated",
             "removal_ratio")


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
