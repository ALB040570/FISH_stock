"""Пакеты алгоритмов каталога a–j в отдельных процессах (как у воркера): сверка с прежним общим расчётом,
период расчёта, априорная проверка модели, прогноз (решение № 70)."""
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


def step(tmp, sp, gk, code, inputs=None, params=None, name=None, period=None, wb="zhaysan"):
    d = tmp / (name or code)
    ctx = {"run_id": "test", "step": code, "water_body": wb, "params": {**manifest_defaults(code), **(params or {})},
           "species_names": sp, "gear_kinds": gk, "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()},
           "tables_path": str(tmp / "tables.json"), "period": period}
    executor.prepare_step(d, PKG[code], ctx)
    st = executor.run_step(d, timeout_s=900)
    assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-2000:] if (d / "log.txt").exists() else "")
    return d, executor.read_result(d)


def _state(d):
    import pickle
    with open(d / "out" / "state.pkl", "rb") as f:
        return pickle.load(f)


def _reference(tmp, sp, gk, wb="zhaysan"):
    """Прежний общий расчёт этапов 1–3 в этом процессе (эталон сверки отдельных алгоритмов) — с теми же значениями
    параметров, что в манифестах (там 1/3 записана как 0,3333333333)."""
    import copy as _copy
    from fishcore import config, stepkit
    saved = {k: _copy.deepcopy(getattr(config, k)) for k in (*stepkit.FIXED_CONFIG, "NET_PANELS_BY_CATCH_TYPE")}
    try:
        for code in ("net_catchability", "seine_catchability", "net_likelihood", "combined_stock", "pdu_by_age"):
            stepkit.apply_fixed(manifest_defaults(code))
        return _reference_calc(tmp, sp, gk, wb)
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


def _reference_calc(tmp, sp, gk, wb):
    from fishcore.bundle import Bundle
    from fishcore.data_source import load_fish_props
    from fishcore.pdu_npc import compute_pdu
    from fishcore.stock import compute_stock
    tables = json.loads((tmp / "tables.json").read_text())
    b = Bundle(wb, tables, sp, gk)
    props = load_fish_props(wb, b)
    res, net_c, seine_c = compute_stock(wb, b, props=props)
    return res, compute_pdu(res, props, data_dir=b), props


