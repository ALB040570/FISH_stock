"""
Тесты этапа 4 (байесовская модель) без PyMC:
    уравнения dynamics.simulate против независимой записи поэлементными циклами (все варианты формул);
    настройки видов: сохранение, сброс, проверка значений;
    входные данные из этапов 2–3;
    априорная проверка (режим "prior") — сохранение и чтение .npz.

Запуск: python -m tests.test_bayes
"""
from __future__ import annotations

import math
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from core import config as app_config
from core.bayes import config as bc
from core.bayes.dynamics import Constants, NumpyOps, maturity, prior_means, simulate


def softplus(x):
    return math.log1p(math.exp(-abs(x))) + max(x, 0.0)


def reference(p, c: Constants, cfg) -> np.ndarray:
    """Независимая запись уравнений (16)-(17) и блоков старых скриптов — скалярные циклы."""
    Y, A, m0, m1, m2 = c.n_years, c.m1, c.m0, c.m1, c.m2
    opt = m0 + 1
    peak = max(p["s_base"] + (1 - opt) ** 2 * p["s_juvenile_steep"],
               p["s_base"] + (m1 - opt) ** 2 * p["s_aging_slow"])
    s = np.zeros((Y, A))
    for t in range(Y):
        for j in range(1, A + 1):
            d = j - opt
            curve = p["s_base"] + d * d * (p["s_juvenile_steep"] if d < 0 else p["s_aging_slow"])
            raw = (curve + 1e-6) * math.exp(p["s_year_fluct"][t])
            norm = raw / (peak + 2e-6) * cfg.s_norm
            if cfg.s_clip_mode == "peak_switch" and peak < 0.99:
                s[t, j - 1] = min(max(raw, cfg.s_clip_lo), cfg.s_clip_hi)
            else:
                s[t, j - 1] = min(max(norm, cfg.s_clip_lo), cfg.s_clip_hi)
    g = np.zeros((Y, A))
    for t in range(Y):
        row = [p["press_base"][t] / j if j <= m2 else 0.0 for j in range(1, A + 1)]
        mx = max(row) + 1e-6
        g[t] = [v / mx * cfg.press_max for v in row]
    slope = (p["fec_at_m1"] - p["fec_at_m0"]) / (m1 - m0 + 1e-6)
    theta = [p["fec_at_m0"] + slope * (j - m0 - cfg.theta_offset) for j in range(1, A + 1)]
    if cfg.theta_nonneg:
        theta = [max(v, 0.0) for v in theta]
    eggsurv = p["egg_survival_base"] * cfg.egg_scale

    def recruits(t, eggs):
        cap = c.K[t] * p["density_alpha"][t]
        larvae = eggs * eggsurv
        if t > 0 and cfg.density_softmin == "plain":
            eff = cap - softplus(cap - larvae)
        else:
            eff = cap - softplus((cap - larvae) / 1e5) * 1e5
        return eff * (1 - s[t, 0]) ** 2 / (1 + g[t, 0])

    X = np.zeros((Y, A))
    older = [min(max(v, lo), hi) for v, lo, hi in
             zip(p["X_initial_older_raw"], c.x0 * cfg.x0_lo, c.x0 * cfg.x0_hi)]
    eggs0 = sum(theta[j] * 0.5 * older[j - 1] * c.eps[j] for j in range(1, A))
    X[0, 0] = recruits(0, eggs0)
    X[0, 1:] = older
    X[0] *= [1 / (1 + math.exp(5 * (j - m1))) for j in range(1, A + 1)]
    for t in range(1, Y):
        prev = X[t - 1]
        if cfg.eggs_mode == "older_half":
            eggs = sum(theta[j] * 0.5 * prev[j] * c.eps[j] for j in range(1, A))
        else:
            eggs = sum(theta[j] * prev[j] * c.eps[j] for j in range(A))
        cur = np.zeros(A)
        cur[0] = recruits(t, eggs)
        cur[1] = (1 - s[t, 1]) * prev[0] / (1 + g[t, 1])
        for k in range(2, A):                       # возраст j = k + 1 из j − 1 = k
            surv = (1 - s[t, k - 1]) * prev[k - 1]
            catch = p["beta_1d"][t] * c.pdu[t, k - 2]
            if cfg.catch_mode == "max":
                num = max(surv - catch, 1.0)
            elif cfg.catch_mode == "softplus":
                den = 1000 + softplus((surv - 1000) / 100) * 100
                rate = 0.95 - softplus((0.95 - catch / den) * 10) / 10
                num = 1.3 + softplus((surv * (1 - rate) - 1.3) * 2) / 2
            else:
                num = surv - math.tanh(1 / (catch / (surv + 1) + 1e-5)) * catch
            j = k + 1
            h = (1.0 if j <= m2 else 0.0) if cfg.h_mask_mode == "step" else 1 / (1 + math.exp(5 * (j - m2)))
            cur[k] = num / (1 + h * g[t, k])
        if cfg.x_softplus:
            cur = np.array([softplus(v) for v in cur])
        X[t] = cur
    return X


