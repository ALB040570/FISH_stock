"""
Тесты этапа 5 (прогноз и ПДУ):
    прогноз без промысла и без случайностей = продолжение тех же уравнений модели;
    уравнение Баранова: вылов не больше запаса, при F = M доля изъятия = ½(1 − e^(−2M));
    скользящее среднее β; масштабирование смертности; фиксированный ПДУ распределяется полностью.

Запуск: python -m tests.test_forecast
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from core.bayes import config as bc
from core.bayes.dynamics import Constants, NumpyOps, maturity, prior_means, simulate
from core.forecast import (ForecastSettings, Posterior, baranov_catch, rolling_beta, run_forecast,
                           scale_mortality)


def _setup(cfg, m0=3, m1=9, m2=5, Y=6, H=4, D=2, fry=2.0, area=1000.0):
    """Синтетическая «апостериорная» выборка: параметры постоянны по годам, чтобы прогноз был детерминирован."""
    rng = np.random.default_rng(3)
    K = area * 1e6 * 0.1 * fry * 10
    total = Y + H
    pdu = np.zeros((total, m1 - 1))
    pdu[:Y] = rng.uniform(0, 5e4, (Y, m1 - 1)) + 0.1
    c = Constants(m0=m0, m1=m1, m2=m2, n_years=total, eps=maturity(m0, m1), K=np.full(total, K), pdu=pdu,
                  x0=rng.uniform(1e5, 2e6, m1 - 1), fec_bounds=(2000.0, 90000.0))
    draws, full = {}, []
    for i in range(D):
        p = prior_means(c, cfg)
        p["s_base"] *= 1 + 0.1 * i
        p["density_alpha"] = np.full(total, 0.8 + 0.1 * i)
        p["beta_1d"] = np.full(total, 1.05)
        p["s_year_fluct"] = np.zeros(total)
        out = simulate(NumpyOps, p, c, cfg)
        full.append(out["X_estimated"])
        for k, v in p.items():
            v = np.asarray(v)
            draws.setdefault(k, []).append(v[:Y] if v.ndim == 1 and len(v) == total else v)
        draws.setdefault("X_estimated", []).append(out["X_estimated"][:Y])
    draws = {k: np.array(v) for k, v in draws.items()}
    years = list(range(2015, 2015 + Y))
    post = Posterior(species="тест", years=years, m0=m0, m1=m1, m2=m2, cfg=cfg, draws=draws,
                     X_q=np.zeros((5, Y, m1)), total_obs_q=np.zeros((5, Y)))
    return post, np.array(full), c, K


def test_no_fishing_equals_model_continuation():
    worst = 0.0
    for sp in ("окунь", "лещ", "карась", "щука"):
        cfg = replace(bc.DEFAULTS[sp], s_year_sigma=1e-12)
        post, full, c, K = _setup(cfg)
        Y, H = len(post.years), 4
        w = np.linspace(10, 900, post.m1)
        areas = {post.years[-1] + h: 1000.0 for h in range(1, H + 1)}
        res = run_forecast(post, ForecastSettings(horizon=H, areas=areas), np.tile(w, (Y, 1)), w, 2.0, 1000.0, 100.0)
        for i in range(len(full)):
            rel = np.abs(res.X["none"][i] - full[i][Y:]) / np.maximum(np.abs(full[i][Y:]), 1.0)
            worst = max(worst, float(rel.max()))
    assert worst < 1e-6, worst
    print(f"  без промысла = продолжение уравнений модели (4 вида, наибольшее отличие {worst:.1e})")


def test_baranov():
    X = np.array([1e6, 5e5, 3e5, 2e5, 1e5])
    s = np.array([0.9, 0.4, 0.2, 0.15, 0.3])
    g = np.array([0.1, 0.05, 0.0, 0.0, 0.0])
    fish = np.array([False, False, True, True, True])
    C, F, Mbar = baranov_catch(X, s, g, fish, 1.0)
    M = -np.log((1 - s) / (1 + g))
    assert np.all(C <= X) and np.all(C[~fish] == 0)
    assert abs(Mbar - (M[fish] * X[fish]).sum() / X[fish].sum()) < 1e-12 and abs(F - Mbar) < 1e-12
    # при одинаковой M у всех промысловых возрастов и F = M: доля = ½(1 − e^(−2M))
    s2 = np.full(5, 0.25)
    C2, F2, _ = baranov_catch(X, s2, np.zeros(5), fish, 1.0)
    m = -math.log(0.75)
    assert np.allclose(C2[fish] / X[fish], 0.5 * (1 - math.exp(-2 * m)))
    C0, F0, _ = baranov_catch(X, s, g, fish, 0.0)
    assert F0 == 0 and np.all(C0 == 0)
    print("  Баранов: C ≤ X, F = M̄, доля ½(1 − e^(−2M)), k = 0 → без вылова")


def test_rolling_beta():
    b = rolling_beta(np.array([0.5, 1.0, 2.0, 3.0]), 4)
    exp = [2.0, (3 + 2 + 2.0) / 3]
    exp.append((3.0 + exp[0] + exp[1]) / 3)
    exp.append((exp[0] + exp[1] + exp[2]) / 3)
    assert np.allclose(b, exp), (b, exp)
    print("  β: среднее за 3 предыдущих года, с 4-го года — по прогнозным")


def test_scale_mortality_and_fixed_pdu():
    cfg = bc.DEFAULTS["окунь"]
    ages = np.arange(1, 10)
    s0 = np.array([0.9, 0.4, 0.15, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3])
    s = scale_mortality(s0, 0.3, ages, 3, cfg)
    assert abs(s[ages >= 3].mean() - 0.3) < 1e-12
    assert np.allclose((s / s0)[ages >= 3], s[2] / s0[2])        # форма сохранена (молодь обрезана сверху)
    assert s.max() <= cfg.s_clip_hi
    post, _, _, _ = _setup(cfg)
    Y, w = len(post.years), np.linspace(10, 900, post.m1)
    res = run_forecast(post, ForecastSettings(horizon=3, pdu_t=5.0), np.tile(w, (Y, 1)), w, 2.0, 1000.0, 100.0)
    assert np.allclose(res.pdu_tonnes("fixed"), 5.0, rtol=1e-6)
    assert np.all(res.pdu_tonnes("none") == 0)
    assert res.area_default_years == [post.years[-1] + h for h in (1, 2, 3)]
    print("  смертность масштабируется к заданному уровню; фиксированный ПДУ распределяется полностью")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("OK")