def test_catalog_algorithms_a_to_h_match_reference(env):
    """Алгоритмы a–h каталога (решение № 70), каждый в своём процессе, дают те же числа, что прежний общий расчёт
    этапов 1–3 (а он сверен с эталоном 22.10 — test_regression_stage123)."""
    from fishcore import config
    from fishcore.stock import MEAN
    tmp, sp, gk = env
    da, ra = step(tmp, sp, gk, "net_catchability")
    db, rb = step(tmp, sp, gk, "seine_catchability")
    dc, rc = step(tmp, sp, gk, "seine_likelihood", {"seine_catchability": db})
    dd, rd = step(tmp, sp, gk, "net_likelihood", {"net_catchability": da})
    de, re_ = step(tmp, sp, gk, "seine_stock", {"seine_likelihood": dc})
    df, rf = step(tmp, sp, gk, "net_stock", {"net_likelihood": dd})
    dg, rg = step(tmp, sp, gk, "combined_stock", {"seine_stock": de, "net_stock": df})
    dh, rh = step(tmp, sp, gk, "pdu_by_age", {"combined_stock": dg})
    ref, ref_pdu, props = _reference(tmp, sp, gk)
    NET, SEINE = config.GEAR_NET, config.GEAR_SEINE
    close = lambda a, b: np.allclose(np.asarray(a, float), np.asarray(b, float), rtol=1e-12, atol=0, equal_nan=True)
    assert close(_state(da)["cube"], ref.catchability[(NET, "with_ages")])
    assert close(_state(db)["cube"], ref.catchability[(SEINE, "with_ages")])
    assert close(_state(dc)["per_haul"], ref.per_haul[(SEINE, "with_ages")])
    assert close(_state(dd)["sigma"], ref.sigma["with_ages"])
    assert close(_state(dd)["per_haul"], ref.per_haul[(NET, "with_ages")])
    assert close(_state(de)["yearly"], ref.yearly[(SEINE, "with_ages", "on_stock")])
    assert close(_state(df)["yearly"], ref.yearly[(NET, "with_ages", "on_stock")])
    g = _state(dg)["res"]
    assert close(g.yearly[(MEAN, "with_ages", "on_stock")], ref.yearly[(MEAN, "with_ages", "on_stock")])
    assert close(g.npc_stock, ref.npc_stock)
    assert close(_state(dh)["pdu"].pieces, ref_pdu.pieces)
    # контрольные значения эталона 22.10: лещ 2024 — сеть 22 829 938, невод 224 656 053, окончательный 91 190 397
    yi, si = ref.years.index(2024), ref.species.index("лещ")
    # (допуск сверки с эталоном — 1e-6, как в test_regression_stage123)
    for gear, val in ((NET, 22829938), (SEINE, 224656053), (MEAN, 91190397)):
        assert abs(g.yearly_total(gear, "with_ages", "on_stock")[yi, si] / val - 1) < 1e-6
    rows = rh["tables"]["pdu_by_age"]["rows"]
    assert abs(sum(r["pdu_t"] or 0 for r in rows if r["species"] == "лещ" and r["year"] == 2024) - 4488) < 1
    # тонны: промысловый запас окончательный = промысловая биомасса шага ПДУ (те же веса и возрасты)
    t = {(r["year"], r["species"], r["gear"]): r for r in rg["tables"]["tonnes"]["rows"]}
    bio = ref_pdu.fishable_biomass_t()
    assert abs(t[(2024, "лещ", MEAN)]["tonnes_fishable"] - bio[yi, si]) < 1e-3
    assert t[(2024, "лещ", MEAN)]["tonnes_all"] >= t[(2024, "лещ", MEAN)]["tonnes_fishable"]
    # таблицы и представления для мониторинга
    assert ra["payload"]["fits"]["лещ"] and rd["payload"]["net"]["fits"]["лещ"]["2024"]["sigma"]
    assert rg["payload"]["stock"]["species"]["лещ"]["variants"]["with_ages"]["on_stock"]["totals"]
    assert "out_ages" not in rg["payload"]["stock"]["species"]["лещ"]["variants"]
    assert {r["gear"] for r in rc["tables"]["catch_by_age"]["rows"]} == {SEINE}
    # «по улову» — тот же способ у e, f, g, как в прежнем расчёте
    de2, _ = step(tmp, sp, gk, "seine_stock", {"seine_likelihood": dc}, {"STOCK_METHOD": "on_catch"}, name="e2")
    df2, _ = step(tmp, sp, gk, "net_stock", {"net_likelihood": dd}, {"STOCK_METHOD": "on_catch"}, name="f2")
    dg2, _ = step(tmp, sp, gk, "combined_stock", {"seine_stock": de2, "net_stock": df2}, name="g2")
    g2 = _state(dg2)["res"]
    assert g2.method == "on_catch"
    assert close(g2.yearly[(MEAN, "with_ages", "on_catch")], ref.yearly[(MEAN, "with_ages", "on_catch")])
    # разные способы у входов g — понятная ошибка
    d = tmp / "g_bad"
    ctx = {"water_body": "zhaysan", "params": manifest_defaults("combined_stock"), "species_names": sp, "gear_kinds": gk,
           "inputs": {"seine_stock": str(de2 / "out"), "net_stock": str(df / "out")}, "tables_path": str(tmp / "tables.json")}
    executor.prepare_step(d, PKG["combined_stock"], ctx)
    st = executor.run_step(d, timeout_s=300)
    assert st["status"] == "failed" and "разными способами" in st["message"]
    # период: c за 2018–2022 по уловистости невода за все годы
    dcp, rcp = step(tmp, sp, gk, "seine_likelihood", {"seine_catchability": db}, period={"from": 2018, "to": 2022}, name="c_period")
    assert _state(dcp)["years"] == [2018, 2019, 2020, 2021, 2022]
    assert {r["year"] for r in rcp["tables"]["per_haul"]["rows"]} <= set(range(2018, 2023))
    # e за все годы по c за 2018–2022 — расчёт за общие годы с замечанием
    dep, rep_ = step(tmp, sp, gk, "seine_stock", {"seine_likelihood": dcp}, name="e_period")
    assert _state(dep)["years"] == [2018, 2019, 2020, 2021, 2022]
    # h за 2020–2024 по g за все годы — те же числа, что у h за все годы, за эти годы
    dhp, _ = step(tmp, sp, gk, "pdu_by_age", {"combined_stock": dg}, period={"from": 2020, "to": 2024}, name="h_period")
    hp = _state(dhp)["pdu"]
    idx = [ref.years.index(y) for y in hp.years]
    assert hp.years == [2020, 2021, 2022, 2023, 2024] and close(hp.pieces, ref_pdu.pieces[idx])
    # априорная проверка модели по входам c, d, g, h (секунды)
    d4, r4 = step(tmp, sp, gk, "bayes_cohort", {"seine_likelihood": dc, "net_likelihood": dd, "combined_stock": dg,
                                               "pdu_by_age": dh}, {"mode": "prior", "species": ["lesh", "sudak"]})
    assert set(r4["payload"]["species"]) == {"лещ", "судак"}
    assert r4["tables"]["bayes_totals"]["rows"]


