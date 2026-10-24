"""
Период расчёта (решение № 70): расчёт алгоритма может быть выполнен за часть лет, а результат другого расчёта,
взятый входом, — за больший период. Здесь только отбор лет из уже посчитанных объектов (без пересчёта):
уловы по ловам, коэффициенты уловистости, запас по уловам. Формулы не меняются.
"""
from __future__ import annotations

import copy

import numpy as np


def common_years(*lists) -> list[int]:
    """Годы, которые есть во всех списках (по возрастанию); None — список не ограничивает."""
    sets = [set(int(y) for y in lst) for lst in lists if lst is not None]
    if not sets:
        return []
    out = sets[0]
    for s in sets[1:]:
        out &= s
    return sorted(out)


def year_index(years, keep) -> list[int]:
    pos = {int(y): i for i, y in enumerate(years)}
    return [pos[int(y)] for y in keep]


def select_catch(hc, keep):
    """HaulCatch только за годы keep; возвращает (новый объект, маска ловов) — маской режутся массивы по ловам."""
    from .catch import HaulCatch
    keep = [int(y) for y in keep]
    idx = year_index(hc.years, keep)
    mask = hc.meta["Year"].astype(int).isin(keep).to_numpy() if len(hc.meta) else np.zeros(0, bool)
    meta = hc.meta[mask].reset_index(drop=True)
    return HaulCatch(gear=hc.gear, waterbody=hc.waterbody, meta=meta, species=list(hc.species), ages=hc.ages,
                     years=keep, values=hc.values[mask], shares=hc.shares[idx], sample_raw=hc.sample_raw[idx]), mask


def select_fits(obj, keep):
    """Уловистость (SeineCatchability / NetCatchability) только за годы keep."""
    keep = [int(y) for y in keep]
    out = copy.copy(obj)
    out.years = keep
    out.fits = {k: v for k, v in obj.fits.items() if int(k[1]) in set(keep)}
    return out


def select_stock(res, keep):
    """StockResult только за годы keep (уловы, уловистость, σ, оценки по ловам, годовой запас, НПЦ)."""
    keep = [int(y) for y in keep]
    if [int(y) for y in res.years] == keep:
        return res
    idx = year_index(res.years, keep)
    out = copy.copy(res)
    out.years = keep
    out.catches, masks = {}, {}
    for g, hc in res.catches.items():
        out.catches[g], masks[g] = select_catch(hc, keep)
    out.catchability = {k: v[idx] for k, v in res.catchability.items()}
    out.sigma = {k: v[idx] for k, v in res.sigma.items()}
    out.per_haul = {k: v[masks[k[0]]] for k, v in res.per_haul.items()}
    out.yearly = {k: v[idx] for k, v in res.yearly.items()}
    out.npc_stock = None if res.npc_stock is None else res.npc_stock[idx]
    return out


def years_title(years) -> str:
    years = [int(y) for y in years]
    if not years:
        return "—"
    if years == list(range(years[0], years[-1] + 1)):
        return f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])
    return ", ".join(map(str, years))


def select_gear_state(st: dict, keep) -> dict:
    """Состояние алгоритмов c–f (одно орудие) только за годы keep."""
    keep = [int(y) for y in keep]
    if [int(y) for y in st["years"]] == keep:
        return st
    idx = year_index(st["years"], keep)
    hc, mask = select_catch(st["catch"], keep)
    out = dict(st)
    out.update(catch=hc, per_haul=st["per_haul"][mask], cube=st["cube"][idx], area=st["area"][idx], years=keep)
    if "sigma" in st:
        out.update(sigma=st["sigma"][idx], hours=[st["hours"][i] for i in idx], length=[st["length"][i] for i in idx])
    for k in ("yearly", "tonnes_all", "tonnes_fishable"):
        if k in st:
            out[k] = st[k][idx]
    return out


def select_pdu(pdu, keep):
    """Результат распределения ПДУ НПЦ по возрастам (PduResult) только за годы keep."""
    keep = [int(y) for y in keep]
    if [int(y) for y in pdu.years] == keep:
        return pdu
    idx = year_index(pdu.years, keep)
    out = copy.copy(pdu)
    out.years = keep
    for k in ("stock", "weights", "pieces", "capped", "pdu_t", "left_t", "iterations"):
        setattr(out, k, getattr(pdu, k)[idx])
    out.stop_reason = [pdu.stop_reason[i] for i in idx]
    return out
