"""
Тесты проверок для ответа рецензентам:
    без PyMC — моделирование синтетических данных (восстановление параметров), чувствительность модели баланса;
    с PyMC (пропускается, если PyMC не установлен) — весь расчёт на коротких цепях (2 × 20 выборок, лещ):
    файлы диагностики, монотонность когорт, ретроспективный прогноз, таблицы приложения, сводка диагностики.

Запуск: python -m tests.test_bayes_pipeline
"""
from __future__ import annotations

import dataclasses
from dataclasses import replace
import importlib.util
import json
import tempfile
from pathlib import Path

import numpy as np

from core.bayes import config as bc

SHORT = dict(chains=2, draws=20, tune=20)


def _stage23():
    from core.data_source import load_fish_props
    from core.pdu_npc import compute_pdu
    from core.stock import compute_stock

    props = load_fish_props()
    res, _, _ = compute_stock(props=props)
    return res, compute_pdu(res, props), props


def test_simulated_observations():
    """Синтетические данные: та же схема ловов; при σ → 0 оценки по ловам = ожиданию модели."""
    from core.bayes.analyses import simulate_observations, true_parameters
    from core.bayes.dynamics import NumpyOps, expected_observations, mu_floor
    from core.bayes.inputs import build_new_inputs

    res, pdu, props = _stage23()
    cfg = bc.DEFAULTS["лещ"]
    inp = build_new_inputs("лещ", cfg, res, pdu, props)
    p, _ = true_parameters("лещ", inp, cfg, Path(tempfile.mkdtemp()))
    p["sigma_stock"] = 1e-12
    p["log_q_net"] = 0.3
    p["zero_c"] = np.array([50.0, 50.0])          # λ огромна — пустых ловов нет
    syn, X = simulate_observations(inp, cfg, p, seed=1)
    exp_, sl = expected_observations(X, p["q_bias"], inp.year_idx, cfg, inp.gear, 0.3)
    assert syn.stock.shape == inp.stock.shape and np.array_equal(syn.year_idx, inp.year_idx)
    assert not syn.zero_mask.any() and syn.zero_ref == inp.zero_ref
    assert np.allclose(syn.stock[:, sl], mu_floor(NumpyOps, exp_, cfg) + cfg.obs_pad, rtol=1e-9)

    p["zero_c"] = np.array([-50.0, -50.0])        # λ ≈ 0 — все ловы пустые, оценки равны добавке obs_pad
    syn, _ = simulate_observations(inp, cfg, p, seed=1)
    assert syn.zero_mask.all() and np.allclose(syn.stock, cfg.obs_pad)

    cfg_pad = dataclasses.replace(cfg, likelihood="pad")    # прежнее правдоподобие: оценки = ожиданию модели
    syn, _ = simulate_observations(inp, cfg_pad, p, seed=1)
    assert np.allclose(syn.stock[:, sl], mu_floor(NumpyOps, exp_, cfg), rtol=1e-9)


def test_balance_sensitivity():
    """База — множитель 1; больше V, k или времени стоянки — меньше запас; p_to_net = 0,25 — прежняя модель."""
    from core.net_model import balance_model
    from core.net_sensitivity import species_table

    rows = species_table("тест", 180.0, 0.2, 12, 25.0)
    f = {(r["parameter"], round(float(r["value"] or 0), 6)): r["stock_factor"] for r in rows}
    assert f[("база", 0.0)] == 1.0
    assert f[("V, м/ч", 270.0)] < 1 < f[("V, м/ч", 90.0)]
    assert f[("k", 0.3)] < 1 < f[("k", 0.1)]
    assert f[("p_to_net", 0.35)] < 1 < f[("p_to_net", 0.15)]
    a = balance_model(0.3, 12, 25.0, 180.0)[1]["Сеть"]
    b = balance_model(0.3, 12, 25.0, 180.0, p_to_net=0.25)[1]["Сеть"]
    assert a == b


