"""
Сверка расчётного ядра FishStock (algorithms/fishcore + наборы данных из сервиса «Входные данные»)
с исходным проектом (legacy/fish_stock_forecast/core + legacy/data_catch/*.py) и его сохранёнными результатами.
Допуск — 1e-6 (относительный), этапы 1–3 детерминированы.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import H, REPO

sys.path.insert(0, str(REPO / "algorithms"))
os.environ["FISH_SOURCE_DIR"] = str(REPO / "legacy")
sys.path.insert(0, str(REPO / "legacy" / "fish_stock_forecast"))

TYPES = ["catches", "age_samples", "mean_weights", "species_props", "yearly_conditions", "npc_stock", "npc_pdu"]


@pytest.fixture()
def bundle(data_stack):
    from fishcore.bundle import Bundle
    dm, da, _ = data_stack
    tables = {}
    for t in TYPES:
        r = da.post("/upload", headers=H("ichthyologist"), data={"water_body": "zhaysan", "dataset_type": t},
                    files={"file": (f"{t}.xlsx", (REPO / "samples" / "zhaysan" / f"{t}.xlsx").read_bytes())}).json()
        assert r["ok"], r["errors"][:3]
        tables[t] = da.get(f"/datasets/{r['dataset']['id']}/data", headers=H()).json()["table"]
    sp = {r["values"]["code"]: r["values"]["name_ru"] for r in dm.get("/entities/species/records", headers=H()).json()}
    gk = {r["values"]["code"]: r["values"]["kind"] for r in dm.get("/entities/gears/records", headers=H()).json()}
    return Bundle("zhaysan", tables, sp, gk)


LEGACY_CATCH_TYPE = {"научный": "scientific", "промысловый": "commercial"}


def _close(a, b, what, rtol=1e-6):
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape, (what, a.shape, b.shape)
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"{what}: пропуски не совпадают"
    m = ~np.isnan(a)
    assert np.allclose(a[m], b[m], rtol=rtol, atol=1e-9), f"{what}: max |Δ| = {np.max(np.abs(a[m] - b[m]))}"


def test_inputs_identical(bundle):
    from core import data_source as old
    from fishcore import data_source as new
    po, pn = old.load_fish_props("zhaysan"), new.load_fish_props("zhaysan", bundle)
    for k in ("lake_area_km2", "net_hours", "net_length", "m0", "m1", "m2", "is_predator", "fecundity", "fry_density"):
        o, n = getattr(po, k), getattr(pn, k)
        if k in ("m0", "m1", "m2", "is_predator", "fecundity", "fry_density"):
            o = {s: o[s] for s in po.species}
        assert {s: o[s] for s in o} == {s: n[s] for s in o}, k
    for k in ("cruise_speed", "k_net", "k_seine"):
        assert {s: getattr(po, k)[s] for s in po.species} == getattr(pn, k), k
    assert po.species == pn.species
    for s, w in po.weights.items():
        _close(w.values, pn.weights[s].loc[w.index, w.columns].values, f"вес {s}")
    assert old.list_catch_years("zhaysan") == new.list_catch_years("zhaysan", bundle)
    for y in old.list_catch_years("zhaysan"):
        co, so = old.load_year(y, "zhaysan")
        cn, sn = new.load_year(y, "zhaysan", bundle)
        assert list(co.columns[:7]) == list(cn.columns[:7]) and set(co.columns) == set(cn.columns), y
        for c in co.columns:
            if c == "Instrument_raw":  # исходное название орудия в файле — справочно, в расчёте не участвует
                continue
            if c == "CatchType":     # с 21.10.2026 — коды справочника «Типы вылова» вместо слов
                assert [LEGACY_CATCH_TYPE.get(x, x) for x in co[c]] == cn[c].tolist(), (y, c)
            elif not pd.api.types.is_numeric_dtype(co[c]):
                assert co[c].tolist() == cn[c].tolist(), (y, c)
            else:
                _close(co[c].values, cn[c].values, f"{y} {c}")
        assert set(so.columns) == set(sn.columns) and list(so.index) == list(sn.index)
        _close(so.values, sn[so.columns].values, f"проба {y}")
    so, po_ = old.load_npc("zhaysan")
    sn, pn_ = new.load_npc("zhaysan", bundle)
    _close(so.values, sn.loc[so.index, so.columns].values, "запас НПЦ")
    _close(po_.values, pn_.loc[po_.index, po_.columns].values, "ПДУ НПЦ")


def test_stages_identical(bundle):
    from core.catchability_seine import compute_seine_catchability as s_old
    from core.stock import compute_stock as st_old, GEARS, VARIANTS, METHODS, MEAN
    from core.pdu_npc import compute_pdu as p_old
    from core.data_source import load_fish_props as lp_old
    from fishcore.catchability_seine import compute_seine_catchability as s_new
    from fishcore.stock import compute_stock as st_new
    from fishcore.pdu_npc import compute_pdu as p_new
    from fishcore.data_source import load_fish_props as lp_new

    a, b = s_old("zhaysan"), s_new("zhaysan", bundle)
    _close(a.cube(), b.cube(), "уловистость невода")
    ro, no, _ = st_old("zhaysan", seine_c=a)
    rn, nn, _ = st_new("zhaysan", bundle, seine_c=b)
    _close(no.cube(), nn.cube(), "уловистость сети")
    for k in ro.per_haul:
        _close(ro.per_haul[k], rn.per_haul[k], f"запас по ловам {k}")
    for k in ro.yearly:
        _close(ro.yearly[k], rn.yearly[k], f"годовой запас {k}")
    _close(ro.npc_stock, rn.npc_stock, "НПЦ")
    po = p_old(ro, lp_old("zhaysan"))
    pn = p_new(rn, lp_new("zhaysan", bundle), data_dir=bundle)
    _close(po.pieces, pn.pieces, "ПДУ по возрастам")
    _close(po.pdu_t, pn.pdu_t, "ПДУ НПЦ, т")


def test_matches_saved_results(bundle, tmp_path):
    """Контрольный пример: результаты этапов 1–3 совпадают с файлами эталона
    (legacy/fish_stock_forecast/results, эталон 22.10.2026, см. legacy/ETALON.md)."""
    xr = pytest.importorskip("xarray")
    from fishcore import config as fc
    from fishcore.catchability_seine import compute_seine_catchability, save_results
    from fishcore.export_nc import save_pdu, save_stage2
    from fishcore.pdu_npc import compute_pdu
    from fishcore.stock import compute_stock
    from fishcore.data_source import load_fish_props
    seine = compute_seine_catchability("zhaysan", bundle)
    save_results(seine, tmp_path)
    res, net_c, _ = compute_stock("zhaysan", bundle, seine_c=seine)
    save_stage2(res, net_c, tmp_path)
    save_pdu(compute_pdu(res, load_fish_props("zhaysan", bundle), data_dir=bundle), tmp_path)
    ref = REPO / "legacy" / "fish_stock_forecast" / "results"
    checked = 0
    for f in sorted(ref.glob("zhaysan_*.nc")):
        if "_bayes_" in f.name or "_mean_" in f.name:
            continue
        mine = tmp_path / f.name
        assert mine.exists(), f.name
        with xr.open_dataset(f) as dr, xr.open_dataset(mine) as dn:
            for v in dr.data_vars:
                # подгонка сигмоиды невода (scipy.optimize) на другой версии scipy отличается в 6-м знаке
                _close(dr[v].values, dn[v].values, f"{f.name}:{v}", rtol=1e-5)
                checked += 1
    assert checked >= 20
