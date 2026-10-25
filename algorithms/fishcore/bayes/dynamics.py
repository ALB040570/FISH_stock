"""
Уравнения когортной модели (16)-(17) статьи — общие для PyMC и numpy.

Одна функция simulate() строит динамику численности и в графе PyTensor (модель PyMC), и на numpy
(проверка, прогноз этапа 5). Порядок арифметических операций повторяет скрипты старого проекта,
чтобы расчёт в режиме сверки давал те же числа.

Возрасты модели j = 1..m1 (индекс 0 — сеголетки 0–1, индекс 1 — двухлетки 1–2 и т. д.).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SpeciesConfig


# ---------------------------------------------------------------- операции


class NumpyOps:
    exp = staticmethod(np.exp)
    log = staticmethod(np.log)
    tanh = staticmethod(np.tanh)
    maximum = staticmethod(np.maximum)
    where = staticmethod(np.where)
    clip = staticmethod(np.clip)

    @staticmethod
    def softplus(x):
        return np.logaddexp(0.0, x)

    @staticmethod
    def sum(x):
        return np.sum(x, axis=0)

    @staticmethod
    def row_max(x):
        return np.max(x, axis=1, keepdims=True)

    @staticmethod
    def vec1(x):
        return np.reshape(np.asarray(x, float), (1,))

    @staticmethod
    def concat(parts):
        return np.concatenate(parts, axis=0)

    @staticmethod
    def stack(parts):
        return np.stack(parts, axis=0)


def pytensor_ops():
    """Те же операции в PyTensor (импорт только на машине, где установлен PyMC)."""
    import pytensor.tensor as pt

    class PytensorOps:
        exp = staticmethod(pt.exp)
        log = staticmethod(pt.log)
        tanh = staticmethod(pt.tanh)
        maximum = staticmethod(pt.maximum)
        where = staticmethod(pt.where)
        clip = staticmethod(pt.clip)
        softplus = staticmethod(pt.softplus)

        @staticmethod
        def sum(x):
            return pt.sum(x, axis=0)

        @staticmethod
        def row_max(x):
            return pt.max(x, axis=1, keepdims=True)

        @staticmethod
        def vec1(x):
            return pt.as_tensor_variable(x).dimshuffle("x")

        @staticmethod
        def concat(parts):
            return pt.concatenate(parts, axis=0)

        @staticmethod
        def stack(parts):
            return pt.stack(parts, axis=0)

    return PytensorOps


# ---------------------------------------------------------------- константы вида


@dataclass
class Constants:
    """Неслучайные величины модели одного вида."""
    m0: int
    m1: int
    m2: int
    n_years: int
    eps: np.ndarray          # (m1,)  доля половозрелых ε_j = 1 / (1 + 4^(m0 − j)), j = 1..m1
    K: np.ndarray            # (годы,) ёмкость нерестилищ по мальку: S·0,1·норматив·10
    pdu: np.ndarray          # (годы, m1 − 1) ПДУ в штуках, возрасты 2..m1 (+0,1 и множитель)
    x0: np.ndarray           # (m1 − 1,) оценка начального запаса, возрасты 2..m1
    fec_bounds: tuple        # (мин, макс) икринок на самку

    @property
    def n_ages(self) -> int:
        return self.m1

    def fec_limits(self, cfg: SpeciesConfig) -> tuple[float, float, float, float]:
        low, high = float(self.fec_bounds[0]), float(self.fec_bounds[1])
        rng = high - low
        return low, low + cfg.fec_m0_width * rng, high - cfg.fec_m1_width * rng, high


def maturity(m0: int, m1: int) -> np.ndarray:
    eps = np.zeros(m1)
    for j in range(m1):
        eps[j] = 1 / (1 + 4 ** (-(j + 1 - m0)))
    return eps


# ---------------------------------------------------------------- модель


PARAMS = ("density_alpha", "s_base", "s_juvenile_steep", "s_aging_slow", "s_year_fluct",
          "beta_1d", "egg_survival_base", "fec_at_m0", "fec_at_m1", "X_initial_older_raw")


def mortality_matrix(ops, p: dict, fluct, m0: int, m1: int, cfg: SpeciesConfig):
    """Естественная смертность s (строки — годы, столбцы — возрасты 1..m1): парабола с минимумом в m0 + 1,
    годовые колебания fluct, нормировка на теоретический максимум и обрезка."""
    n_ages = m1
    ages_grid_2d = np.arange(1, n_ages + 1)[None, :]
    optimal_age = m0 + 1.0
    age_distance = ages_grid_2d - optimal_age
    s_curve_left = p["s_base"] + (age_distance ** 2) * p["s_juvenile_steep"]
    s_curve_right = p["s_base"] + (age_distance ** 2) * p["s_aging_slow"]
    s_curve_raw = ops.where(age_distance < 0, s_curve_left, s_curve_right)
    s_raw_matrix = ops.exp(ops.log(s_curve_raw + 1e-6) + fluct[:, None])
    is_age_alive = ages_grid_2d <= m1
    s_at_age_1 = p["s_base"] + ((1.0 - optimal_age) ** 2) * p["s_juvenile_steep"]
    s_at_max_age = p["s_base"] + ((m1 - optimal_age) ** 2) * p["s_aging_slow"]
    theoretical_peak = ops.maximum(s_at_age_1, s_at_max_age)
    s_peak_scale = ops.exp(ops.log(theoretical_peak + 1e-6))
    s_normalized_raw = (s_raw_matrix / (s_peak_scale + 1e-6)) * cfg.s_norm
    s_final_normalized = ops.where(is_age_alive, s_normalized_raw, 0.0)
    if cfg.s_clip_mode == "peak_switch":
        s_if = ops.clip(s_final_normalized, cfg.s_clip_lo, cfg.s_clip_hi)
        s_else = ops.clip(s_raw_matrix, cfg.s_clip_lo, cfg.s_clip_hi)
        return ops.where(s_peak_scale >= 0.99, s_if, s_else)
    return ops.clip(s_final_normalized, cfg.s_clip_lo, cfg.s_clip_hi)


def predation_matrix(m2: int, n_ages: int, cfg: SpeciesConfig, n_years: int = 1) -> np.ndarray:
    """Давление хищников γ (годы × возрасты): γ_j = γ_max · χ(j ≤ m2) / j — постоянная, без параметров.

    Раньше γ = (b/j)·χ / (b + 10⁻⁶) · γ_max со случайным b = press_base по годам: b сокращается, поэтому
    b не определялся данными; новое γ отличается от прежнего лишь на 10⁻⁶/b (≈ 3·10⁻⁶ относительно)."""
    ages = np.arange(1, n_ages + 1)
    row = np.where(ages <= m2, 1.0, 0.0) / ages * cfg.press_max
    return np.repeat(row[None, :], n_years, axis=0)


def fecundity(ops, fec_at_m0, fec_at_m1, m0: int, m1: int, cfg: SpeciesConfig):
    """Плодовитость θ(j), j = 1..m1: линейно от θ(m0) до θ(m1)."""
    fec_slope = (fec_at_m1 - fec_at_m0) / (m1 - m0 + 1e-6)
    ages_vector = np.arange(1, m1 + 1)
    if cfg.theta_offset:
        theta_linear = fec_at_m0 + fec_slope * (ages_vector - m0 - cfg.theta_offset)
    else:
        theta_linear = fec_at_m0 + fec_slope * (ages_vector - m0)
    return ops.where(theta_linear > 0, theta_linear, 0.0) if cfg.theta_nonneg else theta_linear


def predator_mask(ops, m2: int, n_ages: int, cfg: SpeciesConfig):
    """h(j) для возрастов 3..m1 в знаменателе (17): плавная граница или ступенька в m2."""
    older_grid = np.arange(3, n_ages + 1)
    if cfg.h_mask_mode == "step":
        return np.where(older_grid <= m2, 1.0, 0.0)
    return 1.0 / (1.0 + ops.exp(5.0 * (older_grid - m2)))


def removal_ratio(X_prev, s_t1, beta_older, A_older):
    """Запрошенное изъятие β·A как доля выживших (1 − s)·X (+1 рыба), возрасты 2..m1 − 1 → 3..m1."""
    return (beta_older * A_older) / ((1.0 - s_t1[1:-1]) * X_prev[1:-1] + 1.0)


def step(ops, X_prev, s_t1, pp, beta_older, A_older, K_t, alpha_t, theta, eps, egg_survival, h_mask,
         cfg: SpeciesConfig):
    """Один год уравнений (16)-(17): численность года t по численности года t − 1.

    s_t1, pp — смертность и давление хищников года t (возрасты 1..m1);
    beta_older, A_older — β и вылов для возрастов 2..m1 − 1 (переходят в 3..m1);
    K_t · alpha_t — ёмкость нерестилищ. Возвращает (X_t, сеголетки X_1(t)).
    """
    # j = 1: пополнение от нерестового стада прошлого года
    if cfg.eggs_mode == "older_half":
        X_mature_prev = X_prev[1:] * eps[1:]
        raw_egg_pool = theta[1:] * 0.5 * X_mature_prev
    else:
        X_mature_prev = X_prev * eps
        raw_egg_pool = theta * X_mature_prev
    total_eggs_laid = ops.sum(raw_egg_pool)
    larvae_hatched = total_eggs_laid * egg_survival
    density_cap_t = K_t * alpha_t
    if cfg.density_softmin == "plain":
        effective_larvae = density_cap_t - ops.softplus(density_cap_t - larvae_hatched)
    else:
        diff = density_cap_t - larvae_hatched
        smooth_max = ops.softplus(diff / 100000.0) * 100000.0
        effective_larvae = density_cap_t - smooth_max
    larvae_survived_year = effective_larvae * ((1.0 - s_t1[0]) ** 2)
    X_j1_new = larvae_survived_year / (1.0 + pp[0])

    # j = 2
    numerator_j2 = (1.0 - s_t1[1]) * X_prev[0]
    X_j2_new = numerator_j2 / (1.0 + pp[1])

    # j = 3..m1: уравнение (17)
    X_prev_m1 = X_prev[1:-1]
    s_prev_m1 = s_t1[1:-1]
    beta_curr_older = beta_older
    A_curr_older = A_older
    if cfg.catch_mode == "cap":
        # плавный минимум из запрошенной доли и removal_cap: изъятие никогда не превышает cap·выживших
        available_pop = (1.0 - s_prev_m1) * X_prev_m1
        ratio = removal_ratio(X_prev, s_t1, beta_curr_older, A_curr_older)
        k = cfg.removal_sharp
        rate = cfg.removal_cap - ops.softplus(k * (cfg.removal_cap - ratio)) / k
        num_older = available_pop * (1.0 - rate)
    elif cfg.catch_mode == "max":
        num_older_raw = ((1.0 - s_prev_m1) * X_prev_m1) - (beta_curr_older * A_curr_older)
        num_older = ops.maximum(num_older_raw, 1)
    elif cfg.catch_mode == "softplus":
        survived_before_catch = X_prev_m1 * (1.0 - s_prev_m1)
        safe_denominator = 1000.0 + ops.softplus((survived_before_catch - 1000.0) / 100.0) * 100.0
        catch_rate_raw = (beta_curr_older * A_curr_older) / safe_denominator
        diff_catch = 0.95 - catch_rate_raw
        catch_rate_safe = 0.95 - ops.softplus(diff_catch * 10.0) / 10.0
        num_older_raw = survived_before_catch * (1.0 - catch_rate_safe)
        diff_num = num_older_raw - 1.3
        num_older = 1.3 + ops.softplus(diff_num * 2.0) / 2.0
    else:  # tanh
        available_pop = (1.0 - s_prev_m1) * X_prev_m1
        requested_catch = beta_curr_older * A_curr_older
        catch_ratio = requested_catch / (available_pop + 1.0)
        smooth_factor = ops.tanh(1.0 / (catch_ratio + 1e-5))
        num_older = available_pop - (smooth_factor * requested_catch)
    denominator_older = 1.0 + h_mask * pp[2:]
    X_older_new = num_older / denominator_older

    X_curr = ops.concat([ops.vec1(X_j1_new), ops.vec1(X_j2_new), X_older_new])
    if cfg.x_softplus:
        X_curr = ops.softplus(X_curr)
    return X_curr, X_j1_new


def simulate(ops, p: dict, c: Constants, cfg: SpeciesConfig) -> dict:
    """Динамика численности по уравнениям (16)-(17).

    p — параметры (имена как у случайных величин PyMC): density_alpha (годы), s_base, s_juvenile_steep,
    s_aging_slow, s_year_fluct (годы), beta_1d (годы), egg_survival_base, fec_at_m0,
    fec_at_m1, X_initial_older_raw (m1 − 1).
    Возвращает промежуточные величины с именами старых скриптов и removal_ratio (годы × возрасты) — запрошенное
    изъятие β·A как доля выживших (возрасты 3..m1, годы 2-й и далее; иначе 0): где > removal_cap, ограничение
    изъятия действует.
    """
    n_years, n_ages = c.n_years, c.n_ages
    m0, m1, m2 = c.m0, c.m1, c.m2
    ages_grid_2d = np.arange(1, n_ages + 1)[None, :]
    is_age_alive = ages_grid_2d <= m1

    s = mortality_matrix(ops, p, p["s_year_fluct"], m0, m1, cfg)
    pred = predation_matrix(m2, n_ages, cfg, n_years)
    beta = ops.where(is_age_alive, p["beta_1d"][:, None] + np.zeros((1, n_ages)), 0.0)
    theta = fecundity(ops, p["fec_at_m0"], p["fec_at_m1"], m0, m1, cfg)
    egg_survival = p["egg_survival_base"] * cfg.egg_scale
    eps = c.eps
    K = c.K
    density_alpha = p["density_alpha"]

    # --- начальный год ---
    x0 = c.x0
    X_initial_older = ops.clip(p["X_initial_older_raw"], x0 * cfg.x0_lo, x0 * cfg.x0_hi)
    X_mature_0 = X_initial_older * eps[1:]
    raw_egg_pool = theta[1:] * 0.5 * X_mature_0
    total_eggs_laid = ops.sum(raw_egg_pool)
    larvae_hatched = total_eggs_laid * egg_survival
    density_cap_0 = K[0] * density_alpha[0]
    diff = density_cap_0 - larvae_hatched
    smooth_max = ops.softplus(diff / 100000.0) * 100000.0
    effective_larvae = density_cap_0 - smooth_max
    larvae_survived = effective_larvae * ((1.0 - s[0, 0]) ** 2)
    X_j1_0 = larvae_survived / (1.0 + pred[0, 0])
    X_initial_raw = ops.concat([ops.vec1(X_j1_0), X_initial_older])
    smooth_mask = 1.0 / (1.0 + ops.exp(5.0 * (np.arange(1, n_ages + 1) - m1)))
    X_initial = X_initial_raw * smooth_mask

    h_mask = predator_mask(ops, m2, n_ages, cfg)
    X_list = [X_initial]
    ratio_list = [np.zeros(n_ages)]
    for t in range(1, n_years):
        X_curr, _ = step(ops, X_list[t - 1], s[t, :], pred[t, :], beta[t, 1:-1], c.pdu[t, :-1],
                         K[t], density_alpha[t], theta, eps, egg_survival, h_mask, cfg)
        ratio_list.append(ops.concat([np.zeros(2), removal_ratio(X_list[t - 1], s[t, :], beta[t, 1:-1],
                                                                 c.pdu[t, :-1])]))
        X_list.append(X_curr)

    return {
        "s": s, "pred_press_cube": pred, "beta": beta, "theta_dyn": theta,
        "egg_survival": egg_survival, "X_initial_older": X_initial_older, "X_initial": X_initial,
        "X_estimated": ops.stack(X_list), "removal_ratio": ops.stack(ratio_list),
    }


def expected_observations(X_estimated, q_bias, year_idx: np.ndarray, cfg: SpeciesConfig, gear=None,
                          log_q_net: float = 0.0):
    """Ожидаемые оценки запаса по ловам (numpy): X(год лова, возраст) · q(возраст) · q_net (только сеть).

    Возвращает (ожидание, срез столбцов наблюдений): возрасты likelihood_from..m1 (оценки по ловам хранятся
    для возрастов 2..m1). В модели PyMC то же самое записано в model.py.
    gear — орудие лова (0 — сеть, 1 — невод); без gear поправка сети не применяется.
    """
    obs = np.asarray(X_estimated)[:, 1:][year_idx]     # возрасты 2..m1
    if gear is not None and cfg.gear_effect and cfg.likelihood_gears == "both":
        obs = obs * np.exp(log_q_net * (np.asarray(gear) == 0))[:, None]
    k = cfg.likelihood_from - 2
    return obs[:, k:] * q_bias[k + 1:], slice(k, None)


def mu_floor(ops, expected, cfg: SpeciesConfig):
    if cfg.mu_floor == "max":
        return ops.maximum(expected, 10)
    return ops.softplus(expected - 10.0) + 10.0


def obs_slice(cfg: SpeciesConfig) -> slice:
    """Столбцы оценок по ловам (возрасты 2..m1), входящие в правдоподобие."""
    return slice(cfg.likelihood_from - 2, None)


def zero_log_ref(stock: np.ndarray, zero: np.ndarray, cfg: SpeciesConfig) -> float:
    """ln N̄ — средний логарифм суммы оценок по ненулевым ловам (точка отсчёта наклона b, константа данных)."""
    vals = np.asarray(stock)[~np.asarray(zero, bool)][:, obs_slice(cfg)] - cfg.obs_pad
    tot = np.maximum(vals.sum(axis=1), 1e-9)
    return float(np.mean(np.log(tot))) if len(tot) else 0.0


def zero_log_lambda(log_total, gear, zero_c, zero_b, log_ref: float):
    """ln λ_h = c_орудия + b · (ln N_h − ln N̄); вероятность пустого лова p0 = exp(−λ).

    log_total — ln суммы ожидаемых оценок лова по возрастам правдоподобия (с поправками уловистости).
    Работает и с numpy, и с pytensor (индексирование zero_c[gear]).
    """
    return zero_c[gear] + zero_b * (log_total - log_ref)


def log_likelihood_np(X_estimated, q_bias, sigma_stock, stock, year_idx, cfg, gear=None,
                      log_q_net: float = 0.0, zero=None, zero_c=None, zero_b: float = 1.0) -> float:
    """Правдоподобие оценок по ловам (numpy, для проверки): логнормальное с добавкой ("pad")
    или дельта-логнормальное ("delta": пустые ловы — exp(−λ), ненулевые — (1 − exp(−λ)) · логнормальное)."""
    exp_, sl = expected_observations(X_estimated, q_bias, year_idx, cfg, gear, log_q_net)
    safe = mu_floor(NumpyOps, exp_, cfg)
    mu = np.log(safe)
    y = np.asarray(stock)[:, sl]
    if cfg.likelihood != "delta":
        ly = np.log(y)
        return float(np.sum(-ly - np.log(sigma_stock) - 0.5 * np.log(2 * np.pi) - (ly - mu) ** 2 / (2 * sigma_stock ** 2)))
    zero = np.asarray(zero, bool)
    pos = ~zero
    yp = np.maximum(y[pos] - cfg.obs_pad, cfg.obs_pad)
    if cfg.delta_pos == "gamma":
        from scipy.special import gammaln
        a = 1.0 / sigma_stock ** 2
        rate = a / safe[pos]
        ll = np.sum(a * np.log(rate) - gammaln(a) + (a - 1) * np.log(yp) - rate * yp)
    else:
        if cfg.delta_pos == "lognormal_total":
            ly, m = np.log(yp.sum(axis=1)), np.log(safe[pos].sum(axis=1))
        else:
            ly, m = np.log(yp), mu[pos]
        ll = np.sum(-ly - np.log(sigma_stock) - 0.5 * np.log(2 * np.pi) - (ly - m) ** 2 / (2 * sigma_stock ** 2))
    g = np.zeros(len(y), int) if gear is None else np.asarray(gear, int)
    lam = np.exp(zero_log_lambda(np.log(safe.sum(axis=1)), g, np.asarray(zero_c, float), zero_b,
                                 zero_log_ref(stock, zero, cfg)))
    p_present = np.clip(-np.expm1(-lam), 1e-12, 1.0 - 1e-12)     # как в model.py
    ll += np.sum(np.log1p(-p_present[zero])) + np.sum(np.log(p_present[pos]))
    return float(ll)


def prior_means(c: Constants, cfg: SpeciesConfig) -> dict:
    """Параметры в медианах априорных распределений — для проверок и тестов."""
    low0, high0, low1, high1 = c.fec_limits(cfg)
    Y = c.n_years
    return {
        "density_alpha": np.ones(Y),
        "s_base": float(np.exp(cfg.s_base_mu)),
        "s_juvenile_steep": float(np.exp(cfg.s_juv_mu)),
        "s_aging_slow": float(np.exp(cfg.s_age_mu)),
        "s_year_fluct": np.zeros(Y),
        "beta_1d": np.full(Y, min(max(cfg.beta_mu, cfg.beta_lower), cfg.beta_upper)),
        "egg_survival_base": (cfg.egg_alpha - 1) / (cfg.egg_alpha + cfg.egg_beta - 2),
        "fec_at_m0": (low0 + high0) / 2,
        "fec_at_m1": (low1 + high1) / 2,
        "X_initial_older_raw": np.asarray(c.x0, float).copy(),
        "log_q_net": 0.0,
        "zero_c": np.zeros(2),
        "zero_b": float(cfg.zero_b_mu),
    }