def test_missing_input_message(env):
    tmp, sp, gk = env
    d = tmp / "c_alone"
    ctx = {"water_body": "zhaysan", "params": manifest_defaults("seine_likelihood"), "species_names": sp, "gear_kinds": gk,
           "inputs": {}, "tables_path": str(tmp / "tables.json")}
    executor.prepare_step(d, PKG["seine_likelihood"], ctx)
    st = executor.run_step(d, timeout_s=120)
    assert st["status"] == "failed" and "b. Уловистость невода" in st["message"]


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


def test_species_outside_reference(data_stack, tmp_path):
    """Виды, которых нет в профиле Жайсана (жерех, сом), считаются моделью: Балхаш, априорная проверка (секунды).
    Значения профиля — общие значения модели (как при «Добавить вид»), только для проверки работоспособности."""
    from dataclasses import asdict
    from fishcore.bayes import config as bc
    dm, da, _ = data_stack
    tables = upload_samples(da, "balkhash", REPO / "samples" / "balkhash")
    (tmp_path / "tables.json").write_text(json.dumps(tables, ensure_ascii=False))
    sp, gk = dict_maps(dm)

    def step_wb(code, inputs=None, params=None):
        d = tmp_path / code
        ctx = {"run_id": "test", "step": code, "water_body": "balkhash",
               "params": {**manifest_defaults(code), **(params or {})}, "species_names": sp, "gear_kinds": gk,
               "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()}, "tables_path": str(tmp_path / "tables.json")}
        executor.prepare_step(d, PKG[code], ctx)
        st = executor.run_step(d, timeout_s=900)
        assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-2000:])
        return d, executor.read_result(d)

    general = {k: v for k, v in asdict(bc.SpeciesConfig()).items() if k in bc.EDITABLE}
    da, _ = step_wb("net_catchability")
    db, _ = step_wb("seine_catchability")
    dc, _ = step_wb("seine_likelihood", {"seine_catchability": db})
    dd, _ = step_wb("net_likelihood", {"net_catchability": da})
    de, _ = step_wb("seine_stock", {"seine_likelihood": dc})
    df, _ = step_wb("net_stock", {"net_likelihood": dd})
    dg, _ = step_wb("combined_stock", {"seine_stock": de, "net_stock": df})
    d3, _ = step_wb("pdu_by_age", {"combined_stock": dg})
    d4, r4 = step_wb("bayes_cohort", {"seine_likelihood": dc, "net_likelihood": dd, "combined_stock": dg, "pdu_by_age": d3},
                     {"mode": "prior", "species_profiles": {"zherekh": general, "som": general}})
    assert set(r4["payload"]["species"]) == {"жерех", "сом"}
    names = {f["name"] for f in r4["files"]}
    assert {"balkhash_bayes_zherekh_prior.npz", "balkhash_bayes_som_prior.npz"} <= names, names
