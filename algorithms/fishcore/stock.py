"""
Запас рыб по данным уловов (правдоподобие для байесовской модели и годовые оценки).

По каждому лову d (возрастная группа j, вид i):
    невод, метод площадей (27):   X²_ij(d) = Y²_ij(d) · S(t) / (c²_ij(t) · s_area(d))
    сеть, балансовый метод:        X¹_ij(d) = Y¹_ij(d) · S(t) / (σ(c¹_ij(t)) · (V_i² − r0²))   (как в старом коде)
        или по формуле (28) статьи:  X¹_ij(d) = Y¹_ij(d) · S(t) / (π V_i² σ(c¹_ij(t)))       (config.NET_STOCK_FORMULA)
        n сетей на каждую ячею (научные 2, промысловые 1; config.NET_PANELS_MODE): улов приводится к одной сети, Y / √n:
                                       X¹_ij(d) = Y¹_ij(d) · S(t) / (√n(d) · π V_i² σ(c¹_ij(t)))
        σ — доля рыб первого круга, попавших в сеть (core.net_model), V_i — путь рыбы за час, r0 — полдлины сети.

Варианты:
    with_ages — уловистость по возрастным группам (кубы этапа 1 и параболы сети);
    out_ages  — одна средняя уловистость вида c̄ для всех групп.

Годовой запас:
    on_stock — среднее оценок по ловам года (как calc_yearly_stock_on_stock_3d; вес
               научных и промысловых ловов по их числу = простое среднее);
    on_catch — по годовому улову (статья, после формулы (28)):
               невод: ΣY(d) · S / (c · Σ s_area(d));   сеть: средний улов на лов → (28).
    окончательный запас по возрасту (config.COMBINE_GEARS):
        "hauls": X_ij(t) = (N¹·X¹_ij(t) + N²·X²_ij(t)) / (N¹ + N²),  N — число ловов орудия в году,
                 в которых вид учитывался (решение автора);
        "mean":  X_ij(t) = (X¹_ij(t) + X²_ij(t)) / 2 — формула (29) статьи;
    суммарный запас = сумма окончательных запасов по всем возрастам; по окончательному запасу
    распределяется ПДУ.

Ловы, в которых вид не учитывался (NaN в исходных данных), исключаются; нулевые уловы учитываются.
Где уловистость равна 0 (группы старше m1), запас принимается равным 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .catch import HaulCatch, build_haul_catch
from .catchability_net import NetCatchability, compute_net_catchability
from .catchability_seine import SeineCatchability, compute_seine_catchability
from .data_source import FishProps, load_fish_props, load_npc
from .net_model import net_denominator, net_share

GEARS = (config.GEAR_NET, config.GEAR_SEINE)
MEAN = "сеть+невод"   # окончательный запас: объединение сети и невода
VARIANTS = ("with_ages", "out_ages")
METHODS = ("on_stock", "on_catch")
VARIANT_TITLES = {"with_ages": "с учётом возрастов", "out_ages": "без учёта возрастов"}
METHOD_TITLES = {"on_stock": "по запасам (среднее оценок по ловам)", "on_catch": "по годовому улову"}


def _safe_div(num, den):
    num = np.asarray(num, float)
    den = np.asarray(den, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0)
    return np.where(np.isnan(num), np.nan, out)


def _nanmean(a, axis):
    """Среднее без NaN; если все NaN — NaN (без предупреждений)."""
    cnt = (~np.isnan(a)).sum(axis=axis)
    s = np.nansum(a, axis=axis)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(cnt > 0, s / np.where(cnt > 0, cnt, 1), np.nan)


def combine_gears(cubes, counts, how: str | None = None) -> np.ndarray:
    """Окончательный запас по возрастам из оценок сети и невода.

    cubes  — [(годы, виды, возрасты)] по орудиям; counts — [(годы, виды)] число ловов.
    "hauls": средневзвешенное по числу ловов; "mean": простое среднее (29).
    Если у одного орудия оценки нет (NaN), берётся оценка другого.
    """
    how = how or config.COMBINE_GEARS
    num = np.zeros_like(cubes[0], dtype=float)
    den = np.zeros_like(cubes[0], dtype=float)
    for cube, n in zip(cubes, counts):
        w = np.broadcast_to((n if how == "hauls" else np.ones_like(n))[..., None], cube.shape)
        ok = ~np.isnan(cube) & (w > 0)
        num += np.where(ok, cube * w, 0.0)
        den += np.where(ok, w, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


@dataclass
class StockResult:
    waterbody: str
    years: list[int]
    species: list[str]
    ages: np.ndarray
    m1: dict
    catches: dict[str, HaulCatch]                      # орудие -> уловы по ловам
    catchability: dict[tuple[str, str], np.ndarray]    # (орудие, вариант) -> (годы, виды, группы)
    sigma: dict[str, np.ndarray]                       # вариант -> σ сети (годы, виды, группы)
    per_haul: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)   # (орудие, вариант) -> (N, виды, группы)
    yearly: dict[tuple[str, str, str], np.ndarray] = field(default_factory=dict)  # (орудие|среднее, вариант, метод)
    npc_stock: np.ndarray | None = None                # (годы, виды), штук
    method: str = "on_stock"                           # способ годового запаса, по которому считаются ПДУ и модель

    def age_mask(self) -> np.ndarray:
        """(виды, группы) — группы от 2 до m1 вида."""
        return np.array([[2 <= a <= self.m1[s] for a in self.ages] for s in self.species])

    def yearly_total(self, gear: str, variant: str, method: str) -> np.ndarray:
        """(годы, виды) — запас по сумме групп 2..m1; NaN, если данных нет."""
        cube = self.yearly[(gear, variant, method)]
        m = self.age_mask()[None, :, :]
        vals = np.where(m, cube, 0.0)
        all_nan = np.all(np.isnan(np.where(m, cube, np.nan)), axis=2)
        return np.where(all_nan, np.nan, np.nansum(vals, axis=2))

    def combined_total(self, variant: str, method: str) -> np.ndarray:
        """(годы, виды) — суммарный годовой запас: сумма окончательных запасов по всем возрастам."""
        return self.yearly_total(MEAN, variant, method)

    def per_haul_total(self, gear: str, variant: str) -> np.ndarray:
        """(N, виды) — оценка запаса по лову, сумма групп 2..m1."""
        arr = self.per_haul[(gear, variant)]
        m = self.age_mask()[None, :, :]
        all_nan = np.all(np.isnan(np.where(m, arr, np.nan)), axis=2)
        return np.where(all_nan, np.nan, np.nansum(np.where(m, arr, 0.0), axis=2))

    def variant_methods(self) -> list[tuple[str, str]]:
        """Пары (вариант, способ), посчитанные в результате: у compute_stock — все, у алгоритма g — одна (№ 66)."""
        have = {(k[1], k[2]) for k in self.yearly if k[0] == MEAN}
        return [(v, m) for v in VARIANTS for m in METHODS if (v, m) in have]

    def totals_frame(self) -> pd.DataFrame:
        rows = []
        for v, meth in self.variant_methods():
            if True:
                tot = {g: self.yearly_total(g, v, meth) for g in (*GEARS, MEAN)}
                cnt = {g: self.catches[g].yearly_count() for g in GEARS}
                for si, fish in enumerate(self.species):
                    for yi, year in enumerate(self.years):
                        rows.append({
                            "вариант": VARIANT_TITLES[v], "метод": METHOD_TITLES[meth], "вид": fish, "год": year,
                            "сеть, шт": tot[config.GEAR_NET][yi, si], "невод, шт": tot[config.GEAR_SEINE][yi, si],
                            "сеть+невод (окончательный), шт": tot[MEAN][yi, si],
                            "ловов сетью": cnt[config.GEAR_NET][yi, si], "ловов неводом": cnt[config.GEAR_SEINE][yi, si],
                            "НПЦ, шт": None if self.npc_stock is None else self.npc_stock[yi, si],
                        })
        return pd.DataFrame(rows)


def panel_factor(hc: HaulCatch) -> np.ndarray:
    """(N,) — √n по каждому лову сетью (n — число полотен, config.NET_PANELS_MODE); 1 при "one"."""
    n = hc.meta["NetPanels"].to_numpy(float) if "NetPanels" in hc.meta else np.ones(len(hc.meta))
    if config.NET_PANELS_MODE == "one":
        return np.ones_like(n)
    if config.NET_PANELS_MODE == "sqrt":
        return np.sqrt(np.maximum(n, 1.0))
    raise ValueError(f"Неизвестный режим числа полотен: {config.NET_PANELS_MODE}")


# ---------------------------------------------------------------- части расчёта (алгоритмы каталога c–g)
# Те же выражения, что были внутри compute_stock (результат не меняется — проверяет регрессия этапов 1–3):
# compute_stock собирается из этих функций, алгоритмы каталога вызывают их по отдельности (решение № 66).

def gear_inputs(props: FishProps, years, species):
    """S(t), м²; V вида, м/ч; время стоянки и длина сети по годам."""
    area = np.array([props.lake_area_km2[y] * config.KM2_M2 for y in years])       # S(t), м²
    speed = np.array([props.cruise_speed[s] * 3600.0 for s in species])            # V, м/ч
    hours = [props.net_hours[y] for y in years]
    length = [props.net_length[y] for y in years]
    return area, speed, hours, length


def net_sigma(c: np.ndarray, hours, length, speed) -> np.ndarray:
    """σ — доля рыб первого круга, попавших в сеть (балансовая модель), (годы, виды, группы)."""
    nY, nS, nA = c.shape
    sg = np.zeros_like(c)
    for yi in range(nY):
        for si in range(nS):
            for ai in range(nA):
                sg[yi, si, ai] = net_share(c[yi, si, ai], hours[yi], length[yi], speed[si])
    return sg


def seine_per_haul(hc: HaulCatch, c: np.ndarray, area: np.ndarray) -> np.ndarray:
    """Метод площадей: X²_ij(d) = Y²_ij(d) · S(t) / (c²_ij(t) · s_area(d)), (ловы, виды, группы)."""
    yi = hc.year_index
    s_area = hc.meta["Area"].to_numpy(float) * config.HECTARE_M2
    den = c[yi] * s_area[:, None, None]
    return _safe_div(hc.values * area[yi][:, None, None], den)


def net_per_haul(hc: HaulCatch, sigma: np.ndarray, area: np.ndarray, speed: np.ndarray, length) -> np.ndarray:
    """Балансовый метод: X¹_ij(d) = Y¹_ij(d) · S(t) / (√n(d) · π V_i² σ(c¹_ij(t))), (ловы, виды, группы)."""
    yi = hc.year_index
    width = np.array([length[k] for k in yi], float)
    den = net_denominator(speed[None, :, None], width[:, None, None], sigma[yi])
    den = den * panel_factor(hc)[:, None, None]
    return _safe_div(hc.values * area[yi][:, None, None], den)


def seine_yearly(hc: HaulCatch, per: np.ndarray, c: np.ndarray, area: np.ndarray, method: str) -> np.ndarray:
    """Годовой запас неводом (годы, виды, группы): on_stock — среднее оценок по ловам; on_catch — по годовому улову."""
    nY = len(hc.years)
    yi = hc.year_index
    out = np.full((nY, len(hc.species), len(hc.ages)), np.nan)
    for k in range(nY):
        sel = yi == k
        if not sel.any():
            continue
        if method == "on_stock":
            out[k] = _nanmean(per[sel], axis=0)
            continue
        vals = hc.values[sel]                                   # (n, виды, группы)
        recorded = ~np.isnan(vals)
        s_area = hc.meta["Area"].to_numpy(float)[sel] * config.HECTARE_M2
        area_sum = (recorded * s_area[:, None, None]).sum(axis=0)
        catch_sum = np.where(recorded.any(axis=0), np.nansum(vals, axis=0), np.nan)
        out[k] = _safe_div(catch_sum * area[k], c[k] * area_sum)
    return out


def net_yearly(hc: HaulCatch, per: np.ndarray, sigma: np.ndarray, area: np.ndarray, speed: np.ndarray, length,
               method: str) -> np.ndarray:
    """Годовой запас сетью (годы, виды, группы): on_stock — среднее оценок по ловам; on_catch — средний улов на лов."""
    nY = len(hc.years)
    yi = hc.year_index
    out = np.full((nY, len(hc.species), len(hc.ages)), np.nan)
    for k in range(nY):
        sel = yi == k
        if not sel.any():
            continue
        if method == "on_stock":
            out[k] = _nanmean(per[sel], axis=0)
            continue
        vals = hc.values[sel]
        mean_catch = _nanmean(vals / panel_factor(hc)[sel][:, None, None], axis=0)  # к одной сети
        den = net_denominator(speed[:, None], length[k], sigma[k])
        out[k] = _safe_div(mean_catch * area[k], den)
    return out


def compute_stock(
    waterbody: str = config.WATERBODY,
    data_dir: Path | None = None,
    props: FishProps | None = None,
    seine_c: SeineCatchability | None = None,
    net_c: NetCatchability | None = None,
) -> tuple[StockResult, NetCatchability, SeineCatchability]:
    props = props or load_fish_props(waterbody, data_dir)
    net_catch = build_haul_catch(config.GEAR_NET, waterbody, data_dir, props)
    seine_catch = build_haul_catch(config.GEAR_SEINE, waterbody, data_dir, props)
    net_c = net_c or compute_net_catchability(waterbody, data_dir, props, net_catch)
    seine_c = seine_c or compute_seine_catchability(waterbody, data_dir)

    years, species, ages = net_catch.years, net_catch.species, net_catch.ages
    assert seine_c.years == years and list(seine_c.species) == list(species), "несогласованы годы/виды"
    assert np.array_equal(seine_c.all_ages, ages) and np.array_equal(net_c.all_ages, ages)

    nY, nS, nA = len(years), len(species), len(ages)
    area, speed, hours, length = gear_inputs(props, years, species)

    catchability = {
        (config.GEAR_NET, "with_ages"): net_c.cube(),
        (config.GEAR_SEINE, "with_ages"): seine_c.cube(),
        (config.GEAR_NET, "out_ages"): np.broadcast_to(
            np.array([props.k_net[s] for s in species])[None, :, None], (nY, nS, nA)).copy(),
        (config.GEAR_SEINE, "out_ages"): np.broadcast_to(
            np.array([props.k_seine[s] for s in species])[None, :, None], (nY, nS, nA)).copy(),
    }

    # σ сети для каждого (год, вид, группа) — модель баланса с кэшем
    sigma = {v: net_sigma(catchability[(config.GEAR_NET, v)], hours, length, speed) for v in VARIANTS}

    res = StockResult(waterbody, years, species, ages, dict(props.m1),
                      {config.GEAR_NET: net_catch, config.GEAR_SEINE: seine_catch}, catchability, sigma)

    # --- запас по каждому лову ---
    for v in VARIANTS:
        res.per_haul[(config.GEAR_SEINE, v)] = seine_per_haul(seine_catch, catchability[(config.GEAR_SEINE, v)], area)
        res.per_haul[(config.GEAR_NET, v)] = net_per_haul(net_catch, sigma[v], area, speed, length)

    # --- годовой запас ---
    for v in VARIANTS:
        for meth in METHODS:
            res.yearly[(config.GEAR_SEINE, v, meth)] = seine_yearly(
                seine_catch, res.per_haul[(config.GEAR_SEINE, v)], catchability[(config.GEAR_SEINE, v)], area, meth)
            res.yearly[(config.GEAR_NET, v, meth)] = net_yearly(
                net_catch, res.per_haul[(config.GEAR_NET, v)], sigma[v], area, speed, length, meth)
        for meth in METHODS:
            res.yearly[(MEAN, v, meth)] = combine_gears(
                [res.yearly[(g, v, meth)] for g in GEARS],
                [res.catches[g].yearly_count() for g in GEARS])

    npc_stock, _ = load_npc(waterbody, data_dir)
    if npc_stock is not None:
        res.npc_stock = np.array([[npc_stock.loc[y, s] * config.NPC_STOCK_MULTIPLIER
                                   if (y in npc_stock.index and s in npc_stock.columns) else np.nan
                                   for s in species] for y in years])
    return res, net_c, seine_c
