"""
Подбор масштаба выживаемости икры egg_scale для вида водоёма (решение № 73).

Правило: при медианах (модах) априорных распределений всех параметров детерминированная траектория модели —
численность возрастов 2..m1 по годам (уравнения (16)-(17), dynamics.simulate) — должна идти на уровне оценок
запаса по тем орудиям, которые входят в правдоподобие (сеть и невод — окончательный запас g; только сеть или
только невод — годовой запас этим орудием). Критерий — наименьшее среднеквадратичное отклонение логарифмов по
годам с оценкой больше 0; перебор по сетке от 10⁻⁶ до 1 (61 точка, логарифмический шаг), результат округляется
до двух значащих цифр.

Остальные априорные значения не меняются. Масштаб умножает выживаемость икры Beta(α, β), поэтому апостериорная
выживаемость икры по-прежнему уточняется данными в пределах этого распределения.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from .config import SpeciesConfig
from .dynamics import NumpyOps, prior_means, simulate
from .inputs import BayesInputs

GRID = np.exp(np.linspace(np.log(1e-6), np.log(1.0), 61))


def target_totals(inp: BayesInputs, cfg: SpeciesConfig) -> np.ndarray:
    """Оценки запаса по годам (возрасты 2..m1) для орудий правдоподобия."""
    src = {"net": inp.yearly_net, "seine": inp.yearly_seine}.get(cfg.likelihood_gears, inp.yearly_final)
    if src is None:
        src = inp.yearly_final
    return np.nansum(np.asarray(src, float), axis=1)


def trajectory(inp: BayesInputs, cfg: SpeciesConfig) -> np.ndarray:
    """Численность возрастов 2..m1 по годам при медианах априорных распределений."""
    out = simulate(NumpyOps, prior_means(inp.consts, cfg), inp.consts, cfg)
    return np.asarray(out["X_estimated"], float)[:, 1:].sum(axis=1)


def _rmse_log(x: np.ndarray, obs: np.ndarray) -> float:
    ok = np.isfinite(obs) & (obs > 0)
    if not ok.any():
        return float("nan")
    return float(np.sqrt(np.mean((np.log(np.maximum(x[ok], 1.0)) - np.log(obs[ok])) ** 2)))


def round_sig(x: float, n: int = 2) -> float:
    return float(f"{x:.{n}g}")


def fit_egg_scale(inp: BayesInputs, cfg: SpeciesConfig, grid: np.ndarray = GRID) -> dict:
    """Подобранный egg_scale и траектории «сейчас / после подбора» для отчёта."""
    obs = target_totals(inp, cfg)
    cur = trajectory(inp, cfg)
    best_es, best_err = None, np.inf
    for es in grid:
        err = _rmse_log(trajectory(inp, replace(cfg, egg_scale=float(es))), obs)
        if np.isfinite(err) and err < best_err:
            best_es, best_err = float(es), err
    if best_es is None:
        return {"current": cfg.egg_scale, "suggested": None, "rmse_current": None, "rmse_suggested": None,
                "years": list(inp.years), "target": obs.tolist(), "traj_current": cur.tolist(), "traj_suggested": None}
    sug = round_sig(best_es)
    traj = trajectory(inp, replace(cfg, egg_scale=sug))
    return {"current": cfg.egg_scale, "suggested": sug, "rmse_current": _rmse_log(cur, obs),
            "rmse_suggested": _rmse_log(traj, obs), "years": list(inp.years), "target": obs.tolist(),
            "traj_current": cur.tolist(), "traj_suggested": traj.tolist(), "at_grid_edge": best_es in (grid[0], grid[-1])}
