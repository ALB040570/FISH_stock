"""
Этап 5: прогноз запаса на 1–10 лет и ПДУ.

Основа — 500 выборок параметров байесовской модели вида (results/zhaysan_bayes_{вид}.npz). Каждая выборка
продолжается теми же уравнениями (16)-(17) (core.bayes.dynamics.step) от численности последнего года.

Будущие годы (модель их не оценивала):
    s     — кривая смертности выборки; если на странице задан уровень смертности половозрелых L(t),
            кривая масштабируется так, что её среднее по возрастам j ≥ m0 равно L(t); иначе — годовое
            колебание N(0, σ) из настроек модели («из истории»);
    γ, α  — давление хищников и множитель ёмкости нерестилищ — случайный год 2015–2024 той же выборки;
    K     — ёмкость нерестилищ по площади водоёма, заданной на странице для каждого прогнозного года;
    β     — среднее за 3 предыдущих года (скользящее: с 4-го прогнозного года — по прогнозным годам);
    w     — средний вес по возрастам последнего года (недостающие — от младшего возраста, как на этапе 3).

Сценарии вылова A_j(t) (промысловые возрасты j ≥ m0):
    none     — без промысла;
    fixed    — фиксированный ПДУ, т, распределённый по возрастам алгоритмом этапа 3 по запасу на начало года;
    baranov  — F = k·M:  M_j = −ln((1 − s_j)/(1 + γ_j)),  F = k·M̄ (M̄ — средняя M промысловых возрастов,
               взвешенная по численности),  C_j = F/(F + M_j)·(1 − e^(−(F+M_j)))·X_j(t−1).
ПДУ года t считается по запасу на начало года X(t−1); фактическое изъятие β·A вычитается в (17).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields

import numpy as np

from .bayes.config import SpeciesConfig
from .bayes.dynamics import (NumpyOps, fecundity, maturity, mortality_matrix, predation_matrix, predator_mask,
                             step)
from .pdu_npc import distribute_pdu

SCENARIOS = ("baranov", "fixed", "none")
SCENARIO_TITLES = {"baranov": "F = k·M", "fixed": "фиксированный ПДУ", "none": "без промысла"}
QUANTILES = (0.025, 0.25, 0.5, 0.75, 0.975)
MAX_HORIZON = 10


@dataclass
class ForecastSettings:
    horizon: int = 5
    k: float = 1.0
    areas: dict = field(default_factory=dict)       # год → площадь водоёма, км²
    mortality: dict = field(default_factory=dict)   # год → уровень s половозрелых (доля за год) или None
    pdu_t: float | None = None                      # фиксированный ПДУ, т (None — ПДУ НПЦ последнего года)
    seed: int = 42


@dataclass
class Posterior:
    """Выборки байесовской модели одного вида (из .npz этапа 4)."""
    species: str
    years: list[int]
    m0: int
    m1: int
    m2: int
    cfg: SpeciesConfig
    draws: dict                  # имя → (D, …)
    X_q: np.ndarray              # (5, годы, возрасты) — квантили по всем выборкам NUTS
    total_obs_q: np.ndarray      # (5, годы)
    finished: str | None = None

    @property
    def n_draws(self) -> int:
        return len(self.draws["X_estimated"])

    @property
    def ages(self) -> np.ndarray:
        return np.arange(1, self.m1 + 1)


def posterior_from_npz(arrays: dict, meta: dict) -> Posterior:
    names = {f.name for f in fields(SpeciesConfig)}
    cfg = SpeciesConfig(**{k: v for k, v in meta.get("config", {}).items() if k in names})
    draws = {k[5:]: v for k, v in arrays.items() if k.startswith("draw_")}
    return Posterior(species=meta["species"], years=[int(y) for y in arrays["years"]], m0=int(meta["m0"]),
                     m1=int(meta["m1"]), m2=int(meta["m2"]), cfg=cfg, draws=draws, X_q=arrays["X_q"],
                     total_obs_q=arrays["total_obs_q"], finished=meta.get("finished"))


@dataclass
class ForecastResult:
    species: str
    years_hist: list[int]
    years_fc: list[int]
    ages: np.ndarray
    m0: int
    weights: np.ndarray                 # (возрасты,) г — последнего года
    weights_hist: np.ndarray            # (годы, возрасты)
    settings: ForecastSettings
    areas_used: list[float]
    area_default_years: list[int]       # годы, для которых площадь не задана и взята последняя известная
    mortality_used: list                # уровень s по годам или None («из истории»)
    pdu_fixed_t: float
    # история (выборки, D × годы)
    hist_total: np.ndarray              # (D, годы) численность 1–2+
    hist_biomass: np.ndarray            # (D, годы) биомасса 1–2+, т
    hist_fishable: np.ndarray           # (D, годы) промысловая биомасса j ≥ m0, т
    # прогноз по сценариям: имя → массивы (D, H, …)
    X: dict = field(default_factory=dict)          # (D, H, возрасты)
    catch: dict = field(default_factory=dict)      # (D, H, возрасты) ПДУ, штук
    beta: np.ndarray | None = None                 # (D, H)
    F: np.ndarray | None = None                    # (D, H) сценарий baranov
    Mbar: np.ndarray | None = None                 # (D, H)
    s_mature: np.ndarray | None = None             # (D, H) средняя s половозрелых
    notes: list = field(default_factory=list)

    # ---- производные величины (D, H)
    def total(self, sc: str) -> np.ndarray:
        return self.X[sc][:, :, 1:].sum(axis=2)

    def biomass(self, sc: str) -> np.ndarray:
        return (self.X[sc][:, :, 1:] * self.weights[1:]).sum(axis=2) / 1e6

    def fishable(self, sc: str) -> np.ndarray:
        m = self.ages >= self.m0
        return (self.X[sc][:, :, m] * self.weights[m]).sum(axis=2) / 1e6

    def pdu_tonnes(self, sc: str) -> np.ndarray:
        return (self.catch[sc] * self.weights).sum(axis=2) / 1e6

    def removal_tonnes(self, sc: str) -> np.ndarray:
        return self.pdu_tonnes(sc) * self.beta

    def p_decline(self, sc: str) -> float:
        """Доля траекторий, в которых численность 1–2+ в последний прогнозный год ниже последнего года истории."""
        return float(np.mean(self.total(sc)[:, -1] < self.hist_total[:, -1]))


def q(a: np.ndarray, axis: int = 0) -> np.ndarray:
    return np.quantile(a, QUANTILES, axis=axis)


# ---------------------------------------------------------------- вспомогательные формулы


def scale_mortality(s_row: np.ndarray, level: float, ages: np.ndarray, m0: int, cfg: SpeciesConfig) -> np.ndarray:
    """Кривая s с тем же профилем по возрастам, среднее по возрастам j ≥ m0 равно level."""
    mature = ages >= m0
    mean = float(np.mean(s_row[mature]))
    factor = level / mean if mean > 0 else 1.0
    return np.clip(s_row * factor, cfg.s_clip_lo, cfg.s_clip_hi)


def next_age_predation(pp: np.ndarray, h_mask: np.ndarray) -> np.ndarray:
    """γ, действующий на когорту возраста j в течение года (как в (17)): j = 1 → γ₂, j ≥ 2 → h(j+1)·γ_{j+1},
    последний возраст — 0 (в следующий год не переходит)."""
    A = len(pp)
    g = np.zeros(A)
    if A > 1:
        g[0] = pp[1]
    for i in range(1, A - 1):
        g[i] = h_mask[i - 1] * pp[i + 1]
    return g


def baranov_catch(X_prev: np.ndarray, s_row: np.ndarray, gamma_row: np.ndarray, fishable: np.ndarray,
                  k: float) -> tuple[np.ndarray, float, float]:
    """Вылов по уравнению Баранова при F = k·M̄. Возвращает (C_j, F, M̄)."""
    surv = np.clip((1.0 - s_row) / (1.0 + gamma_row), 1e-12, 1.0)
    M = -np.log(surv)
    Xf = np.where(fishable, np.maximum(X_prev, 0.0), 0.0)
    Mbar = float((M * Xf).sum() / Xf.sum()) if Xf.sum() > 0 else float(M[fishable].mean())
    F = k * Mbar
    Z = F + M
    frac = np.where(Z > 0, F / np.where(Z > 0, Z, 1.0) * (1.0 - np.exp(-Z)), 0.0)
    return np.where(fishable, frac * Xf, 0.0), F, Mbar


def rolling_beta(history: np.ndarray, horizon: int) -> np.ndarray:
    """β прогнозных лет: среднее за 3 предыдущих года (включая уже спрогнозированные)."""
    seq = list(np.asarray(history, float)[-3:])
    out = []
    for _ in range(horizon):
        b = float(np.mean(seq[-3:]))
        out.append(b)
        seq.append(b)
    return np.array(out)


# ---------------------------------------------------------------- прогноз


def run_forecast(post: Posterior, settings: ForecastSettings, weights_hist: np.ndarray, weights_last: np.ndarray,
                 fry_density: float, area_last: float, pdu_npc_last_t: float) -> ForecastResult:
    """Прогноз по всем выборкам и сценариям.

    weights_hist — (годы, возрасты 1..m1) г; weights_last — (возрасты,) г; fry_density — норматив мальков;
    area_last — площадь последнего года истории (для незаданных лет); pdu_npc_last_t — ПДУ НПЦ последнего года.
    """
    cfg, ops = post.cfg, NumpyOps
    H = int(min(max(settings.horizon, 1), MAX_HORIZON))
    y_last = post.years[-1]
    years_fc = [y_last + h for h in range(1, H + 1)]
    ages = post.ages
    A = len(ages)
    m0, m1, m2 = post.m0, post.m1, post.m2
    fishable = ages >= m0
    D = post.n_draws
    d = post.draws
    rng = np.random.default_rng(settings.seed)

    notes = []
    areas, missing = [], []
    last_known = area_last
    for y in years_fc:
        v = settings.areas.get(y, settings.areas.get(str(y)))
        if v is None or not np.isfinite(float(v)) or float(v) <= 0:
            missing.append(y)
            areas.append(last_known)
        else:
            last_known = float(v)
            areas.append(last_known)
    if missing:
        notes.append("площадь водоёма не задана на " + ", ".join(map(str, missing))
                     + " — взята последняя известная")
    K = np.array(areas) * 1000000 * 0.10 * fry_density * 10

    mort = []
    for y in years_fc:
        v = settings.mortality.get(y, settings.mortality.get(str(y)))
        mort.append(None if v in (None, "") or not np.isfinite(float(v)) else float(v))
    pdu_fixed_t = float(settings.pdu_t) if settings.pdu_t not in (None, "") else float(pdu_npc_last_t)

    eps = maturity(m0, m1)
    h_mask = predator_mask(ops, m2, A, cfg)
    Y = len(post.years)

    # случайные величины — общие для всех сценариев, чтобы сценарии различались только выловом
    fluct = rng.normal(0.0, cfg.s_year_sigma, (D, H))
    idx_press = rng.integers(0, Y, (D, H))
    idx_alpha = rng.integers(0, Y, (D, H))

    Xh = d["X_estimated"]                                         # (D, Y, A)
    res = ForecastResult(
        species=post.species, years_hist=post.years, years_fc=years_fc, ages=ages, m0=m0,
        weights=weights_last, weights_hist=weights_hist, settings=settings, areas_used=areas,
        area_default_years=missing, mortality_used=mort, pdu_fixed_t=pdu_fixed_t,
        hist_total=Xh[:, :, 1:].sum(axis=2),
        hist_biomass=(Xh[:, :, 1:] * weights_hist[None, :, 1:]).sum(axis=2) / 1e6,
        hist_fishable=(Xh[:, :, fishable] * weights_hist[None, :, fishable]).sum(axis=2) / 1e6,
        notes=notes)

    beta = np.zeros((D, H))
    s_rows = np.zeros((D, H, A))
    pp_rows = np.zeros((D, H, A))
    alpha = np.zeros((D, H))
    theta = np.zeros((D, A))
    egg = np.zeros(D)
    for i in range(D):
        p = {k: d[k][i] for k in ("s_base", "s_juvenile_steep", "s_aging_slow")}
        s_hist_like = mortality_matrix(ops, p, fluct[i], m0, m1, cfg)          # (H, A) «из истории»
        s0 = mortality_matrix(ops, p, np.zeros(1), m0, m1, cfg)[0]             # кривая без колебаний
        for h in range(H):
            s_rows[i, h] = s_hist_like[h] if mort[h] is None else scale_mortality(s0, mort[h], ages, m0, cfg)
        _, pred = predation_matrix(ops, d["press_base"][i][idx_press[i]], m2, A, cfg)
        pp_rows[i] = pred
        alpha[i] = d["density_alpha"][i][idx_alpha[i]]
        beta[i] = rolling_beta(d["beta_1d"][i], H)
        theta[i] = fecundity(ops, d["fec_at_m0"][i], d["fec_at_m1"][i], m0, m1, cfg)
        egg[i] = d["egg_survival_base"][i] * cfg.egg_scale
    res.beta = beta
    res.s_mature = s_rows[:, :, fishable].mean(axis=2)

    for sc in SCENARIOS:
        Xs = np.zeros((D, H, A))
        Cs = np.zeros((D, H, A))
        Fs = np.zeros((D, H))
        Ms = np.zeros((D, H))
        for i in range(D):
            X_prev = Xh[i, -1]
            for h in range(H):
                s_row, pp = s_rows[i, h], pp_rows[i, h]
                if sc == "none":
                    C = np.zeros(A)
                elif sc == "fixed":
                    C = distribute_pdu(X_prev, weights_last, fishable, ages, m1, pdu_fixed_t * 1e6).pieces
                else:
                    C, Fs[i, h], Ms[i, h] = baranov_catch(X_prev, s_row, next_age_predation(pp, h_mask),
                                                          fishable, settings.k)
                X_new, _ = step(ops, X_prev, s_row, pp, beta[i, h], C[1:-1], K[h], alpha[i, h], theta[i], eps,
                                egg[i], h_mask, cfg)
                Xs[i, h], Cs[i, h] = X_new, C
                X_prev = X_new
        res.X[sc], res.catch[sc] = Xs, Cs
        if sc == "baranov":
            res.F, res.Mbar = Fs, Ms
    return res