def _constants(m0=3, m1=9, m2=5, Y=6, seed=0):
    rng = np.random.default_rng(seed)
    x0 = rng.uniform(1e4, 3e6, m1 - 1)
    pdu = rng.uniform(0, 2e5, (Y, m1 - 1)) + 0.1
    return Constants(m0=m0, m1=m1, m2=m2, n_years=Y, eps=maturity(m0, m1), K=rng.uniform(5e8, 3e9, Y),
                     pdu=pdu, x0=x0, fec_bounds=(2000.0, 120000.0))


def _random_params(c, cfg, rng):
    p = prior_means(c, cfg)
    Y, A = c.n_years, c.m1
    p["s_year_fluct"] = rng.normal(0, 0.05, Y)
    p["press_base"] = np.exp(rng.normal(cfg.press_mu, 0.13, Y))
    p["beta_1d"] = rng.uniform(cfg.beta_lower, min(cfg.beta_upper, 2.0), Y)
    p["density_alpha"] = np.exp(rng.normal(0, 0.2, Y))
    p["X_initial_older_raw"] = c.x0 * np.exp(rng.normal(0, 0.4, A - 1))
    p["s_base"] *= math.exp(rng.normal(0, 0.1))
    return p


def test_dynamics_matches_reference():
    """Все 8 видов и дополнительные сочетания вариантов формул."""
    rng = np.random.default_rng(1)
    variants = list(bc.DEFAULTS.values())
    base = bc.DEFAULTS["окунь"]
    variants += [replace(base, catch_mode=cm, h_mask_mode=hm, x_softplus=xs, eggs_mode=em, density_softmin=dm,
                         s_clip_mode=sm, theta_offset=to, theta_nonneg=tn)
                 for cm, hm, xs, em, dm, sm, to, tn in [
                     ("max", "sigmoid", True, "older_half", "plain", "peak_switch", 1, False),
                     ("softplus", "step", False, "all_ages", "scaled", "normalized", 0, True),
                     ("tanh", "step", False, "older_half", "plain", "peak_switch", 1, True)]]
    worst = 0.0
    for i, cfg in enumerate(variants):
        for m0, m1, m2 in ((3, 9, 5), (4, 12, 12), (2, 10, 3)):
            c = _constants(m0, m1, m2, seed=i)
            p = _random_params(c, cfg, rng)
            X = simulate(NumpyOps, p, c, cfg)["X_estimated"]
            ref = reference(p, c, cfg)
            rel = np.max(np.abs(X - ref) / np.maximum(np.abs(ref), 1.0))
            worst = max(worst, rel)
            assert rel < 1e-9, (i, cfg.catch_mode, m0, m1, m2, rel)
    print(f"  динамика = независимая запись: {len(variants)} вариантов × 3 вида, наибольшее отличие {worst:.1e}")


