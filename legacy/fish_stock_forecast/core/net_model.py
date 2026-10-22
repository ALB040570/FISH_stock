"""
Балансовая модель лова сетью (перенос calc_model_for_net из model_for_net.py без изменения логики).

Вокруг сети строятся кольца: круг 0 радиусом r0 = длина сети / 2, кольцо 1 до радиуса V
(V — путь рыбы за час, м/ч), кольцо k — от (k−1)V до kV. Количество рыб задаётся в долях
рыб первого круга (площадь πV² = 1): круг 0 = (r0/V)², кольцо 1 = 1 − (r0/V)², кольцо k = 2k − 1.
Каждый час рыба с вероятностью 1/4 движется к сети, 1/4 — от сети, 1/2 остаётся;
через границу круга 0 и кольца 1 потоки делятся пропорционально длинам границ.
Из встретивших сеть в неё попадает доля k (коэффициент уловистости).

Подшаги в круге 0 (config.NET_ZONE0_SUBSTEPS, решение автора от 16.10.2026). За час рыба проходит
V метров, а радиус круга 0 — r0 = длина сети / 2 (12,5 м), поэтому внутри круга 0 час делится на
n подшагов (по умолчанию n = ⌈V / r0⌉). На каждом подшаге из рыб круга 0: 1/4 встречает сеть
(доля k попадает в неё, остальные остаются в круге 0), 1/4 выходит в кольцо 1, 1/2 остаётся;
приток из кольца 1 за час (тот же, что без подшагов) приходит равными частями после каждого
подшага. Ушедшие из круга 0 попадают в кольцо 1 в конце часа. Кольца 1..12 считаются по часам,
как раньше. При n = 1 модель совпадает с прежней.

σ = доля рыб первого круга, попавших в сеть за время стоянки (столбец «Сеть»).
Запас (config.NET_STOCK_FORMULA):
    "code"    — как calc_stock_net старого проекта:  X = Y · S / (σ · (V² − r0²)),  r0 = длина сети / 2
    "article" — формула (28) статьи:                   X = Y · S / (π V² σ)

Таблица 9 первой редакции статьи получается при k = 0.4, 12 ч, сеть 25 м, V = 72 м/ч, без подшагов.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config


def zone0_substeps(net_width: float, fish_speed: float, substeps=None) -> int:
    """Число подшагов в круге 0 за час: "auto" — ⌈V / r0⌉, число — как задано."""
    substeps = config.NET_ZONE0_SUBSTEPS if substeps is None else substeps
    if substeps == "auto":
        return max(1, int(np.ceil(fish_speed / (net_width / 2.0) - 1e-9)))
    n = int(substeps)
    if n < 1:
        raise ValueError(f"Число подшагов в круге 0 должно быть ≥ 1, задано {substeps}")
    return n


def balance_model(k_catchability: float, hours: int, net_width: float, fish_speed: float, substeps=None,
                  p_to_net: float = 0.25):
    """Возвращает (таблица по часам, итоговое состояние) — как calc_model_for_net.
    substeps — подшаги в круге 0 ("auto", число; None — из config.NET_ZONE0_SUBSTEPS);
    p_to_net — доля рыб круга 0, движущихся к сети за шаг (по умолчанию 1/4; от сети — 1/2 − p_to_net,
    остаются 1/2) — только для анализа чувствительности."""
    if not (0.0 <= p_to_net <= 0.5):
        raise ValueError(f"p_to_net должно быть от 0 до 0,5, задано {p_to_net}")
    hours = int(hours)
    r0 = net_width / 2.0
    r1 = fish_speed
    if r0 >= r1:
        raise ValueError(f"Половина длины сети ({r0} м) не должна превышать путь рыбы за час ({r1} м/ч).")
    n_sub = zone0_substeps(net_width, fish_speed, substeps)

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
    p_in[0], p_out[0] = p_to_net, 0.5 - p_to_net
    if total_areas > 1:
        p_in[1] = 0.5 * r0 / (r0 + r1)
        p_out[1] = 0.5 * r1 / (r0 + r1)
    for idx in range(2, total_areas):
        total_w = float((idx - 1) + idx)
        p_in[idx] = 0.5 * (idx - 1) / total_w
        p_out[idx] = 0.5 * idx / total_w

    for hour in range(1, hours + 1):
        nxt = [0.0] * total_areas
        # круг 0 — n подшагов; приток из кольца 1 за час делится поровну между подшагами
        zone0 = fish[0]
        inflow = p_in[1] * fish[1] / n_sub
        left_zone0 = 0.0
        for _ in range(n_sub):
            met = p_in[0] * zone0
            in_net += met * k_catchability
            left_zone0 += p_out[0] * zone0
            zone0 = 0.5 * zone0 + (1 - k_catchability) * met + inflow
        nxt[0] = zone0
        nxt[1] = 0.5 * fish[1] + left_zone0 + (p_in[2] * fish[2] if total_areas > 2 else 0.0)
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
def _net_share_cached(k: float, hours: int, net_width: float, fish_speed: float, substeps) -> float:
    if k <= 0:
        return 0.0
    return balance_model(k, hours, net_width, fish_speed, substeps)[1]["Сеть"]


def net_share(k_catchability: float, hours: int, net_width: float, fish_speed: float, substeps=None) -> float:
    """σ — доля рыб первого круга, попавших в сеть за время стоянки."""
    substeps = config.NET_ZONE0_SUBSTEPS if substeps is None else substeps
    return _net_share_cached(round(float(k_catchability), 12), int(hours), float(net_width), float(fish_speed),
                             substeps)


def net_share_array(k: np.ndarray, hours: int, net_width: float, fish_speed: float, substeps=None) -> np.ndarray:
    k = np.asarray(k, float)
    return np.vectorize(lambda v: net_share(v, hours, net_width, fish_speed, substeps), otypes=[float])(k)


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


def stock_from_net_catch(catch, k_catchability, hours, net_width, fish_speed, lake_area_m2, formula=None,
                         substeps=None):
    """Запас по улову сетью. σ = 0 (уловистость 0) → запас 0."""
    sigma = net_share_array(k_catchability, hours, net_width, fish_speed, substeps)
    denom = net_denominator(fish_speed, net_width, sigma, formula)
    catch = np.asarray(catch, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.where(denom > 0, catch * lake_area_m2 / np.where(denom > 0, denom, 1.0), 0.0)
    return np.where(np.isnan(catch), np.nan, x)
