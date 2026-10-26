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


def test_forecast_k_scenarios(env):
    """Сценарный анализ k (3.1.0): каждый k — сценарий F = k·M на тех же выборках; основной сценарий не меняется."""
    from fishcore.forecast import parse_k_grid
    assert parse_k_grid("1,5; 0,5;1; 1") == (0.5, 1.0, 1.5) and parse_k_grid("") == () and parse_k_grid(None) == ()
    assert parse_k_grid("0; 2") == (0.0, 2.0)
    for bad in ("0,5; abc", "-0,5", "11", "; ".join(str(x) for x in range(1, 11))):
        with pytest.raises(ValueError):
            parse_k_grid(bad)
    tmp, sp, gk = env
    fake = tmp / "bayes_k" / "out"
    fake.mkdir(parents=True)
    shutil.copy(REPO / "legacy" / "fish_stock_forecast" / "results" / "zhaysan_bayes_sudak.npz", fake)
    base = {"horizon": 3, "k": 1.0}
    _, r0 = step(tmp, sp, gk, "forecast_pdu", {"bayes_cohort": tmp / "bayes_k"}, {**base, "k_scenarios": "1"})
    _, r1 = step(tmp, sp, gk, "forecast_pdu", {"bayes_cohort": tmp / "bayes_k"}, {**base, "k_scenarios": "0,5; 1; 1,5"})
    _, rz = step(tmp, sp, gk, "forecast_pdu", {"bayes_cohort": tmp / "bayes_k"}, {**base, "k_scenarios": "0; 1"})
    kz = rz["payload"]["species"]["судак"]
    assert kz["k_scen"]["k"] == [0.0, 1.0] and kz["k_scen"]["pdu_t_q"][0] == [0, 0, 0, 0, 0]       # k = 0 — без промысла
    assert np.isclose(kz["k_scen"]["p_decline"][0], kz["scenarios"]["none"]["p_decline"])
    # запас по годам для каждого k: k = 0 совпадает с «без промысла», k = 1 — с F = k·M
    ty = kz["k_scen"]["total_q_years"]
    assert np.array(ty).shape == (2, 5, 3) and np.allclose(ty[0], kz["scenarios"]["none"]["total_q"]) and np.allclose(ty[1], kz["scenarios"]["baranov"]["total_q"])
    assert np.allclose(kz["k_scen"]["fishable_q_years"][1], kz["scenarios"]["baranov"]["fishable_q"])
    assert {r["k"] for r in rz["tables"]["k_years"]["rows"]} == {0.0, 1.0} and len(rz["tables"]["k_years"]["rows"]) == 2 * 3
    a, b = r0["payload"]["species"]["судак"], r1["payload"]["species"]["судак"]
    for sc in ("baranov", "fixed", "none"):           # сценарии не влияют на основной расчёт
        assert np.allclose(np.array(a["scenarios"][sc]["pdu_t_q"], float), np.array(b["scenarios"][sc]["pdu_t_q"], float))
    ks = b["k_scen"]
    assert ks["k"] == [0.5, 1.0, 1.5] and ks["base_k"] == 1.0
    med = [x[2] for x in ks["pdu_t_q"]]
    assert med[0] < med[1] < med[2]
    assert np.isclose(med[1], b["scenarios"]["baranov"]["pdu_t_q"][2][0])   # k = 1 — тот же сценарий F = k·M
    assert 0.4 < med[0] / med[1] < 0.6 and 1.3 < med[2] / med[1] < 1.6
    rows = r1["tables"]["k_scenarios"]["rows"]
    assert [r["k"] for r in rows] == [0.5, 1.0, 1.5] and np.isclose(rows[1]["pdu_pct_base"], 100)
    assert r1["payload"]["k_grid"] == [0.5, 1.0, 1.5]
    assert not any("npc" in k for k in ks)                      # с ПДУ НПЦ сценарии не сравниваются
    d = tmp / "k_bad"
    ctx = {"water_body": "zhaysan", "params": {**manifest_defaults("forecast_pdu"), **base, "k_scenarios": "0,5; x"},
           "species_names": sp, "gear_kinds": gk, "inputs": {"bayes_cohort": str(tmp / "bayes_k" / "out")},
           "tables_path": str(tmp / "tables.json")}
    executor.prepare_step(d, PKG["forecast_pdu"], ctx)
    st = executor.run_step(d, timeout_s=300)
    assert st["status"] == "failed" and "«Сценарии k»" in st["message"]


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


