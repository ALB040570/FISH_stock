"""
Чувствительность оценки запаса по сетям к параметрам модели баланса (ответ рецензентам, без MCMC).

Запас по сети X = Y · S / знаменатель(V, σ(k, часы, V, p_to_net)), поэтому при том же улове Y и площади S
отношение X(вариант) / X(база) = знаменатель(база) / знаменатель(вариант). Базовые значения по видам:
V — крейсерская скорость × 3600 м/ч, k — средняя уловистость сети вида, часы и длина сети — последнего года.
Варианты: V × 0,5…1,5; k × 0,5…1,5 (не больше 1); время стоянки × 0,5…1,5; p_to_net 0,15…0,35.

Результат: results/net_balance_sensitivity.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import config
from .net_model import balance_model, net_denominator

FACTORS = (0.5, 0.75, 1.25, 1.5)
P_TO_NET = (0.15, 0.2, 0.3, 0.35)


def _denominator(k: float, hours: float, width: float, speed: float, p_to_net: float = 0.25) -> float:
    sigma = balance_model(k, int(round(hours)), width, speed, p_to_net=p_to_net)[1]["Сеть"]
    return float(net_denominator(speed, width, sigma))


def species_table(species: str, speed: float, k: float, hours: float, width: float) -> list[dict]:
    """Строки таблицы для одного вида: параметр, значение, множитель запаса относительно базы."""
    base = _denominator(k, hours, width, speed)
    rows = [{"species": species, "parameter": "база", "value": None, "rel_change": 0.0, "stock_factor": 1.0}]

    def add(name, value, rel, **kw):
        args = dict(k=k, hours=hours, width=width, speed=speed)
        args.update(kw)
        try:
            d = _denominator(args["k"], args["hours"], args["width"], args["speed"], args.get("p_to_net", 0.25))
            f = base / d if d > 0 else np.nan
        except ValueError:                  # например, половина сети длиннее пути рыбы за час
            f = np.nan
        rows.append({"species": species, "parameter": name, "value": value, "rel_change": rel, "stock_factor": f})

    for f in FACTORS:
        add("V, м/ч", speed * f, f - 1, speed=speed * f)
    for f in FACTORS:
        add("k", min(k * f, 1.0), min(k * f, 1.0) / k - 1, k=min(k * f, 1.0))
    for f in FACTORS:
        h = max(1, int(round(hours * f)))
        add("время стоянки, ч", h, h / hours - 1, hours=h)
    for p in P_TO_NET:
        add("p_to_net", p, p / 0.25 - 1, p_to_net=p)
    for r in rows:
        r.update({"V_base": speed, "k_base": k, "hours_base": hours, "net_length": width})
    return rows


def balance_sensitivity(species_list=None, props=None, out: Path | None = None) -> Path:
    """Таблица по видам → CSV."""
    import pandas as pd

    from .bayes.config import DEFAULTS
    from .data_source import load_fish_props

    props = props or load_fish_props()
    years = sorted(props.net_hours)
    y = years[-1]
    hours = float(props.net_hours[y])
    width = float(props.net_length.get(y, list(props.net_length.values())[-1]))
    rows = []
    for sp in species_list or list(DEFAULTS):
        if sp not in props.cruise_speed or sp not in props.k_net:
            continue
        rows += species_table(sp, float(props.cruise_speed[sp]) * 3600.0, float(props.k_net[sp]), hours, width)
    out = Path(out or config.RESULTS_DIR / "net_balance_sensitivity.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    return out
