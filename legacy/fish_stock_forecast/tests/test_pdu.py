"""
Тесты распределения ПДУ по возрастам (раздел 5 статьи).

Запуск:  python -m tests.test_pdu
"""
import numpy as np

from core import config
from core.pdu_npc import distribute_pdu

AGES = np.arange(2, 12, dtype=float)          # возрасты j = 2..11 (от 1–2 до 10–11 лет)
M1, M0 = 11, 4
MATURE = AGES >= M0
STOCK = 1e6 * np.exp(-0.3 * (AGES - 2))       # штук
WEIGHT = 50.0 * (AGES - 1) ** 1.5             # г


def test_small_quota_one_iteration():
    """Квота мала — распределяется за одну итерацию пропорционально X·w·j/m1."""
    biomass = (STOCK * WEIGHT * MATURE).sum()
    P = 0.05 * biomass
    r = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, P)
    assert r.iterations == 1 and r.stop_reason == "квота исчерпана"
    assert np.isclose((r.pieces * WEIGHT).sum(), P)
    bt = STOCK * WEIGHT * MATURE * AGES / M1
    assert np.allclose(r.pieces * WEIGHT, P * bt / bt.sum())
    assert np.all(r.pieces[~MATURE] == 0)                     # неполовозрелые не ловятся
    # доля изъятия растёт с возрастом (линейная функция нагрузки)
    expl = r.pieces[MATURE] / STOCK[MATURE]
    assert np.all(np.diff(expl) > 0)


def test_cap_and_redistribution():
    """Квота большая: ограничение 75 % срабатывает, остаток переходит на другие возрасты."""
    biomass = (STOCK * WEIGHT * MATURE).sum()
    P = 0.6 * biomass
    r = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, P)
    assert r.capped.any()
    assert r.iterations > 1
    assert np.isclose((r.pieces * WEIGHT).sum() + r.left_g, P, rtol=1e-9)
    assert r.stop_reason == "квота исчерпана" and r.left_g < config.PDU_TOL_G
    assert np.all(r.pieces <= STOCK + 1e-6)


def test_quota_larger_than_stock():
    """Квота больше всей промысловой биомассы: вылавливается почти всё, остаток показывается."""
    biomass = (STOCK * WEIGHT * MATURE).sum()
    P = 2.0 * biomass
    r = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, P)
    assert r.stop_reason == "нет свободного запаса"
    assert np.isclose(r.left_g, P - biomass, rtol=1e-6)
    assert np.allclose(r.pieces[MATURE], STOCK[MATURE], rtol=1e-6)


def test_three_iterations_like_old_code():
    """С пределом в 3 итерации (как в статье и старом коде) остаётся нераспределённая часть."""
    biomass = (STOCK * WEIGHT * MATURE).sum()
    P = 0.99 * biomass
    r3 = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, P, max_iter=3)
    r = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, P)
    assert r3.iterations == 3 and r3.stop_reason == "предел итераций"
    assert r3.left_g > 0.01 * biomass and r.left_g < config.PDU_TOL_G


def test_zero_weight_age_excluded_and_no_quota():
    w = WEIGHT.copy(); w[-1] = 0.0
    r = distribute_pdu(STOCK, w, MATURE, AGES, M1, 1e6)
    assert r.pieces[-1] == 0
    r0 = distribute_pdu(STOCK, WEIGHT, MATURE, AGES, M1, 0.0)
    assert r0.stop_reason == "нет квоты" and r0.pieces.sum() == 0


def test_real_data_if_available():
    if not (config.DATA_CATCH_DIR / f"{config.WATERBODY}_fish_prop.py").exists():
        print("  (исходные данные не найдены — тест пропущен)")
        return
    from core.data_source import load_fish_props
    from core.pdu_npc import compute_pdu
    from core.stock import compute_stock
    res, _, _ = compute_stock()
    props = load_fish_props()
    p = compute_pdu(res, props)
    dist = p.distributed_t()
    ok = np.isfinite(p.pdu_t)
    assert np.allclose(dist[ok] + p.left_t[ok], p.pdu_t[ok], rtol=1e-9, atol=1e-6)
    # язь: вес возраста 12–13 взят от возраста 11–12
    si = p.species.index("язь")
    j13 = int(np.where(p.ages == 13)[0][0])
    assert p.weight_filled[si, j13]
    assert np.allclose(p.weights[:, si, j13], p.weights[:, si, j13 - 1])
    # неполовозрелые возрасты не ловятся
    for si, fish in enumerate(p.species):
        young = p.ages < props.m0[fish]
        assert np.all(p.pieces[:, si, young] == 0)


if __name__ == "__main__":
    import sys
    import warnings
    warnings.filterwarnings("ignore")
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK    {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed} из {len(tests)} тестов пройдено")
    sys.exit(1 if failed else 0)
