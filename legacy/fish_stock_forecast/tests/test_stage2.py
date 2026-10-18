"""
Тесты этапа 2: модель баланса, уловистость сети (парабола), запас по уловам.

Запуск:  python -m tests.test_stage2
"""
import numpy as np

from core import config
from core.catchability_net import fit_parabola
from core.net_model import balance_model, net_share, stock_from_net_catch

# Таблица 9 статьи (доли рыб первого круга): час -> [Сеть, Круг 0, Кольцо 1..4]
TABLE_9 = {
    0: [0.00, 0.03, 0.97, 3.00, 5.00, 7.00],
    1: [0.00, 0.09, 0.99, 2.91, 5.00, 7.00],
    2: [0.01, 0.13, 1.00, 2.88, 4.97, 7.00],
    6: [0.08, 0.20, 1.04, 2.85, 4.90, 6.95],
    12: [0.21, 0.22, 1.06, 2.85, 4.86, 6.90],
}


def test_balance_model_reproduces_table_9():
    """k = 0.4, 12 ч, сеть 25 м, V = 72 м/ч (в тексте статьи указано 400 м/ч — опечатка)."""
    df, _ = balance_model(0.4, 12, 25, 72)
    cols = ["Сеть", "Круг 0", "Кольцо 1", "Кольцо 2", "Кольцо 3", "Кольцо 4"]
    for hour, expected in TABLE_9.items():
        got = df.loc[df["Час"] == hour, cols].to_numpy()[0]
        assert np.allclose(got, expected, atol=0.006), (hour, got.round(3), expected)


def test_balance_conserves_fish():
    df, _ = balance_model(0.3, 12, 25, 180)
    assert np.allclose(df["Баланс"], df["Баланс"].iloc[0], atol=1e-9)


def test_balance_model_rejects_short_path():
    try:
        balance_model(0.4, 12, 25, 10)
    except ValueError:
        return
    raise AssertionError("должна быть ошибка: половина длины сети больше пути рыбы за час")


def test_net_stock_formulas():
    sigma = net_share(0.4, 12, 25, 72)
    # как в старом коде calc_stock_net: X = Y·S / (σ·(V² − r0²))
    x = stock_from_net_catch(np.array([10.0, 0.0, np.nan]), np.array([0.4, 0.4, 0.4]), 12, 25, 72, 1e6, formula="code")
    assert np.isclose(x[0], 10 * 1e6 / (sigma * (72 ** 2 - 12.5 ** 2)))
    # формула (28) статьи
    x28 = stock_from_net_catch(np.array([10.0]), np.array([0.4]), 12, 25, 72, 1e6, formula="article")
    assert np.isclose(x28[0], 10 * 1e6 / (np.pi * 72 ** 2 * sigma))
    assert x[1] == 0 and np.isnan(x[2])
    assert stock_from_net_catch(np.array([5.0]), np.array([0.0]), 12, 25, 72, 1e6)[0] == 0  # c = 0 → 0


def test_parabola_follows_article():
    ages = np.arange(2, 17, dtype=float)
    observed = np.exp(-0.3 * (ages - 5) ** 2)          # пик улова в группе 5
    p = fit_parabola(ages, observed, m0=4, c_mean=0.3)
    assert p.peak == 5
    assert np.isclose(p.a1, (0.3 - 0.1) / (2 - 5) ** 2)
    assert np.isclose(p.a2, (0.3 - 0.2) / (16 - 5) ** 2)
    c = p.value(ages)
    assert np.isclose(c.mean(), 0.3)                    # (23)
    assert c.min() >= 0.1 and c.max() <= 0.8            # (24)
    assert np.argmax(c) == 3                            # вершина в группе 5
    # вершина не раньше m0 + 1
    p2 = fit_parabola(ages, np.exp(-(ages - 2) ** 2), m0=4, c_mean=0.3)
    assert p2.peak == 5