def test_species_m1_above_age_groups(data_stack, tmp_path):
    """Капчагай: у сома m1 = 26 больше старшей возрастной группы данных — вид не считается (заметка), остальные
    виды считаются; раньше весь расчёт модели завершался IndexError (25.10.2026). Априорная проверка — секунды."""
    from dataclasses import asdict
    from fishcore.bayes import config as bc
    dm, da, _ = data_stack
    tables = upload_samples(da, "kapshagay", REPO / "samples" / "kapshagay")
    (tmp_path / "tables.json").write_text(json.dumps(tables, ensure_ascii=False))
    sp, gk = dict_maps(dm)

    def step_wb(code, inputs=None, params=None):
        d = tmp_path / code
        ctx = {"run_id": "test", "step": code, "water_body": "kapshagay",
               "params": {**manifest_defaults(code), **(params or {})}, "species_names": sp, "gear_kinds": gk,
               "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()}, "tables_path": str(tmp_path / "tables.json")}
        executor.prepare_step(d, PKG[code], ctx)
        st = executor.run_step(d, timeout_s=900)
        assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-2000:])
        return d, executor.read_result(d)

    general = {k: v for k, v in asdict(bc.SpeciesConfig()).items() if k in bc.EDITABLE}
    da_, _ = step_wb("net_catchability")
    db, _ = step_wb("seine_catchability")
    dc, _ = step_wb("seine_likelihood", {"seine_catchability": db})
    dd, _ = step_wb("net_likelihood", {"net_catchability": da_})
    de, _ = step_wb("seine_stock", {"seine_likelihood": dc})
    df, _ = step_wb("net_stock", {"net_likelihood": dd})
    dg, _ = step_wb("combined_stock", {"seine_stock": de, "net_stock": df})
    d3, _ = step_wb("pdu_by_age", {"combined_stock": dg})
    _, r4 = step_wb("bayes_cohort", {"seine_likelihood": dc, "net_likelihood": dd, "combined_stock": dg, "pdu_by_age": d3},
                    {"mode": "prior", "species_profiles": {"zherekh": general, "som": general}})
    assert set(r4["payload"]["species"]) == {"жерех"}
    assert any("«сом» не рассчитан" in n and "m1 = 26" in n for n in r4["notes"]), r4["notes"]


