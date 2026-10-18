"""
Улов по каждому лову, виду и возрастной группе (аналог save_catch_3d.py).

Возрастная группа j (less_j) — рыбы в возрасте от j−1 до j лет; группа 2 — двухлетки.

Улов лова d по возрастам: Y_ij(d) = Y_i(d) · q_ij(t), где q_ij(t) — доли возрастной
пробы года (к пробе прибавляется 1 для групп <= m1, формула (20) статьи).

Пропуск (NaN) в исходной таблице означает, что вид в этом лове не учитывался;
он сохраняется как NaN и исключается из средних (как в исходном проекте через xarray),
а ноль — это учтённый нулевой улов.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .data_source import FishProps, list_catch_years, load_fish_props, load_year

META_COLUMNS = ["Date", "Place", "Instrument", "Instrument_size", "CatchType", "Year", "Area"]


@dataclass
class HaulCatch:
    """Уловы одного орудия лова по ловам."""
    gear: str
    waterbody: str
    meta: pd.DataFrame          # по строке на лов: Id (1..N), Date, Place, ..., Year, Area
    species: list[str]
    ages: np.ndarray            # возрастные группы таблицы пробы (2..16)
    years: list[int]
    values: np.ndarray          # (N, виды, группы) — улов, штук; NaN — вид не учитывался
    shares: np.ndarray          # (годы, виды, группы) — доли возрастной пробы (сумма = 1)
    sample_raw: np.ndarray      # (годы, виды, группы) — проба, штук

    @property
    def year_index(self) -> np.ndarray:
        """Номер года (в self.years) для каждого лова."""
        pos = {y: i for i, y in enumerate(self.years)}
        return np.array([pos[y] for y in self.meta["Year"]])

    def totals(self) -> np.ndarray:
        """(N, виды) — улов вида в лове, штук (NaN — не учитывался)."""
        return np.where(np.isnan(self.values).all(axis=2), np.nan, np.nansum(self.values, axis=2))

    def yearly_sum(self) -> np.ndarray:
        """(годы, виды, группы) — суммарный улов за год, NaN считаются нулями."""
        out = np.zeros((len(self.years), len(self.species), len(self.ages)))
        yi = self.year_index
        for k in range(len(self.years)):
            out[k] = np.nansum(self.values[yi == k], axis=0)
        return out

    def yearly_count(self) -> np.ndarray:
        """(годы, виды) — число ловов, в которых вид учитывался (не NaN)."""
        out = np.zeros((len(self.years), len(self.species)))
        yi = self.year_index
        recorded = ~np.isnan(self.totals())
        for k in range(len(self.years)):
            out[k] = recorded[yi == k].sum(axis=0)
        return out


def build_haul_catch(
    gear: str,
    waterbody: str = config.WATERBODY,
    data_dir: Path | None = None,
    props: FishProps | None = None,
) -> HaulCatch:
    props = props or load_fish_props(waterbody, data_dir)
    species = props.species
    years = list_catch_years(waterbody, data_dir)

    metas, blocks, shares_all, samples_all = [], [], [], []
    ages = None
    for year in years:
        catches, sample = load_year(year, waterbody, data_dir)
        ages_y = sample.index.to_numpy()
        if ages is None:
            ages = ages_y
        elif not np.array_equal(ages, ages_y):
            sample = sample.reindex(ages, fill_value=0.0)

        shares = np.zeros((len(species), len(ages)))
        raw = np.zeros((len(species), len(ages)))
        for s, fish in enumerate(species):
            if fish not in sample.columns:
                continue
            r = sample[fish].to_numpy(dtype=float)
            smoothed = r + (ages <= props.m1[fish]).astype(float)
            raw[s] = r
            shares[s] = smoothed / smoothed.sum() if smoothed.sum() > 0 else 0.0
        shares_all.append(shares)
        samples_all.append(raw)

        rows = catches[catches["Instrument"] == gear].reset_index(drop=True)
        if rows.empty:
            continue
        totals = np.column_stack([
            rows[f].to_numpy(dtype=float) if f in rows.columns else np.full(len(rows), np.nan)
            for f in species
        ])                                                   # (n, виды)
        blocks.append(totals[:, :, None] * shares[None, :, :])  # NaN сохраняется
        metas.append(rows[[c for c in META_COLUMNS if c in rows.columns]].copy())

    meta = pd.concat(metas, ignore_index=True)
    meta.insert(0, "Id", np.arange(1, len(meta) + 1))
    meta["Area"] = meta["Area"].astype(float).fillna(0.0)
    return HaulCatch(
        gear=gear, waterbody=waterbody, meta=meta, species=species, ages=ages, years=years,
        values=np.concatenate(blocks, axis=0), shares=np.stack(shares_all), sample_raw=np.stack(samples_all),
    )