def test_delta_likelihood_matches_numpy():
    """Дельта-правдоподобие (логнормальное, гамма, по сумме лова) в PyMC = формуле numpy (log_likelihood_np) в начальной точке."""
    if importlib.util.find_spec("pymc") is None:
        print("  PyMC не установлен — пропуск")
        return
    from core.bayes.dynamics import log_likelihood_np
    from core.bayes.inputs import build_new_inputs
    from core.bayes.model import build_model

    res, pdu, props = _stage23()
    for sp, pos in (("щука", "lognormal"), ("лещ", "lognormal"), ("карась", "gamma"), ("карась", "lognormal_total")):
        cfg = replace(bc.get_config(sp), delta_pos=pos)
        assert cfg.likelihood == "delta"
        inp = build_new_inputs(sp, cfg, res, pdu, props)
        assert inp.zero_mask.any() or sp == "лещ"
        model = build_model(inp, cfg)
        assert {"zero_c", "zero_b"} <= {rv.name for rv in model.free_RVs}
        pt_ll = model.compile_logp(vars=model.observed_RVs, jacobian=False)(model.initial_point())
        names = ["X_estimated", "q_bias", "sigma_stock", "zero_c", "zero_b", "log_q_net"]
        outs = model.replace_rvs_by_values([model[n] for n in names])
        fn = model.compile_fn(outs, inputs=model.value_vars, on_unused_input="ignore")
        vals = dict(zip(names, fn(model.initial_point())))
        np_ll = log_likelihood_np(vals["X_estimated"], vals["q_bias"], float(vals["sigma_stock"]), inp.stock,
                                  inp.year_idx, cfg, inp.gear, float(vals["log_q_net"]), inp.zero_mask,
                                  vals["zero_c"], float(vals["zero_b"]))
        assert np.isclose(float(pt_ll), np_ll, rtol=1e-6), (sp, pos, float(pt_ll), np_ll)


def test_short_chains_pipeline():
    """PyMC, 2 цепи × 20 выборок: расчёт, диагностика, монотонность, ретроспектива, приложение, сводка."""
    if importlib.util.find_spec("pymc") is None:
        print("  PyMC не установлен — пропуск")
        return
    from core.bayes import run as R
    from core.bayes.analyses import retro_forecast
    from core.bayes.diagnostics import collect_summary
    from core.bayes.inputs import build_new_inputs
    from scripts.make_appendix_tables import make_tables

    stage23 = _stage23()
    tmp = Path(tempfile.mkdtemp())
    meta = R.run("лещ", "new", results_dir=tmp, stage23=stage23, cfg_changes=SHORT, log=lambda *a: None)
    assert meta["chains"] == 2 and meta["draws_per_chain"] == 20
    assert meta["monotonic_ok"] and meta["monotonic_violations"] == 0
    assert meta["numpy_check"] < 1e-6
    ddir = tmp / "lesh" / "diagnostics"
    for name in ("diagnostics.json", "params.csv", "param_counts.csv", "cap_active.csv", "trace_s_base.png",
                 "prior_posterior_s_base.png", "trace_log_q_net.png"):
        assert (ddir / name).exists(), name
    d = json.loads((ddir / "diagnostics.json").read_text(encoding="utf-8"))
    assert len(d["ebfmi_by_chain"]) == 2 and d["rhat_max_params"] is not None and d["n_free_params"] > 0
    assert d["monotonicity"]["ok"]

    arrays, m = R.load_npz(R.result_path("лещ", "new", "npz", tmp))
    assert "press_base_q" not in arrays and "cap_active_frac" in arrays
    draws = {k[5:]: v for k, v in arrays.items() if k.startswith("draw_")}
    assert "log_q_net" in draws and "press_base" not in draws
    assert "zero_c" in draws and "zero_b" in draws and d["likelihood"] == "delta"

    cfg = R.mode_config("лещ", "new")
    full = build_new_inputs("лещ", cfg, *stage23)
    r = retro_forecast(full, draws, cfg, 2021, tmp, seed=0)
    assert r["forecast_years"] == [2022, 2023, 2024]
    allm = r["metrics"][0]
    assert allm["n"] > 0 and 0 <= allm["coverage95"] <= 1 and allm["rmse_log"] >= allm["mae_log"] > 0

    md = make_tables(tmp / "appendix", results_dir=tmp, log=lambda *a: None)
    assert "Таблица A1. Лещ" in md.read_text(encoding="utf-8") and (tmp / "appendix" / "table_A1_lesh.csv").exists()
    summ = collect_summary(tmp).read_text(encoding="utf-8-sig").splitlines()
    assert summ[1].startswith("лещ,lesh,") and len(summ) == 9
    print(f"  короткие цепи: {meta['seconds']} с, R̂ max {d['rhat_max_params']:.2f}, "
          f"ретроспектива RMSE {allm['rmse_log']:.2f}, покрытие {allm['coverage95']:.2f}")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("OK")
