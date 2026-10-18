"""
Коэффициенты уловистости невода: сигмоида по возрасту, параметры которой
находятся методом наименьших квадратов по годовым уловам.

Для каждого вида i и года t (индексы ниже опущены):

    уловистость         c_j = b / (1 + exp(-a (j - j50))),      j = 2..m1       (24)
    улов по возрастам   Y_j ≈ c_j · N_j,   N_j = N0 · exp(-Z j)
    в логарифмах        ln Y_j = K - Z j + ln σ_j,   σ_j = 1 / (1 + exp(-a (j - j50))),
                        K = ln N0 + ln b

    МНК:  min  Σ_j w_j (ln Y_j - K + Z j - ln σ_j)²   по a > 0, j50, Z >= 0, K
          веса w_j — число рыб возраста j в пробе (+1): дисперсия ln Y_j ≈ 1/n_j

    b не определяется по уловам (сливается с N0), его задаёт условие (25):
          (1/(m1-1)) Σ_{j=2..m1} c_j = c̄        c̄ — средний коэффициент уловистости невода
    ограничения (26):  c_j <= 0.8;  c_j >= 0.1 для j >= 3;  для двухлеток (группа 2,
          возраст от 1 до 2 лет) нижняя граница 0.01. Сигмоида возрастает, поэтому
          достаточно c_2 >= 0.01, c_3 >= 0.1 и c_m1 <= 0.8.

При фиксированных (a, j50) параметры K и Z находятся взвешенной линейной
регрессией в явном виде, поэтому численно ищутся только a и j50:
сначала перебором по сетке, затем уточнением SLSQP с ограничениями.

Возраст перегиба по правилу статьи  j50_rule = max(m0 + 1, argmax_j Y_j)
считается для сравнения.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config
from .ages import age_label
from .data_source import FishProps, YearlyCatchByAge, load_fish_props, yearly_catch_by_age

CUBE_NAME = "corrected_catchability_coefficient_seine"  # имя переменной как в старом .nc

A_BOUNDS = (0.05, 8.0)   # крутизна сигмоиды, 1/год
Z_BOUNDS = (0.0, 3.0)    # общая мгновенная смертность, 1/год


# ---------------------------------------------------------------------------
# Математическое ядро
# ---------------------------------------------------------------------------
def _log_sigmoid(a, j50, ages):
    """ln σ = -ln(1 + exp(-a (j - j50))), устойчиво к переполнению. Работает с массивами."""
    return -np.logaddexp(0.0, -a * (ages - j50))


def _profile_kz(t, ages, w):
    """Взвешенная регрессия t = K - Z·ages с ограничением Z в Z_BOUNDS.

    t может иметь лишние ведущие оси (сетка параметров); возраст — последняя ось.
    Возвращает K, Z, взвешенную сумму квадратов остатков.
    """
    W = w.sum()
    mx = (w * ages).sum() / W
    mt = (w * t).sum(axis=-1) / W
    dx = ages - mx
    sxx = (w * dx * dx).sum()
    sxt = (w * dx * (t - mt[..., None])).sum(axis=-1)
    Z = np.clip(-sxt / sxx, *Z_BOUNDS)
    K = mt + Z * mx
    resid = t - K[..., None] + Z[..., None] * ages
    sse = (w * resid * resid).sum(axis=-1)
    return K, Z, sse


def _b_and_edges(a, j50, ages, c_mean):
    """b из условия (25) и уловистость в группах 2, 3 и m1 (первая, вторая, последняя)."""
    sig = np.exp(_log_sigmoid(np.asarray(a)[..., None], np.asarray(j50)[..., None], ages))
    b = c_mean * ages.size / sig.sum(axis=-1)
    second = sig[..., 1] if ages.size > 1 else sig[..., 0]
    return b, b * sig[..., 0], b * second, b * sig[..., -1]


@dataclass
class SigmoidFit:
    a: float
    j50: float
    b: float
    Z: float
    K: float
    sse: float
    r2: float
    first_lower_active: bool  # c_2 (двухлетки) упёрлось в 0.01
    lower_active: bool        # c_3 упёрлось в 0.1
    upper_active: bool        # c_m1 упёрлось в 0.8
    optimizer_ok: bool

    def catchability(self, ages) -> np.ndarray:
        return self.b * np.exp(_log_sigmoid(self.a, self.j50, np.asarray(ages, float)))

    def fitted_catch(self, ages) -> np.ndarray:
        ages = np.asarray(ages, float)
        return np.exp(self.K - self.Z * ages + _log_sigmoid(self.a, self.j50, ages))


def fit_sigmoid_catch_curve(
    ages,
    catch,
    weights,
    c_mean: float,
    c_lower: float = config.SEINE_C_LOWER,
    c_upper: float = config.SEINE_C_UPPER,
    c_lower_first: float = config.SEINE_C_LOWER_FIRST,
    j50_bounds: tuple[float, float] | None = None,
) -> SigmoidFit:
    """МНК-подгонка сигмоиды уловистости по улову одного вида за один год.

    ages    — возрасты 2..m1
    catch   — улов по этим возрастам (> 0)
    weights — веса МНК (число рыб в пробе +1)
    c_mean  — заданный средний коэффициент уловистости невода c̄
    c_lower_first — нижняя граница для первой группы (двухлетки), c_lower — для остальных
    """
    ages = np.asarray(ages, float)
    y = np.asarray(catch, float)
    w = np.asarray(weights, float)
    if np.any(y <= 0):
        raise ValueError("Улов по возрастам должен быть положительным (к пробе прибавлена 1)")
    if not (c_lower <= c_mean <= c_upper):
        raise ValueError(f"Средняя уловистость {c_mean} вне ограничений [{c_lower}, {c_upper}]")

    ly = np.log(y)
    if j50_bounds is None:
        j50_bounds = (ages[0] - 1.0, ages[-1])

    # --- 1. Перебор по сетке (a, j50) ---
    a_grid = np.geomspace(*A_BOUNDS, 70)
    j_grid = np.linspace(*j50_bounds, int((j50_bounds[1] - j50_bounds[0]) * 20) + 1)
    A, J = np.meshgrid(a_grid, j_grid, indexing="ij")
    g = _log_sigmoid(A[..., None], J[..., None], ages)
    _, _, sse = _profile_kz(ly - g, ages, w)
    _, c_first, c_second, c_hi = _b_and_edges(A, J, ages, c_mean)
    tol = 1e-9
    feasible = (c_first >= c_lower_first - tol) & (c_second >= c_lower - tol) & (c_hi <= c_upper + tol)
    sse_masked = np.where(feasible, sse, np.inf)
    ia, ij = np.unravel_index(np.argmin(sse_masked), sse_masked.shape)
    best = (float(np.log(A[ia, ij])), float(J[ia, ij]))
    best_sse = float(sse_masked[ia, ij])

    # --- 1б. Уточнение сужающейся сеткой вокруг лучшей точки ---
    # (надёжно работает и тогда, когда оптимум лежит на границе ограничений)
    dla = np.log(a_grid[1] / a_grid[0]) * 2
    dj = (j_grid[1] - j_grid[0]) * 2
    for _ in range(6):
        la = np.clip(np.linspace(best[0] - dla, best[0] + dla, 41), np.log(A_BOUNDS[0]), np.log(A_BOUNDS[1]))
        jj = np.clip(np.linspace(best[1] - dj, best[1] + dj, 41), *j50_bounds)
        A2, J2 = np.meshgrid(np.exp(la), jj, indexing="ij")
        _, _, s2 = _profile_kz(ly - _log_sigmoid(A2[..., None], J2[..., None], ages), ages, w)
        _, f2, se2, h2 = _b_and_edges(A2, J2, ages, c_mean)
        ok2 = (f2 >= c_lower_first - tol) & (se2 >= c_lower - tol) & (h2 <= c_upper + tol)
        s2 = np.where(ok2, s2, np.inf)
        k1, k2 = np.unravel_index(np.argmin(s2), s2.shape)
        if s2[k1, k2] <= best_sse:
            best, best_sse = (float(np.log(A2[k1, k2])), float(J2[k1, k2])), float(s2[k1, k2])
        dla /= 8
        dj /= 8

    # --- 2. Уточнение SLSQP в переменных (ln a, j50) ---
    def objective(p):
        a, j50 = np.exp(p[0]), p[1]
        _, _, s = _profile_kz(ly - _log_sigmoid(a, j50, ages), ages, w)
        return float(s)

    def edges(p):
        _, first, second, hi = _b_and_edges(np.exp(p[0]), p[1], ages, c_mean)
        return float(first), float(second), float(hi)

    constraints = [
        {"type": "ineq", "fun": lambda p: edges(p)[0] - c_lower_first},
        {"type": "ineq", "fun": lambda p: edges(p)[1] - c_lower},
        {"type": "ineq", "fun": lambda p: c_upper - edges(p)[2]},
    ]
    bounds = [(np.log(A_BOUNDS[0]), np.log(A_BOUNDS[1])), j50_bounds]
    # Когда оптимум лежит на границе ограничения, SLSQP нередко завершается с
    # сообщением о линейном поиске, уже найдя лучшую допустимую точку. Поэтому
    # принимаем любое допустимое улучшение и делаем до трёх перезапусков.
    optimizer_ok = np.isfinite(best_sse)  # после сужающейся сетки решение уже уточнено
    for _ in range(3):
        try:
            res = minimize(objective, x0=np.array(best), method="SLSQP",
                           bounds=bounds, constraints=constraints,
                           options={"ftol": 1e-10, "maxiter": 300})
        except (ValueError, FloatingPointError):
            break
        first, second, hi = edges(res.x)
        feasible_res = (first >= c_lower_first - 1e-6 and second >= c_lower - 1e-6
                        and hi <= c_upper + 1e-6)
        if feasible_res and res.fun <= best_sse + 1e-12:
            improved = res.fun < best_sse - 1e-9
            best, best_sse = (float(res.x[0]), float(res.x[1])), float(res.fun)
            optimizer_ok = True
            if res.success or not improved:
                break
        else:
            break

    a, j50 = float(np.exp(best[0])), best[1]
    K, Z, sse = _profile_kz(ly - _log_sigmoid(a, j50, ages), ages, w)
    b, first, second, hi = _b_and_edges(a, j50, ages, c_mean)
    W = w.sum()
    sst = float((w * (ly - (w * ly).sum() / W) ** 2).sum())
    r2 = 1.0 - float(sse) / sst if sst > 0 else float("nan")

    return SigmoidFit(
        a=a, j50=j50, b=float(b), Z=float(Z), K=float(K), sse=float(sse), r2=r2,
        first_lower_active=bool(abs(float(first) - c_lower_first) < 1e-4),
        lower_active=bool(ages.size > 1 and abs(float(second) - c_lower) < 1e-3),
        upper_active=bool(abs(float(hi) - c_upper) < 1e-3),
        optimizer_ok=optimizer_ok,
    )


# ---------------------------------------------------------------------------
# Расчёт по всем видам и годам
# ---------------------------------------------------------------------------
SOURCE_CATCH = "годовой улов неводом"
SOURCE_SAMPLE = "возрастная проба (улова неводом нет)"
SOURCE_POOLED = "проба за все годы (мало рыб в пробе)"


@dataclass
class SeineFitResult:
    species: str
    year: int
    m0: int
    m1: int
    c_mean: float
    ages: np.ndarray            # возрасты подгонки 2..m1
    observed: np.ndarray        # годовой улов (или доли пробы) по возрастам, использованный в МНК
    weights: np.ndarray
    fit: SigmoidFit
    j50_rule: float             # точка перегиба по правилу статьи
    source: str                 # откуда взяты данные для подгонки
    n_sample: int               # рыб в возрастной пробе года (без +1)
    total_catch: float          # годовой улов вида неводом, штук
    n_hauls: int

    @property
    def catchability(self) -> np.ndarray:
        return self.fit.catchability(self.ages)

    @property
    def fitted(self) -> np.ndarray:
        """Модельный улов в тех же единицах, что observed."""
        return self.fit.fitted_catch(self.ages)

    @property
    def status(self) -> str:
        notes = []
        if self.source != SOURCE_CATCH:
            notes.append(self.source)
        if self.fit.first_lower_active:
            notes.append(f"c({age_label(self.ages[0])}) = {_ru(config.SEINE_C_LOWER_FIRST)}")
        if self.fit.lower_active:
            notes.append(f"c({age_label(self.ages[1])}) = {_ru(config.SEINE_C_LOWER)}")
        if self.fit.upper_active:
            notes.append(f"c({age_label(self.m1)}) = {_ru(config.SEINE_C_UPPER)}")
        if self.fit.a >= A_BOUNDS[1] * 0.999:
            notes.append("ступенька: a на верхней границе")
        elif self.fit.a <= A_BOUNDS[0] * 1.001:
            notes.append("почти константа: a на нижней границе")
        return "; ".join(notes) if notes else "ок"


@dataclass
class SeineCatchability:
    waterbody: str
    years: list[int]
    species: list[str]
    all_ages: np.ndarray                     # все возрасты исходной таблицы (2..16)
    fits: dict[tuple[str, int], SeineFitResult] = field(default_factory=dict)

    # --- куб Year × FishType × Age, совместимый со старым .nc ---
    def cube(self) -> np.ndarray:
        out = np.zeros((len(self.years), len(self.species), len(self.all_ages)))
        for yi, year in enumerate(self.years):
            for si, fish in enumerate(self.species):
                r = self.fits.get((fish, year))
                if r is None:
                    continue
                c = dict(zip(r.ages.astype(int), r.catchability))
                out[yi, si, :] = [c.get(int(a), 0.0) for a in self.all_ages]
        return out

    def params_frame(self) -> pd.DataFrame:
        rows = []
        for (fish, year), r in sorted(self.fits.items(), key=lambda kv: (self.species.index(kv[0][0]), kv[0][1])):
            c = r.catchability
            rows.append({
                "вид": fish, "год": year,
                "a (крутизна)": r.fit.a, "j50 (МНК)": r.fit.j50, "j50 (правило статьи)": r.j50_rule,
                "b": r.fit.b, "Z (общая смертность)": r.fit.Z,
                f"c({age_label(r.ages[0])})": c[0], "c(m1)": c[-1], "среднее c": c.mean(), "c̄ задано": r.c_mean,
                "R² (лог)": r.fit.r2, "рыб в пробе": r.n_sample, "улов неводом, шт": r.total_catch,
                "уловов неводом": r.n_hauls, "m1": r.m1, "статус": r.status,
            })
        return pd.DataFrame(rows)

    def cube_frame(self) -> pd.DataFrame:
        """Куб в виде длинной таблицы: год, вид, возраст, коэффициент."""
        cube = self.cube()
        rows = []
        for yi, year in enumerate(self.years):
            for si, fish in enumerate(self.species):
                for ai, age in enumerate(self.all_ages):
                    rows.append({"год": year, "вид": fish, "возраст": age_label(age), "c": cube[yi, si, ai]})
        return pd.DataFrame(rows)


def _ru(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _article_j50(ages, observed, m0) -> float:
    return float(max(m0 + 1, ages[int(np.argmax(observed))]))


def compute_seine_catchability(
    waterbody: str = config.WATERBODY,
    data_dir: Path | None = None,
    min_sample: int = config.SEINE_MIN_SAMPLE,
) -> SeineCatchability:
    props: FishProps = load_fish_props(waterbody, data_dir)
    catches = yearly_catch_by_age(config.GEAR_SEINE, waterbody, data_dir, props)

    species = sorted({f for f, _ in catches}, key=lambda s: props.species.index(s))
    years = sorted({y for _, y in catches})
    all_ages = next(iter(catches.values())).ages

    # Пробы вида за все годы — запасной вариант, когда в пробе года мало рыб
    pooled_raw = {}
    for fish in species:
        pooled_raw[fish] = sum(catches[(fish, y)].sample_raw for y in years if (fish, y) in catches)

    result = SeineCatchability(waterbody, years, species, all_ages)
    for (fish, year), yc in catches.items():
        m0, m1, c_mean = props.m0[fish], props.m1[fish], props.k_seine[fish]
        mask = (yc.ages >= config.SEINE_MIN_AGE) & (yc.ages <= m1)
        ages = yc.ages[mask].astype(float)
        n_sample = int(yc.sample_raw[mask].sum())

        if n_sample < min_sample:
            smoothed = pooled_raw[fish][mask] + 1.0
            observed, weights, source = smoothed / smoothed.sum(), smoothed, SOURCE_POOLED
        elif yc.total_catch <= 0:
            smoothed = yc.sample_smoothed[mask]
            observed, weights, source = smoothed / smoothed.sum(), smoothed, SOURCE_SAMPLE
        else:
            observed, weights, source = yc.catch_by_age[mask], yc.sample_smoothed[mask], SOURCE_CATCH

        fit = fit_sigmoid_catch_curve(ages, observed, weights, c_mean)
        result.fits[(fish, year)] = SeineFitResult(
            species=fish, year=year, m0=m0, m1=m1, c_mean=c_mean,
            ages=ages, observed=observed, weights=weights, fit=fit,
            j50_rule=_article_j50(ages, observed, m0), source=source,
            n_sample=n_sample, total_catch=yc.total_catch, n_hauls=yc.n_hauls,
        )
    return result


# ---------------------------------------------------------------------------
# Сохранение и чтение (NetCDF через xarray — как в исходном проекте)
# ---------------------------------------------------------------------------
def netcdf_path(waterbody: str = config.WATERBODY, results_dir: Path | None = None) -> Path:
    return Path(results_dir or config.RESULTS_DIR) / f"{waterbody}_catchability_seine_3d.nc"


def to_dataarray(res: SeineCatchability):
    import xarray as xr
    da = xr.DataArray(
        res.cube(),
        coords={
            "Year": res.years,
            "FishType": res.species,
            "LessAge": [f"less_{int(a)}" for a in res.all_ages],
        },
        dims=["Year", "FishType", "LessAge"],
        name=CUBE_NAME,
        attrs={
            "method": "МНК: сигмоида уловистости + кривая улова, ограничения (25)-(26)",
            "c_lower": config.SEINE_C_LOWER,
            "c_lower_age2": config.SEINE_C_LOWER_FIRST,
            "c_upper": config.SEINE_C_UPPER,
            "waterbody": res.waterbody,
        },
    )
    return da.assign_coords(age=("LessAge", res.all_ages.astype(int)))


def save_results(res: SeineCatchability, results_dir: Path | None = None) -> dict[str, Path]:
    """Сохраняет куб в .nc (если установлен xarray) и параметры в CSV."""
    results_dir = Path(results_dir or config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    saved = {}
    csv_path = results_dir / f"{res.waterbody}_catchability_seine_params.csv"
    res.params_frame().to_csv(csv_path, index=False, encoding="utf-8-sig")
    saved["csv"] = csv_path
    try:
        da = to_dataarray(res)
    except ImportError:
        saved["nc_error"] = "не установлен xarray"
        return saved
    nc_path = netcdf_path(res.waterbody, results_dir)
    try:
        da.to_netcdf(nc_path, engine="netcdf4")
        saved["nc"] = nc_path
    except Exception as e:  # например, не установлен netCDF4
        saved["nc_error"] = str(e)
    return saved


def load_old_cube(waterbody: str = config.WATERBODY, old_dir: Path | None = None):
    """Старые (байесовские) коэффициенты из исходного проекта.

    Возвращает dict {(вид, год): {возраст: c}} или None, если файла нет
    или не установлен xarray.
    """
    path = Path(old_dir or config.OLD_DATA_STOCK_DIR) / f"{waterbody}_catchability_seine_3d.nc"
    if not path.exists():
        return None
    try:
        import xarray as xr
    except ImportError:
        return None
    with xr.open_dataarray(path) as da:
        da = da.load()
    ages = da["age"].values.astype(int) if "age" in da.coords else \
        np.array([int(str(s).split("_")[1]) for s in da["LessAge"].values])
    out = {}
    for year in da["Year"].values:
        for fish in da["FishType"].values:
            vals = da.sel(Year=year, FishType=fish).values
            out[(str(fish), int(year))] = dict(zip(ages.tolist(), vals.astype(float).tolist()))
    return out