def test_catch_reduces_stock():
    """Больший вылов (β·A) даёт меньше рыбы старших возрастов в следующем году."""
    for mode in ("tanh", "max", "softplus"):
        cfg = replace(bc.DEFAULTS["окунь"], catch_mode=mode, x_softplus=False)
        c = _constants()
        p = prior_means(c, cfg)
        X1 = simulate(NumpyOps, p, c, cfg)["X_estimated"]
        c2 = replace(c, pdu=c.pdu * 3)
        X2 = simulate(NumpyOps, p, c2, cfg)["X_estimated"]
        assert np.all(X2[1, 2:] <= X1[1, 2:] + 1e-6), mode
        assert np.all(X2[1, :2] == X1[1, :2]), mode   # 0–1 и 1–2 не облавливаются
    print("  вылов уменьшает запас старших возрастов (3 варианта формулы (17))")


def test_config_roundtrip():
    old = app_config.RESULTS_DIR
    app_config.RESULTS_DIR = Path(tempfile.mkdtemp())
    try:
        for sp in bc.DEFAULTS:
            assert bc.validate(sp, {}) == [], sp
        cfg = bc.save_overrides("судак", {"s_juv_mu": "-1.5", "draws": "500", "catch_mode": "tanh",
                                          "s_base_mu": -2.2})
        assert cfg.s_juv_mu == -1.5 and cfg.draws == 500 and cfg.catch_mode == "tanh"
        assert bc.overrides("судак") == {"s_juv_mu": -1.5, "draws": 500, "catch_mode": "tanh"}
        for bad in ({"beta_lower": 3.0}, {"catch_mode": "x"}, {"target_accept": 1.5}, {"x0_lo": 2.0}):
            try:
                bc.save_overrides("судак", bad)
                raise AssertionError(bad)
            except ValueError:
                pass
        assert bc.reset("судак").s_juv_mu == bc.DEFAULTS["судак"].s_juv_mu
        assert bc.get_config("судак") == bc.DEFAULTS["судак"]
    finally:
        app_config.RESULTS_DIR = old
    print("  настройки: сохранение, проверка и сброс")


def test_inputs_and_prior_run():
    from core.bayes import run as R
    from core.bayes.inputs import build_new_inputs
    from core.data_source import load_fish_props
    from core.pdu_npc import compute_pdu
    from core.stock import compute_stock

    props = load_fish_props()
    res, _, _ = compute_stock(props=props)
    pdu = compute_pdu(res, props)
    tmp = Path(tempfile.mkdtemp())
    for sp, cfg in bc.DEFAULTS.items():
        inp = build_new_inputs(sp, cfg, res, pdu, props)
        c = inp.consts
        assert inp.stock.shape[1] == c.m1 - 1 and np.all(inp.stock >= 0.1)
        assert inp.year_idx.min() >= 0 and inp.year_idx.max() < c.n_years
        assert c.pdu.shape == (c.n_years, c.m1 - 1) and np.all(c.pdu >= 0.1)
        assert np.all(c.x0 >= 1.0) and len(c.x0) == c.m1 - 1
        X = simulate(NumpyOps, prior_means(c, cfg), c, cfg)["X_estimated"]
        assert np.all(np.isfinite(X)) and X.shape == (c.n_years, c.m1)
    meta = R.run("окунь", "prior", results_dir=tmp, stage23=(res, pdu, props), log=lambda *a: None)
    arrays, m = R.load_npz(R.result_path("окунь", "prior", "npz", tmp))
    assert m["mode"] == "prior" and arrays["X_q"].shape[0] == 5
    assert arrays["draw_X_estimated"].shape[0] == R.N_KEEP
    q = arrays["total_obs_q"]
    assert np.all(q[0] <= q[2]) and np.all(q[2] <= q[4])
    print(f"  входные данные 8 видов; априорная проверка окуня за {meta['seconds']} с")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("OK")
