"""
Балансовая модель лова сетью (перенос calc_model_for_net из model_for_net.py без изменения логики).

Вокруг сети строятся кольца: круг 0 радиусом r0 = длина сети / 2, кольцо 1 до радиуса V
(V — путь рыбы за час, м/ч), кольцо k — от (k−1)V до kV. Количество рыб задаётся в долях
рыб первого круга (площадь πV² = 1): круг 0 = (r0/V)², кольцо 1 = 1 − (r0/V)², кольцо k = 2k − 1.
Каждый час рыба с вероятностью 1/4 движется к сети, 1/4 — от сети, 1/2 остаётся;
через границу круга 0 и кольца 1 потоки делятся пропорционально длинам границ.
Из встретивших сеть в неё попадает доля k (коэффициент уловистости).

σ = доля рыб первого круга, попавших в сеть за время стоянки (столбец «Сеть»).
Запас (config.NET_STOCK_FORMULA):
    "code"    — как calc_stock_net старого проекта:  X = Y · S / (σ · (V² − r0²)),  r0 = длина сети / 2
    "article" — формула (28) статьи:                   X = Y · S / (π V² σ)

Таблица 9 статьи получается при k = 0.4, 12 ч, сеть 25 м, V = 72 м/ч.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config


def balance_model(k_catchability: float, hours: int, net_width: float, fish_speed: float):
    """Возвращает (таблица по часам, итоговое состояние) — как calc_model_for_net."""
    hours = int(hours)
    r0 = net_width / 2.0
    r1 = fish_speed
    if r0 >= r1:
        raise ValueError(f"Половина длины сети ({r0} м) не должна превышать путь рыбы за час ({r1} м/ч).")

    total_areas = 1 + hours
    fish = [0.0] * total_areas
    fish[0] = (r0 / r1) ** 2
    fish[1] = 1.0 - (r0 / r1) ** 2
    for idx in range(2, total_areas):
        fish[idx] = float(2 * idx - 1)

    in_net = 0.0
    history = [{"Час": 0, "Сеть": in_net, "Круг 0": fish[0],
                **{f"Кольцо {i}": fish[i] for i in range(1, total_areas)}, "Баланс": in_net + sum(fish)}]

    p_in = [0.0] * total_areas
    p_out = [0.0] * total_areas
    p_in[0], p_out[0] = 0.25, 0.25
    if total_areas > 1:
        p_in[1] = 0.5 * r0 / (r0 + r1)
        p_out[1] = 0.5 * r1 / (r0 + r1)
    for idx in range(2, total_areas):
        total_w = float((idx - 1) + idx)
        p_in[idx] = 0.5 * (idx - 1) / total_w
        p_out[idx] = 0.5 * idx / total_w

    for hour in range(1, hours + 1):
        nxt = [0.0] * total_areas
        in_net += p_in[0] * fish[0] * k_catchability
        nxt[0] = 0.5 * fish[0] + (1 - k_catchability) * p_in[0] * fish[0] + p_in[1] * fish[1]
        nxt[1] = 0.5 * fish[1] + p_out[0] * fish[0] + (p_in[2] * fish[2] if total_areas > 2 else 0.0)
        for idx in range(2, total_areas - 1):
            nxt[idx] = 0.5 * fish[idx] + p_out[idx - 1] * fish[idx - 1] + p_in[idx + 1] * fish[idx + 1]
        if total_areas > 2:
            nxt[-1] = 0.5 * fish[-1] + p_out[-2] * fish[-2] + p_out[-1] * fish[-1]
        fish = nxt
        history.append({"Час": hour, "Сеть": in_net, "Круг 0": fish[0],
                        **{f"Кольцо {i}": fish[i] for i in range(1, total_areas)},
                        "Баланс": in_net + sum(fish)})

    final_state = {"Сеть": in_net, "Круг 0": fish[0], **{f"Кольцо {i}": fish[i] for i in range(1, total_areas)}}
    return pd.DataFrame(history), final_state


@lru_cache(maxsize=100_000)
def _net_share_cached(k: float, hours: int, net_width: float, fish_speed: float) -> float:
    if k <= 0:
        return 0.0
    return balance_model(k, hours, net_width, fish_speed)[1]["Сеть"]


def net_share(k_catchability: float, hours: int, net_width: float, fish_speed: float) -> float:
    """σ — доля рыб первого круга, попавших в сеть за время стоянки."""
    return _net_share_cached(round(float(k_catchability), 12), int(hours), float(net_width), float(fish_speed))


def net_share_array(k: np.ndarray, hours: int, net_width: float, fish_speed: float) -> np.ndarray:
    k = np.asarray(k, float)
    return np.vectorize(lambda v: net_share(v, hours, net_width, fish_speed), otypes=[float])(k)


def net_denominator(fish_speed, net_width, sigma, formula: str | None = None):
    """Знаменатель формулы запаса по сетям (площадь облова × σ), м²."""
    formula = formula or config.NET_STOCK_FORMULA
    fish_speed = np.asarray(fish_speed, float)
    if formula == "article":
        return np.pi * fish_speed ** 2 * sigma
    if formula == "code":
        r0 = np.asarray(net_width, float) / 2.0
        return (fish_speed ** 2 - r0 ** 2) * sigma
    raise ValueError(f"Неизвестная формула запаса по сетям: {formula}")


def stock_from_net_catch(catch, k_catchability, hours, net_width, fish_speed, lake_area_m2, formula=None):
    """Запас по улову сетью. σ = 0 (уловистость 0) → запас 0."""
    sigma = net_share_array(k_catchability, hours, net_width, fish_speed)
    denom = net_denominator(fish_speed, net_width, sigma, formula)
    catch = np.asarray(catch, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.where(denom > 0, catch * lake_area_m2 / np.where(denom > 0, denom, 1.0), 0.0)
    return np.where(np.isnan(catch), np.nan, x)