def test_parabola_peak_at_last_age():
    ages = np.arange(2, 11, dtype=float)
    p = fit_parabola(ages, ages ** 2, m0=3, c_mean=0.4)
    assert p.peak == 10 and p.a2 == 0
    assert np.isclose(p.value(ages).mean(), 0.4)


def test_real_data_if_available():
    if not (config.DATA_CATCH_DIR / f"{config.WATERBODY}_fish_prop.py").exists():
        print("  (исходные данные не найдены — тест пропущен)")
        return
    from core.stock import MEAN, compute_stock

    res, net_c, seine_c = compute_stock()
    area = {y: a * config.KM2_M2 for y, a in __import__("core.data_source", fromlist=["x"]).load_fish_props().lake_area_km2.items()}

    # улов невода по годам совпадает с этапом 1
    ys = res.catches[config.GEAR_SEINE].yearly_sum()
    for (fish, year), r in seine_c.fits.items():
        if r.source.startswith("годовой улов"):
            yi, si = res.years.index(year), res.species.index(fish)
            mask = (res.ages >= 2) & (res.ages <= r.m1)
            assert np.allclose(ys[yi, si, mask], r.observed)

    # формула (27) для конкретного лова
    hc = res.catches[config.GEAR_SEINE]
    d = int(np.argmax(np.nan_to_num(hc.totals()[:, 0])))           # лов с наибольшим уловом леща
    year = int(hc.meta["Year"].iloc[d]); yi = res.years.index(year)
    s_area = hc.meta["Area"].iloc[d] * config.HECTARE_M2
    c = res.catchability[(config.GEAR_SEINE, "with_ages")][yi, 0, 3]
    expected = hc.values[d, 0, 3] * area[year] / (c * s_area)
    assert np.isclose(res.per_haul[(config.GEAR_SEINE, "with_ages")][d, 0, 3], expected)

    # сеть: при одинаковой σ внутри года оценка «по запасам» = «по улову» (формула линейна)
    for v in ("with_ages", "out_ages"):
        a = res.yearly[(config.GEAR_NET, v, "on_stock")]
        b = res.yearly[(config.GEAR_NET, v, "on_catch")]
        assert np.allclose(a, b, equal_nan=True)

    # окончательный запас по возрастам — средневзвешенное сети и невода по числу ловов
    a = res.yearly[(config.GEAR_NET, "with_ages", "on_stock")]
    b = res.yearly[(config.GEAR_SEINE, "with_ages", "on_stock")]
    m = res.yearly[(MEAN, "with_ages", "on_stock")]
    n1 = res.catches[config.GEAR_NET].yearly_count()[..., None]
    n2 = res.catches[config.GEAR_SEINE].yearly_count()[..., None]
    n1, n2 = np.broadcast_to(n1, a.shape), np.broadcast_to(n2, a.shape)
    both = ~np.isnan(a) & ~np.isnan(b) & (n1 > 0) & (n2 > 0)
    assert np.allclose(m[both], (n1[both] * a[both] + n2[both] * b[both]) / (n1[both] + n2[both]))
    # суммарный запас = сумма окончательных запасов по возрастам
    tot = res.combined_total("with_ages", "on_stock")
    si = 0
    ages_ok = (res.ages >= 2) & (res.ages <= res.m1[res.species[si]])
    assert np.allclose(tot[:, si], np.nansum(m[:, si, ages_ok], axis=1))

    # «по запасам» = среднее оценок по ловам, где вид учитывался
    per = res.per_haul[(config.GEAR_SEINE, "with_ages")]
    sel = (hc.meta["Year"] == 2020).to_numpy()
    vals = per[sel, 0, 3]
    assert np.isclose(res.yearly[(config.GEAR_SEINE, "with_ages", "on_stock")][res.years.index(2020), 0, 3],
                      np.nanmean(vals))
    # нарушений ограничений (24) для сети нет
    assert all(not r.violations for r in net_c.fits.values())


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
