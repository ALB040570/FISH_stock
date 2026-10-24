"""
Повозрастное распределение ПДУ НПЦ в штуках (раздел 5 статьи, аналог calc_pdu_in_pieces.py).

Для вида i и года t (индексы опущены), возраст j (группа less_j: от j−1 до j лет):

    X_j      — окончательный годовой запас возраста: средневзвешенное сети и невода по числу ловов
               (config.COMBINE_GEARS; простое среднее (29) — по настройке)
    w_j      — средний вес рыбы, г
    M_j = 1, если j >= m0 (ловятся только половозрелые), иначе 0
    P        — ПДУ НПЦ, т → г (× 10⁶);  A_j = 0

    итерация k:
        X_j^(k) = X_j − A_j                                   (30)
        B_j = X_j^(k) · w_j · M_j                              (31)
        B̃_j = B_j · j / m1                                    — нагрузка растёт с возрастом
        μ_j = B̃_j / Σ B̃_j
        ΔA_j = P · μ_j / w_j,   ΔA_j = min(ΔA_j, 0.75 · X_j^(k))
        A_j += ΔA_j;   P = max(P − Σ ΔA_j · w_j, 0)

Итерации продолжаются, пока квота не исчерпана и есть свободный запас
(решение автора: не ограничиваться тремя итерациями, как в статье и старом коде).

Средний вес для возрастов до m1, которых нет в таблице весов, берётся от ближайшего
младшего возраста (у язя вес возраста 12–13 = вес возраста 11–12).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .data_source import FishProps, load_npc
from .stock import MEAN, StockResult


@dataclass
class DistributionResult:
    pieces: np.ndarray        # A_j, штук
    left_g: float             # нераспределённый остаток квоты, г
    iterations: int
    capped: np.ndarray        # bool: ограничение 75 % срабатывало хотя бы раз
    stop_reason: str          # "квота исчерпана" | "нет свободного запаса" | "предел итераций" | "нет квоты"


def distribute_pdu(stock, weights, mature, ages, m1, pdu_g,
                   cap: float = config.PDU_CAP, max_iter: int = config.PDU_MAX_ITER,
                   tol_g: float = config.PDU_TOL_G, free_tol_g: float = config.PDU_FREE_STOCK_TOL_G) -> DistributionResult:
    """Распределение квоты pdu_g (граммы) одного вида за один год по возрастам."""
    X = np.nan_to_num(np.asarray(stock, float), nan=0.0).clip(min=0)
    w = np.nan_to_num(np.asarray(weights, float), nan=0.0)
    allowed = np.asarray(mature, bool) & (w > 0)
    load = np.asarray(ages, float) / float(m1)
    A = np.zeros_like(X)
    capped = np.zeros(X.shape, bool)
    P = float(pdu_g) if np.isfinite(pdu_g) else 0.0
    if P <= tol_g:
        return DistributionResult(A, max(P, 0.0), 0, capped, "нет квоты")

    k, reason = 0, "предел итераций"
    while k < max_iter:
        rest = X - A                                         # (30)
        B = np.where(allowed, rest * w, 0.0)                 # (31)
        if B.sum() < free_tol_g:
            reason = "нет свободного запаса"
            break
        Bt = B * load
        mu = Bt / Bt.sum()
        dA = np.where(allowed, P * mu / np.where(w > 0, w, 1.0), 0.0)
        limit = cap * rest
        over = dA > limit
        capped |= over
        dA = np.where(over, limit, dA)
        A += dA
        P = max(P - float((dA * w).sum()), 0.0)
        k += 1
        if P < tol_g:
            reason = "квота исчерпана"
            break
    return DistributionResult(A, P, k, capped, reason)


def filled_weights(props: FishProps, fish: str, years, ages) -> tuple[np.ndarray, np.ndarray]:
    """(годы, возрасты) — средний вес, г; вес недостающих возрастов до m1 — от ближайшего младшего.

    Возвращает (веса, отметка «вес заполнен»).
    """
    W = props.weights.get(fish)
    out = np.zeros((len(years), len(ages)))
    filled = np.zeros(len(ages), bool)
    if W is None:
        return out, filled
    for yi, y in enumerate(years):
        col = W[y] if y in W.columns else W.iloc[:, -1]
        last = 0.0
        for ai, a in enumerate(ages):
            if a in col.index and np.isfinite(col.loc[a]) and col.loc[a] > 0:
                last = float(col.loc[a])
                out[yi, ai] = last
            elif a <= props.m1[fish] and last > 0:
                out[yi, ai] = last
                filled[ai] = True
    return out, filled


@dataclass
class PduResult:
    waterbody: str
    years: list[int]
    species: list[str]
    ages: np.ndarray
    m0: dict
    m1: dict
    stock: np.ndarray               # (годы, виды, возрасты) — окончательный запас, по которому распределяется ПДУ
    weights: np.ndarray             # (годы, виды, возрасты), г
    weight_filled: np.ndarray       # (виды, возрасты) — вес взят от младшего возраста
    pieces: np.ndarray              # (годы, виды, возрасты) — ПДУ, штук
    capped: np.ndarray              # (годы, виды, возрасты)
    pdu_t: np.ndarray               # (годы, виды) — ПДУ НПЦ, т
    left_t: np.ndarray              # (годы, виды) — нераспределено, т
    iterations: np.ndarray          # (годы, виды)
    stop_reason: list = field(default_factory=list)   # [годы][виды]

    def mature_mask(self) -> np.ndarray:
        return np.array([[self.m0[s] <= a <= self.m1[s] for a in self.ages] for s in self.species])

    def distributed_t(self) -> np.ndarray:
        return (self.pieces * self.weights).sum(axis=2) / 1e6

    def fishable_biomass_t(self) -> np.ndarray:
        """(годы, виды) — биомасса половозрелых (возраст >= m0), т."""
        m = self.mature_mask()[None]
        return np.where(m, np.nan_to_num(self.stock) * self.weights, 0.0).sum(axis=2) / 1e6

    def exploitation(self) -> np.ndarray:
        """(годы, виды, возрасты) — доля изъятия A/X."""
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.stock > 0, self.pieces / self.stock, np.nan)

    def summary_frame(self) -> pd.DataFrame:
        dist = self.distributed_t()
        bio = self.fishable_biomass_t()
        rows = []
        for si, fish in enumerate(self.species):
            for yi, year in enumerate(self.years):
                rows.append({
                    "вид": fish, "год": year, "ПДУ НПЦ, т": self.pdu_t[yi, si],
                    "распределено, т": dist[yi, si], "не распределено, т": self.left_t[yi, si],
                    "ПДУ, шт": self.pieces[yi, si].sum(),
                    "промысловая биомасса, т": bio[yi, si],
                    "ПДУ / биомасса, %": 100 * self.pdu_t[yi, si] / bio[yi, si] if bio[yi, si] > 0 else np.nan,
                    "итераций": int(self.iterations[yi, si]), "остановка": self.stop_reason[yi][si],
                })
        return pd.DataFrame(rows)


def compute_pdu(res: StockResult, props: FishProps,
                variant: str = "with_ages", method: str | None = None, data_dir=None) -> PduResult:
    """ПДУ НПЦ в штуках по возрастам по окончательному запасу (сеть+невод) выбранного варианта.

    FishStock: добавлен data_dir (набор данных водоёма); без него — как в исходном проекте."""
    method = method or getattr(res, "method", "on_stock")
    _, pdu_df = load_npc(res.waterbody, data_dir)
    years, species, ages = res.years, res.species, res.ages
    nY, nS, nA = len(years), len(species), len(ages)
    stock = np.nan_to_num(res.yearly[(MEAN, variant, method)], nan=0.0)

    weights = np.zeros((nY, nS, nA))
    filled = np.zeros((nS, nA), bool)
    for si, fish in enumerate(species):
        weights[:, si, :], filled[si] = filled_weights(props, fish, years, ages)

    pieces = np.zeros((nY, nS, nA))
    capped = np.zeros((nY, nS, nA), bool)
    pdu_t = np.full((nY, nS), np.nan)
    left_t = np.zeros((nY, nS))
    iters = np.zeros((nY, nS), int)
    reasons = [["" for _ in species] for _ in years]
    for si, fish in enumerate(species):
        mature = (ages >= props.m0[fish]) & (ages <= props.m1[fish])
        for yi, year in enumerate(years):
            p = float(pdu_df.loc[year, fish]) if (pdu_df is not None and year in pdu_df.index
                                                  and fish in pdu_df.columns) else np.nan
            pdu_t[yi, si] = p
            r = distribute_pdu(stock[yi, si], weights[yi, si], mature, ages, props.m1[fish],
                               p * 1e6 if np.isfinite(p) else 0.0)
            pieces[yi, si], capped[yi, si] = r.pieces, r.capped
            left_t[yi, si], iters[yi, si], reasons[yi][si] = r.left_g / 1e6, r.iterations, r.stop_reason

    return PduResult(res.waterbody, years, species, ages, dict(props.m0), dict(props.m1), stock, weights,
                     filled, pieces, capped, pdu_t, left_t, iters, reasons)
