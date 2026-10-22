"""
Коэффициенты уловистости сети — парабола по возрасту, формулы (22)-(24) статьи.

Для вида i и года t (индексы опущены), возрастные группы j = j_min..m1 (j_min = 2):

    вершина             c¹ = max(m0 + 1, argmax_j Y_j)          Y_j — годовой улов сетью
    парабола  (22)      c_j = c⁰ − a1·(j − c¹)²,   j_min <= j <= c¹
                        c_j = c⁰ − a2·(j − c¹)²,   c¹ <= j <= m1
    условия             c̄ − a1·(j_min − c¹)² = 0.1   →  a1 = (c̄ − 0.1) / (j_min − c¹)²
                        c̄ − a2·(m1 − c¹)² = 0.2      →  a2 = (c̄ − 0.2) / (m1 − c¹)²
    среднее  (23)       (1/n) Σ_j c_j = c̄            →  c⁰ = c̄ + (1/n) Σ_j a_j·(j − c¹)²
    ограничения (24)    0.1 <= c_j <= 0.8 (при c̄ < 0.5 выполняются автоматически: c⁰ < 2c̄ − 0.1)

c̄ — заданный средний коэффициент уловистости сети вида (k_catchability_1).
В статье первая группа j = 1; в уловах одногодков нет, поэтому j_min = 2 (config.NET_MIN_AGE).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .catch import HaulCatch, build_haul_catch
from .ages import age_label
from .data_source import FishProps, load_fish_props

CUBE_NAME = "corrected_catchability_coefficient"  # имя переменной как в старом .nc


@dataclass
class Parabola:
    peak: float     # c¹ — вершина (возрастная группа)
    c0: float       # значение в вершине
    a1: float       # левая ветвь
    a2: float       # правая ветвь

    def value(self, ages) -> np.ndarray:
        ages = np.asarray(ages, float)
        d2 = (ages - self.peak) ** 2
        return np.where(ages <= self.peak, self.c0 - self.a1 * d2, self.c0 - self.a2 * d2)


def fit_parabola(ages, observed, m0: int, c_mean: float,
                 end_left: float = config.NET_END_LEFT, end_right: float = config.NET_END_RIGHT) -> Parabola:
    """Парабола по формулам (22)-(24). ages — группы j_min..m1, observed — улов по ним."""
    ages = np.asarray(ages, float)
    observed = np.asarray(observed, float)
    j_min, m1 = ages[0], ages[-1]
    peak = float(max(m0 + 1, ages[int(np.argmax(observed))]))
    peak = min(peak, m1)
    a1 = (c_mean - end_left) / (j_min - peak) ** 2 if peak > j_min else 0.0
    a2 = (c_mean - end_right) / (m1 - peak) ** 2 if m1 > peak else 0.0
    d2 = (ages - peak) ** 2
    c0 = c_mean + float(np.mean(np.where(ages <= peak, a1 * d2, a2 * d2)))
    return Parabola(peak=peak, c0=c0, a1=a1, a2=a2)


SOURCE_CATCH = "годовой улов сетью"
SOURCE_SAMPLE = "возрастная проба (улова сетью нет)"
SOURCE_POOLED = "проба за все годы (мало рыб в пробе)"


@dataclass
class NetFitResult:
    species: str
    year: int
    m0: int
    m1: int
    c_mean: float
    ages: np.ndarray
    observed: np.ndarray
    parabola: Parabola
    source: str
    n_sample: int
    total_catch: float
    n_hauls: int

    @property
    def catchability(self) -> np.ndarray:
        return self.parabola.value(self.ages)

    @property
    def violations(self) -> list[str]:
        c = self.catchability
        out = []
        if c.min() < config.NET_C_LOWER - 1e-9:
            out.append(f"c < {config.NET_C_LOWER} в возрасте {age_label(self.ages[np.argmin(c)])}")
        if c.max() > config.NET_C_UPPER + 1e-9:
            out.append(f"c > {config.NET_C_UPPER} в возрасте {age_label(self.ages[np.argmax(c)])}")
        return out

    @property
    def status(self) -> str:
        notes = []
        if self.source != SOURCE_CATCH:
            notes.append(self.source)
        notes += [f"нарушено ограничение: {v}" for v in self.violations]
        return "; ".join(notes) if notes else "ок"


@dataclass
class NetCatchability:
    waterbody: str
    years: list[int]
    species: list[str]
    all_ages: np.ndarray
    fits: dict[tuple[str, int], NetFitResult] = field(default_factory=dict)

    def cube(self) -> np.ndarray:
        """(годы, виды, все группы таблицы); группы вне j_min..m1 — 0, как в старом кубе."""
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
        order = {s: i for i, s in enumerate(self.species)}
        for (fish, year), r in sorted(self.fits.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])):
            c = r.catchability
            p = r.parabola
            rows.append({
                "вид": fish, "год": year, "вершина c¹ (j)": p.peak, "вершина, возраст": age_label(p.peak),
                "c⁰ (в вершине)": p.c0,
                "a1 (левая ветвь)": p.a1, "a2 (правая ветвь)": p.a2,
                f"c({age_label(r.ages[0])})": c[0], "c(m1)": c[-1], "среднее c": c.mean(), "c̄ задано": r.c_mean,
                "рыб в пробе": r.n_sample, "улов сетью, шт": r.total_catch, "уловов сетью": r.n_hauls,
                "m0": r.m0, "m1": r.m1, "статус": r.status,
            })
        return pd.DataFrame(rows)

    def cube_frame(self) -> pd.DataFrame:
        cube = self.cube()
        rows = []
        for yi, year in enumerate(self.years):
            for si, fish in enumerate(self.species):
                for ai, age in enumerate(self.all_ages):
                    rows.append({"год": year, "вид": fish, "возраст": age_label(age), "c": cube[yi, si, ai]})
        return pd.DataFrame(rows)


def compute_net_catchability(
    waterbody: str = config.WATERBODY,
    data_dir: Path | None = None,
    props: FishProps | None = None,
    net_catch: HaulCatch | None = None,
    min_sample: int = config.NET_MIN_SAMPLE,
) -> NetCatchability:
    props = props or load_fish_props(waterbody, data_dir)
    hc = net_catch or build_haul_catch(config.GEAR_NET, waterbody, data_dir, props)
    yearly = hc.yearly_sum()                   # (годы, виды, группы)
    counts = hc.yearly_count()
    pooled_raw = hc.sample_raw.sum(axis=0)     # (виды, группы)

    res = NetCatchability(waterbody, hc.years, hc.species, hc.ages)
    for si, fish in enumerate(hc.species):
        m0, m1, c_mean = props.m0[fish], props.m1[fish], props.k_net[fish]
        mask = (hc.ages >= config.NET_MIN_AGE) & (hc.ages <= m1)
        ages = hc.ages[mask].astype(float)
        for yi, year in enumerate(hc.years):
            n_sample = int(hc.sample_raw[yi, si, mask].sum())
            total = float(yearly[yi, si].sum())
            if n_sample < min_sample:
                sm = pooled_raw[si, mask] + 1.0
                observed, source = sm / sm.sum(), SOURCE_POOLED
            elif total <= 0:
                observed, source = hc.shares[yi, si, mask], SOURCE_SAMPLE
            else:
                observed, source = yearly[yi, si, mask], SOURCE_CATCH
            res.fits[(fish, year)] = NetFitResult(
                species=fish, year=year, m0=m0, m1=m1, c_mean=c_mean, ages=ages, observed=observed,
                parabola=fit_parabola(ages, observed, m0, c_mean), source=source,
                n_sample=n_sample, total_catch=total, n_hauls=int(counts[yi, si]),
            )
    return res
