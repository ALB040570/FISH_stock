"""Пакеты алгоритмов в отдельных процессах (как у воркера): цепочка этапов 1–3, априорная проверка, прогноз."""
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest

from conftest import REPO, dict_maps, upload_samples

sys.path.insert(0, str(REPO / "algorithms"))
import build  # noqa: E402
import executor  # noqa: E402

PKG = {m["code"]: f for m, f in build.builtin()}


def manifest_defaults(code):
    m = json.loads(PKG[code]["manifest.json"])
    return {p["code"]: p["default"] for p in m["parameters"] if p.get("default") is not None}


@pytest.fixture()
def env(data_stack, tmp_path):
    dm, da, _ = data_stack
    tables = upload_samples(da)
    (tmp_path / "tables.json").write_text(json.dumps(tables, ensure_ascii=False))
    sp, gk = dict_maps(dm)
    return tmp_path, sp, gk


def step(tmp, sp, gk, code, inputs=None, params=None, name=None):
    d = tmp / (name or code)
    ctx = {"run_id": "test", "step": code, "water_body": "zhaysan", "params": {**manifest_defaults(code), **(params or {})},
           "species_names": sp, "gear_kinds": gk, "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()},
           "tables_path": str(tmp / "tables.json")}
    executor.prepare_step(d, PKG[code], ctx)
    st = executor.run_step(d, timeout_s=900)
    assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-2000:] if (d / "log.txt").exists() else "")
    return d, executor.read_result(d)


def test_chain_1_2_3(env):
    tmp, sp, gk = env
    d1, r1 = step(tmp, sp, gk, "seine_catchability")
    assert r1["tables"]["coefficients"]["rows"] and r1["payload"]["fits"]["лещ"]
    d2, r2 = step(tmp, sp, gk, "stock_by_catch", {"seine_catchability": d1})
    assert {"yearly_stock", "stock_by_age", "net_coefficients"} <= set(r2["tables"])
    assert any(f["name"] == "zhaysan_stock_net_with_ages_3d.nc" for f in r2["files"])
    d3, r3 = step(tmp, sp, gk, "pdu_by_age", {"stock_by_catch": d2})
    rows = r3["tables"]["pdu_by_age"]["rows"]
    lesh24 = sum(r["pdu_t"] or 0 for r in rows if r["species"] == "лещ" and r["year"] == 2024)
    assert abs(lesh24 - 4488) < 1  # квота НПЦ 4488 т распределена полностью
    # без цепочки шаг 3 считает этапы 1–2 сам — результат тот же
    d3b, r3b = step(tmp, sp, gk, "pdu_by_age", name="pdu_alone")
    a = [r["pdu_pcs"] for r in rows]
    b = [r["pdu_pcs"] for r in r3b["tables"]["pdu_by_age"]["rows"]]
    assert np.allclose(np.array(a, float), np.array(b, float), rtol=1e-12, equal_nan=True)
    # априорная проверка байесовской модели (секунды)
    d4, r4 = step(tmp, sp, gk, "bayes_cohort", {"stock_by_catch": d2, "pdu_by_age": d3},
                  {"mode": "prior", "species": ["lesh", "sudak"]})
    assert set(r4["payload"]["species"]) == {"лещ", "судак"}
    assert r4["tables"]["bayes_totals"]["rows"]


def test_forecast_matches_legacy(env):
    """Прогноз по сохранённым заказчиком выборкам байесовской модели совпадает с исходным приложением."""
    tmp, sp, gk = env
    fake = tmp / "bayes" / "out"
    fake.mkdir(parents=True)
    for f in ("zhaysan_bayes_lesh.npz", "zhaysan_bayes_sudak.npz"):
        shutil.copy(REPO / "legacy" / "fish_stock_forecast" / "results" / f, fake / f)
    params = {"horizon": 4, "k": 5.5, "mortality": {"lesh": {"2025": 0.02, "2026": 0.04}, "sudak": {"2025": 0.04}},
              "pdu_t": {"lesh": 4488.0, "sudak": 1394.0}}
    d5, r5 = step(tmp, sp, gk, "forecast_pdu", {"bayes_cohort": tmp / "bayes"}, params)
    legacy_settings = {"horizon": 4, "k": 5.5, "areas": {},
                       "species": {"лещ": {"mortality": {"2025": 0.02, "2026": 0.04}, "pdu_t": 4488.0},
                                   "судак": {"mortality": {"2025": 0.04}, "pdu_t": 1394.0}}}
    for ru in ("лещ", "судак"):
        out = subprocess.run([sys.executable, str(REPO / "algorithms/tests/legacy_forecast.py"), ru,
                              json.dumps(legacy_settings)], capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr[-2000:]
        old = json.loads(out.stdout.strip().splitlines()[-1])
        new = r5["payload"]["species"][ru]
        for sc in ("baranov", "fixed", "none"):
            for k in ("total_q", "pdu_t_q", "fishable_q"):
                a = np.array(old["scenarios"][sc][k], float)
                b = np.array(new["scenarios"][sc][k], float)
                assert np.allclose(a, b, rtol=1e-6, equal_nan=True), (ru, sc, k)
        assert old["settings"]["pdu_fixed_t"] == new["settings"]["pdu_fixed_t"]


def test_cancel_running_step(tmp_path):
    """Отмена выполняющегося шага: алгоритм останавливается при ближайшем ctx.progress()."""
    import time
    files = {"manifest.json": json.dumps({"code": "slow", "version": "0.0.1", "title_ru": "медленный", "entrypoint": "algorithm:run",
                                          "parameters": [], "requires": {}}).encode(),
             "algorithm.py": b"import time\ndef run(ctx):\n    for i in range(600):\n        time.sleep(0.1)\n        ctx.progress(i / 600)\n"}
    d = tmp_path / "slow"
    executor.prepare_step(d, files, {"water_body": "x", "params": {}})
    t0 = time.time()
    st = executor.run_step(d, timeout_s=120, on_poll=lambda: time.time() - t0 > 1.5, poll_s=0.5)
    assert st["status"] == "cancelled" and time.time() - t0 < 30


def test_failing_step_reports_error(tmp_path):
    files = {"manifest.json": json.dumps({"code": "bad", "version": "0.0.1", "title_ru": "ошибка", "entrypoint": "algorithm:run",
                                          "parameters": [], "requires": {}}).encode(),
             "algorithm.py": "from fishrunner import UserError\ndef run(ctx):\n    raise UserError('нет данных за 2024 год')\n".encode()}
    d = tmp_path / "bad"
    executor.prepare_step(d, files, {"water_body": "x", "params": {}})
    st = executor.run_step(d, timeout_s=60)
    assert st["status"] == "failed" and st["message"] == "нет данных за 2024 год" and "traceback" not in st
