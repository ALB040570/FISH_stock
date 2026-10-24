"""
Запас в тоннах (алгоритмы e, f, g каталога, решение № 70): запас по возрастам × средний вес возраста года.
Веса — те же, что в распределении ПДУ НПЦ по возрастам (pdu_npc.filled_weights: пропуск веса — вес младшего
возраста). Новых формул нет: то же умножение, что «промысловая биомасса» в ПДУ НПЦ.

Две величины: все учитываемые возрасты (2 … m1, как суммарный запас в штуках) и промысловые (m0 … m1).
"""
from __future__ import annotations

import numpy as np

from .pdu_npc import filled_weights


def weights_cube(props, years, species, ages) -> np.ndarray:
    """(годы, виды, возрасты) — средний вес, г."""
    w = np.zeros((len(years), len(species), len(ages)))
    for si, fish in enumerate(species):
        w[:, si, :], _ = filled_weights(props, fish, years, ages)
    return w


def tonnes(cube: np.ndarray, props, years, species, ages, fishable: bool) -> np.ndarray:
    """(годы, виды) — запас, т; NaN, если запаса по учитываемым возрастам нет."""
    ages = np.asarray(ages)
    w = weights_cube(props, years, species, ages)
    out = np.full((len(years), len(species)), np.nan)
    for si, fish in enumerate(species):
        lo = props.m0[fish] if fishable else 2
        m = (ages >= lo) & (ages <= props.m1[fish])
        part = cube[:, si, :][:, m]
        has = ~np.all(np.isnan(part), axis=1)
        val = np.nansum(part * w[:, si, :][:, m], axis=1) / 1e6
        out[:, si] = np.where(has, val, np.nan)
    return out
