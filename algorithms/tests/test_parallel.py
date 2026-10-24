"""Одновременный расчёт видов и проверок модели (решение № 64): результаты те же, что при расчёте по очереди.

Короткие цепи (20 + 20 выборок, 2 цепи) — только чтобы сравнить числа: при тех же seed процессы дают те же выборки.
"""
import json
import os

import numpy as np
import pytest

from test_pipeline import PKG, build, env, executor, manifest_defaults  # noqa: F401  (env — фикстура)

# «Проверки модели» в каталог не входят (решение № 65), пакет сохранён — для сверки собирается отдельно
PKG = {**PKG, "bayes_checks": build.package_files("bayes_checks")}

SHORT = {"draws": 20, "tune": 20, "chains": 2}
TIMES = {"seconds", "started", "finished", "diagnostics_dir"}
# ~15 минут на 2 ядрах: запускается при FISH_SLOW_TESTS=1 (перед изменением кода модели и параллельного расчёта)
pytestmark = pytest.mark.skipif(not os.environ.get("FISH_SLOW_TESTS"), reason="долгий тест: FISH_SLOW_TESTS=1")


def _strip(o):
    """Без времени расчёта и путей — они у двух расчётов разные."""
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in TIMES}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _js(o):
    return json.dumps(_strip(o), sort_keys=True, default=str)


def _step(tmp, sp, gk, code, name, inputs=None, params=None):
    d = tmp / name
    ctx = {"run_id": "test", "step": code, "water_body": "zhaysan", "params": {**manifest_defaults(code), **(params or {})},
           "species_names": sp, "gear_kinds": gk, "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()},
           "tables_path": str(tmp / "tables.json")}
    executor.prepare_step(d, PKG[code], ctx)
    st = executor.run_step(d, timeout_s=1800)
    assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-3000:])
    return d, executor.read_result(d)


def _npz(d):
    out = {}
    for f in sorted((d / "out").rglob("*.npz")):
        with np.load(f, allow_pickle=True) as z:
            out[str(f.relative_to(d / "out"))] = {k: z[k] for k in z.files if k != "meta"}
    return out


def _same(a, b):
    assert a.keys() == b.keys()
    for f in a:
        assert a[f].keys() == b[f].keys(), f
        for k in a[f]:
            x, y = a[f][k], b[f][k]
            if x.dtype.kind in "fc":
                assert np.array_equal(x, y, equal_nan=True), (f, k)
            else:
                assert (x == y).all(), (f, k)


def test_parallel_same_as_sequential(env, monkeypatch):
    tmp, sp, gk = env
    da, _ = _step(tmp, sp, gk, "net_catchability", "a")
    db, _ = _step(tmp, sp, gk, "seine_catchability", "b")
    dc, _ = _step(tmp, sp, gk, "seine_likelihood", "c", {"seine_catchability": db})
    dd, _ = _step(tmp, sp, gk, "net_likelihood", "d", {"net_catchability": da})
    de, _ = _step(tmp, sp, gk, "seine_stock", "e", {"seine_likelihood": dc})
    df, _ = _step(tmp, sp, gk, "net_stock", "f", {"net_likelihood": dd})
    dg, _ = _step(tmp, sp, gk, "combined_stock", "g", {"seine_stock": de, "net_stock": df})
    d3, _ = _step(tmp, sp, gk, "pdu_by_age", "h", {"combined_stock": dg})
    prm = {**SHORT, "species": ["lesh", "plotva"]}
    inp = {"seine_likelihood": dc, "net_likelihood": dd, "combined_stock": dg, "pdu_by_age": d3}
    monkeypatch.setenv("FISH_CALC_CORES", "1")                 # по очереди, в одном процессе
    ds, rs = _step(tmp, sp, gk, "bayes_cohort", "seq", inp, prm)
    monkeypatch.setenv("FISH_CALC_CORES", "4")                 # 2 процесса по 2 цепи
    dp, rp = _step(tmp, sp, gk, "bayes_cohort", "par", inp, prm)
    assert "одновременно: 2 расчётов" in (dp / "log.txt").read_text()
    assert "одновременно" not in (ds / "log.txt").read_text()
    _same(_npz(ds), _npz(dp))
    assert _js(rs["payload"]) == _js(rp["payload"])
    assert _js(rs["tables"]) == _js(rp["tables"]) and rs["metrics"] == rp["metrics"]

    # проверки модели: пустые ловы (2 варианта — 2 процесса) и синтетические данные
    chk = {**SHORT, "check_net": True, "check_retro": False, "check_prior": False, "check_pad": True, "check_recovery": True,
           "pad_species": ["lesh"], "recovery_species": ["lesh"], "pads": [0.1, 1.0]}
    monkeypatch.setenv("FISH_CALC_CORES", "1")
    cs, crs = _step(tmp, sp, gk, "bayes_checks", "cseq", {"bayes_cohort": ds}, chk)
    monkeypatch.setenv("FISH_CALC_CORES", "6")                 # 3 процесса по 2 цепи
    cp, crp = _step(tmp, sp, gk, "bayes_checks", "cpar", {"bayes_cohort": ds}, chk)
    assert "одновременно: 3 расчётов" in (cp / "log.txt").read_text()
    _same(_npz(cs), _npz(cp))
    assert _js(crs["payload"]) == _js(crp["payload"])
    assert _js(crs["tables"]) == _js(crp["tables"])
    pad_csv = lambda d: (d / "out" / "lesh" / "sens_pad" / "compare_pad.csv").read_text()  # noqa: E731
    assert pad_csv(cs) == pad_csv(cp) and "obs_pad = 1" in pad_csv(cp)
