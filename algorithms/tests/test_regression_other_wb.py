"""
Сверка этапов 1–3 по водоёмам из данных заказчика от 20.10.2026 (Балхаш, Капчагай): ядро FishStock на наборах
данных из сервиса «Входные данные» = исходное ядро legacy/fish_stock_forecast/core на legacy/data_catch/*.py.

Известное отличие данных (исправлено при переносе, docs/data_import_2026-10-20.md): в kapchagay_catch_2019.py
возрастная проба записана как «беламур»/«толстолоб», а в остальных файлах — «б_амур»/«т_лоб». Исходный код считает
это другими видами и пробу 2019 г. для белого амура и толстолобика не видит; при переносе написания объединены.
Проба 2019 г. влияет на подгонку уловистости невода этих видов во все годы, поэтому эти два вида в сверку не входят;
для них отдельно проверено, что проба 2019 г. учтена. Остальные 8 видов Капчагая и все виды Балхаша — совпадение.
Самаркандское вдхр. (только сети) исходным кодом не считается — проверяется только выполнение (test_net_only).
"""
import os
import sys

import numpy as np
import pytest

from conftest import H, REPO

sys.path.insert(0, str(REPO / "algorithms"))
os.environ["FISH_SOURCE_DIR"] = str(REPO / "legacy")
sys.path.insert(0, str(REPO / "legacy" / "fish_stock_forecast"))

TYPES = ["catches", "age_samples", "mean_weights", "species_props", "yearly_conditions", "npc_stock", "npc_pdu"]
CASES = [("balkhash", "balkhash"), ("kapchagay", "kapshagay")]     # (имя в исходных файлах, код водоёма)


def make_bundle(data_stack, legacy_name, code):
    from fishcore.bundle import Bundle
    dm, da, _ = data_stack
    tables = {}
    for t in TYPES:
        r = da.post("/upload", headers=H("ichthyologist"), data={"water_body": code, "dataset_type": t},
                    files={"file": (f"{t}.xlsx", (REPO / "samples" / code / f"{t}.xlsx").read_bytes())}).json()
        assert r["ok"], r["errors"][:3]
        tables[t] = da.get(f"/datasets/{r['dataset']['id']}/data", headers=H()).json()["table"]
    sp = {r["values"]["code"]: r["values"]["name_ru"] for r in dm.get("/entities/species/records", headers=H()).json()}
    gk = {r["values"]["code"]: r["values"]["kind"] for r in dm.get("/entities/gears/records", headers=H()).json()}
    return Bundle(legacy_name, tables, sp, gk)


def _mask(years, species, legacy_name, shape):
    """True — клетки, которые сверяются (оси: годы, виды, ...)."""
    m = np.ones(shape, bool)
    if legacy_name == "kapchagay":
        # проба 2019 г. меняет подгонку уловистости невода этих видов и в другие годы — вид исключается целиком
        for s in ("т_лоб", "б_амур"):
            m[:, species.index(s)] = False
    return m


def _close(a, b, what, mask=None, rtol=1e-6):
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape, (what, a.shape, b.shape)
    if mask is not None:
        a, b = np.where(mask, a, 0.0), np.where(mask, b, 0.0)
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"{what}: пропуски не совпадают"
    m = ~np.isnan(a)
    assert np.allclose(a[m], b[m], rtol=rtol, atol=1e-9), f"{what}: max |Δ| = {np.max(np.abs(a[m] - b[m]))}"


@pytest.mark.parametrize("legacy_name,code", CASES)
def test_stages_identical(data_stack, legacy_name, code):
    from core.catchability_seine import compute_seine_catchability as s_old
    from core.stock import compute_stock as st_old
    from core.pdu_npc import compute_pdu as p_old
    from core.data_source import load_fish_props as lp_old
    from fishcore.catchability_seine import compute_seine_catchability as s_new
    from fishcore.stock import compute_stock as st_new
    from fishcore.pdu_npc import compute_pdu as p_new
    from fishcore.data_source import load_fish_props as lp_new

    bundle = make_bundle(data_stack, legacy_name, code)
    a, b = s_old(legacy_name), s_new(legacy_name, bundle)
    ro, no, _ = st_old(legacy_name, seine_c=a)
    rn, nn, _ = st_new(legacy_name, bundle, seine_c=b)
    years, species = list(ro.years), list(ro.species)
    assert years == list(rn.years) and len(species) == len(rn.species)
    m3 = _mask(years, species, legacy_name, ro.yearly[next(iter(ro.yearly))].shape)
    _close(a.cube(), b.cube(), "уловистость невода", m3)
    _close(no.cube(), nn.cube(), "уловистость сети", m3)
    for k in ro.yearly:
        _close(ro.yearly[k], rn.yearly[k], f"годовой запас {k}", m3)
    _close(ro.npc_stock, rn.npc_stock, "НПЦ")
    m_sp = m3[0, :, 0]                                    # сверяемые виды
    po = p_old(ro, lp_old(legacy_name))
    pn = p_new(rn, lp_new(legacy_name, bundle), data_dir=bundle)
    _close(np.asarray(po.pieces)[:, m_sp], np.asarray(pn.pieces)[:, m_sp], "ПДУ по возрастам")
    _close(np.asarray(po.pdu_t)[:, m_sp], np.asarray(pn.pdu_t)[:, m_sp], "ПДУ НПЦ, т")
    if legacy_name == "kapchagay":
        # проба 2019 г. для белого амура и толстолобика учтена только в FishStock
        yi = years.index(2019)
        for s in ("т_лоб", "б_амур"):
            si = species.index(s)
            assert ro.catches["сеть"].sample_raw[yi, si].sum() == 0
            assert rn.catches["сеть"].sample_raw[yi, si].sum() > 0


def test_net_only(data_stack):
    """Самаркандское вдхр.: ловов неводом нет — окончательный запас равен оценке по сетям."""
    from fishcore.catchability_seine import compute_seine_catchability
    from fishcore.stock import compute_stock, MEAN
    bundle = make_bundle(data_stack, "samarkand", "samarkand")
    res, _, _ = compute_stock("samarkand", bundle, seine_c=compute_seine_catchability("samarkand", bundle))
    assert len(res.catches["невод"].meta) == 0 and len(res.catches["сеть"].meta) == 10
    for v in ("with_ages", "out_ages"):
        net, fin = res.yearly[("сеть", v, "on_stock")], res.yearly[(MEAN, v, "on_stock")]
        assert np.allclose(np.nan_to_num(net), np.nan_to_num(fin))
        assert np.nansum(fin) > 0

