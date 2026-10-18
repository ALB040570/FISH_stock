"""
Тесты МНК-расчёта уловистости невода.

Запуск:  python -m pytest tests          (если установлен pytest)
   или:  python -m tests.test_catchability_seine
"""
import numpy as np

from core import config
from core.catchability_seine import (
    _b_and_edges, _log_sigmoid, _profile_kz, compute_seine_catchability, fit_sigmoid_catch_curve,
)


def _synthetic(a, j50, Z, c_mean, ages, n0=1e6):
    sig = 1.0 / (1.0 + np.exp(-a * (ages - j50)))
    b = c_mean * ages.size / sig.sum()
    catch = n0 * np.exp(-Z * ages) * b * sig
    return catch, b * sig


def test_recovers_known_parameters():
    """Без шума и с неактивными ограничениями МНК восстанавливает a, j50, Z и c."""
    ages = np.arange(2, 13, dtype=float)
    catch, c_true = _synthetic(a=0.8, j50=3.5, Z=0.4, c_mean=0.4, ages=ages)
    fit = fit_sigmoid_catch_curve(ages, catch, weights=np.full(ages.size, 100.0), c_mean=0.4)
    assert abs(fit.a - 0.8) < 1e-3, fit.a
    assert abs(fit.j50 - 3.5) < 1e-3, fit.j50
    assert abs(fit.Z - 0.4) < 1e-4, fit.Z
    assert np.allclose(fit.catchability(ages), c_true, atol=1e-4)
    assert fit.r2 > 0.999999
    assert not fit.lower_active and not fit.upper_active


def test_constraints_hold_when_active():
    """Если истинная уловистость группы 3 < 0.1, решение ложится на границу c(3) = 0.1;
    двухлетки при этом ограничены только снизу 0.01."""
    ages = np.arange(2, 13, dtype=float)
    catch, c_true = _synthetic(a=1.5, j50=4.0, Z=0.4, c_mean=0.4, ages=ages)
    assert c_true[1] < 0.1 and c_true[0] > 0.01
    fit = fit_sigmoid_catch_curve(ages, catch, weights=np.full(ages.size, 100.0), c_mean=0.4)
    c = fit.catchability(ages)
    assert c[0] >= 0.01 - 1e-6 and c[1] >= 0.1 - 1e-6 and c[-1] <= 0.8 + 1e-6
    assert abs(c.mean() - 0.4) < 1e-9
    assert fit.lower_active and not fit.first_lower_active


def test_age2_bound_active():
    """Очень крутая сигмоида: уловистость двухлеток упирается в 0.01."""
    ages = np.arange(2, 13, dtype=float)
    catch, c_true = _synthetic(a=5.0, j50=2.8, Z=0.4, c_mean=0.4, ages=ages)
    assert c_true[0] < 0.01 and c_true[1] > 0.1
    fit = fit_sigmoid_catch_curve(ages, catch, weights=np.full(ages.size, 100.0), c_mean=0.4)
    c = fit.catchability(ages)
    assert c[0] >= 0.01 - 1e-6 and c[1] >= 0.1 - 1e-6
    assert fit.first_lower_active


def test_mean_condition_and_monotonicity_random():
    rng = np.random.default_rng(1)
    for _ in range(25):
        m1 = int(rng.integers(8, 17))
        ages = np.arange(2, m1 + 1, dtype=float)
        c_mean = float(rng.choice([0.4, 0.6]))
        catch, _ = _synthetic(rng.uniform(0.2, 3), rng.uniform(1.5, 7), rng.uniform(0.05, 0.8), c_mean, ages)
        catch = catch * rng.lognormal(0, 0.3, ages.size)
        fit = fit_sigmoid_catch_curve(ages, catch, rng.uniform(1, 200, ages.size), c_mean)
        c = fit.catchability(ages)
        assert abs(c.mean() - c_mean) < 1e-9                        # условие (25)
        assert c[0] >= 0.01 - 1e-6 and c[1:].min() >= 0.1 - 1e-6       # условие (26),
        assert c.max() <= 0.8 + 1e-6                                   # двухлетки от 0.01
        assert np.all(np.diff(c) >= -1e-12)                          # сигмоида не убывает


def test_is_global_minimum_against_dense_search():
    """Решение не хуже плотного перебора по допустимой области."""
    rng = np.random.default_rng(7)
    ages = np.arange(2, 12, dtype=float)
    catch, _ = _synthetic(1.2, 3.2, 0.5, 0.4, ages)
    catch = catch * rng.lognormal(0, 0.4, ages.size)
    w = rng.uniform(5, 100, ages.size)
    fit = fit_sigmoid_catch_curve(ages, catch, w, 0.4)

    A, J = np.meshgrid(np.geomspace(0.05, 8, 400), np.linspace(1, 11, 800), indexing="ij")
    _, _, sse = _profile_kz(np.log(catch) - _log_sigmoid(A[..., None], J[..., None], ages), ages, w)
    _, first, second, hi = _b_and_edges(A, J, ages, 0.4)
    brute = np.where((first >= 0.01) & (second >= 0.1) & (hi <= 0.8), sse, np.inf).min()
    assert fit.sse <= brute + 1e-6, (fit.sse, brute)


def test_real_data_if_available():
    """Проверки на данных Жайсана (пропускается, если исходного проекта нет рядом)."""
    if not (config.DATA_CATCH_DIR / f"{config.WATERBODY}_fish_prop.py").exists():
        print("  (исходные данные не найдены — тест пропущен)")
        return
    res = compute_seine_catchability()
    assert len(res.fits) == len(res.years) * len(res.species)
    lesh_2015 = res.fits[("лещ", 2015)]
    assert lesh_2015.total_catch == 6770                               # улов неводом, из исходных данных
    for (fish, year), r in res.fits.items():
        c = r.catchability
        assert abs(c.mean() - r.c_mean) < 1e-9, (fish, year)
        assert c[0] >= 0.01 - 1e-6 and c[1:].min() >= 0.1 - 1e-6 and c.max() <= 0.8 + 1e-6, (fish, year)
        assert r.ages[0] == 2 and r.ages[-1] == r.m1
        assert r.fit.optimizer_ok, (fish, year)
    cube = res.cube()
    assert cube.shape == (len(res.years), len(res.species), len(res.all_ages))
    # возрасты старше m1 — нули, как в старом кубе
    for si, fish in enumerate(res.species):
        older = res.all_ages > res.fits[(fish, res.years[0])].m1
        assert np.all(cube[:, si, older] == 0)


if __name__ == "__main__":
    import sys
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