def test_likelihood_gears_net_only(data_stack, tmp_path):
    """Самаркандское: ловов неводом нет — в профиле вида «Оценки запаса в правдоподобии: только сеть» (решение № 73):
    в правдоподобии только ловы сети, поправки q_net нет, начальный запас — по сети; «только невод» — понятная ошибка.
    По умолчанию («сеть и невод») модель та же, что раньше (q_net есть)."""
    import pickle
    from dataclasses import asdict, replace
    from fishcore.bayes import config as bc
    from fishcore.bayes.inputs import build_new_inputs
    from fishcore.bayes.model import build_model
    dm, da, _ = data_stack
    tables = upload_samples(da, "samarkand", REPO / "samples" / "samarkand")
    (tmp_path / "tables.json").write_text(json.dumps(tables, ensure_ascii=False))
    sp, gk = dict_maps(dm)

    def step_wb(code, inputs=None, params=None, name=None, ok=True):
        d = tmp_path / (name or code)
        ctx = {"run_id": "test", "step": code, "water_body": "samarkand",
               "params": {**manifest_defaults(code), **(params or {})}, "species_names": sp, "gear_kinds": gk,
               "inputs": {k: str(v / "out") for k, v in (inputs or {}).items()}, "tables_path": str(tmp_path / "tables.json")}
        executor.prepare_step(d, PKG[code], ctx)
        st = executor.run_step(d, timeout_s=900)
        if ok:
            assert st["status"] == "done", (st.get("message"), (d / "log.txt").read_text()[-2000:])
        return d, st, executor.read_result(d) if st["status"] == "done" else None

    karas = {k: v for k, v in asdict(bc.DEFAULTS["карась"]).items() if k in bc.EDITABLE}
    da_, *_ = step_wb("net_catchability")
    db, *_ = step_wb("seine_catchability")
    dc, *_ = step_wb("seine_likelihood", {"seine_catchability": db})
    dd, *_ = step_wb("net_likelihood", {"net_catchability": da_})
    de, *_ = step_wb("seine_stock", {"seine_likelihood": dc})
    df, *_ = step_wb("net_stock", {"net_likelihood": dd})
    dg, *_ = step_wb("combined_stock", {"seine_stock": de, "net_stock": df})
    d3, *_ = step_wb("pdu_by_age", {"combined_stock": dg})
    ins = {"seine_likelihood": dc, "net_likelihood": dd, "combined_stock": dg, "pdu_by_age": d3}
    d4, _, r4 = step_wb("bayes_cohort", ins, {"mode": "prior", "species_profiles": {"karas": {**karas, "likelihood_gears": "net"}}})
    assert set(r4["payload"]["species"]) == {"карась"}
    notes = r4["payload"]["species"]["карась"]["meta"]["notes"]
    assert any("только оценки по ловам: сеть" in n for n in notes) and any("начальный запас — по оценкам: сеть" in n for n in notes)
    _, st, _ = step_wb("bayes_cohort", ins, {"mode": "prior", "species_profiles": {"karas": {**karas, "likelihood_gears": "seine"}}},
                       name="bayes_seine", ok=False)
    assert st["status"] == "failed" and "только невод" in st["message"] and "ловов этим орудием" in st["message"]
    # модель: при «только сеть» нет log_q_net, все наблюдения — сеть, начальный запас = оценка сетью первого года
    with open(d4 / "out" / "state.pkl", "rb") as f:
        s = pickle.load(f)
    cfg = replace(bc.DEFAULTS["карась"], likelihood_gears="net")
    inp = build_new_inputs("карась", cfg, s["res"], s["pdu"], s["props"])
    assert set(np.asarray(inp.gear).tolist()) == {0}
    assert np.allclose(inp.consts.x0, np.maximum(np.nan_to_num(inp.yearly_net[0]), 1.0))
    names = {v.name for v in build_model(inp, cfg).free_RVs}
    assert "log_q_net" not in names and "s_base" in names
    inp2 = build_new_inputs("карась", bc.DEFAULTS["карась"], s["res"], s["pdu"], s["props"])
    assert "log_q_net" in {v.name for v in build_model(inp2, bc.DEFAULTS["карась"]).free_RVs}
    # подбор масштаба выживаемости икры (решение № 73): таблица «сейчас / подобрано», расчёт не может быть основным
    _, _, r5 = step_wb("bayes_cohort", ins, {"mode": "egg_scale", "species_profiles": {"karas": {**karas, "likelihood_gears": "net"}}},
                       name="bayes_egg")
    row = r5["tables"]["egg_scale_fit"]["rows"][0]
    assert row["species"] == "карась" and row["gears"] == "только сеть" and row["current"] == bc.DEFAULTS["карась"].egg_scale
    assert row["suggested"] and row["rmse_suggested"] < row["rmse_current"]
    assert r5["payload"]["not_main"] is True and r5["payload"]["species"] == {}
    # зарыбление (решение № 74): X₁(t) = естественное пополнение + φ · Z(t); без зарыбления числа те же
    from fishcore.bayes.dynamics import NumpyOps, prior_means, simulate
    cfg_s = replace(cfg, stocking="2015: 1000; 2017: 500")
    inp_s = build_new_inputs("карась", cfg_s, s["res"], s["pdu"], s["props"])
    yrs = [int(y) for y in inp_s.years]
    assert inp_s.consts.stock[yrs.index(2015)] == 1000 and inp_s.consts.stock[yrs.index(2016)] == 0
    assert any("зарыбление учтено" in n for n in inp_s.notes)
    p0 = prior_means(inp.consts, cfg)
    ps = {**prior_means(inp_s.consts, cfg_s)}
    assert abs(ps["stock_survival"] - 0.25) < 1e-12                    # мода Beta(3, 7)
    x_no = simulate(NumpyOps, p0, inp.consts, cfg)["X_estimated"]
    x_st = simulate(NumpyOps, ps, inp_s.consts, cfg_s)["X_estimated"]
    assert abs(x_st[0, 0] - x_no[0, 0] - 0.25 * 1000) < 1e-6 * max(1.0, x_no[0, 0])
    assert np.array_equal(simulate(NumpyOps, {**p0, "stock_survival": 0.0}, inp.consts, cfg)["X_estimated"], x_no)
    assert "stock_survival" in {v.name for v in build_model(inp_s, cfg_s).free_RVs}
    assert bc.validate("карась", {"stocking": "2015 = 1000"}) and not bc.validate("карась", {"stocking": "2015: 1 000; 2016: 2000"})
    from fishcore.bayes.calibrate import fit_egg_scale, trajectory
    f = fit_egg_scale(inp, cfg)
    assert f["suggested"] == row["suggested"] and len(f["traj_suggested"]) == len(inp.years)
    assert np.allclose(trajectory(inp, replace(cfg, egg_scale=f["suggested"])), f["traj_suggested"])
