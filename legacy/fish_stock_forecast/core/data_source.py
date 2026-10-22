"""
Чтение исходных данных из папки data_catch исходного проекта.

Файлы data_catch/*.py — это python-модули с таблицами pandas. Мы их
выполняем через runpy (как обычный импорт, но без правки sys.path) и
забираем нужные переменные:

    {водоём}_fish_prop.py        — свойства видов (m0, m1, коэффициенты уловистости ...)
    {водоём}_catch_{год}.py      — {водоём}_catch_{год}: все уловы года (строка = один улов)
                                   qty_treated_fish_{год}: возрастная проба (штук по возрастам)

Годовой улов по возрастам считается так же, как в save_catch_3d.py:
к пробе прибавляется 1 для возрастов <= m1, доли нормируются по всем
возрастам таблицы, и годовой улов вида распределяется по этим долям.
"""
from __future__ import annotations

import re
import runpy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# Низкоуровневое чтение модулей с кэшем по времени изменения файла
# ---------------------------------------------------------------------------
@lru_cache(maxsize=64)
def _run_module_cached(path_str: str, mtime: float) -> dict:
    return runpy.run_path(path_str)


def _run_module(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл исходных данных: {path}")
    return _run_module_cached(str(path), path.stat().st_mtime)


def _data_catch_dir(data_dir: Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else config.DATA_CATCH_DIR


# ---------------------------------------------------------------------------
# Свойства видов
# ---------------------------------------------------------------------------
@dataclass
class FishProps:
    """Свойства видов рыб водоёма (те же словари, что возвращает get_fish_prop)."""
    lake_area_km2: dict        # площадь водоёма по годам, км²
    net_hours: dict            # время стоянки сети по годам, ч
    net_length: dict           # длина сети по годам, м
    cruise_speed: dict         # крейсерская скорость рыбы, м/с (v_cr_dict)
    k_net: dict                # средний коэффициент уловистости сети по видам
    k_seine: dict              # средний коэффициент уловистости невода по видам
    m0: dict                   # возраст половой зрелости
    m1: dict                   # максимальный возраст
    m2: dict                   # возраст, до которого рыба — корм хищников
    is_predator: dict
    fecundity: dict            # (мин, макс) икринок на самку
    fry_density: dict          # максимальное количество мальков
    weights: dict              # вид -> DataFrame (index=age, columns=годы), граммы

    @property
    def species(self) -> list[str]:
        """Виды, для которых заданы максимальный возраст и уловистость невода."""
        return [s for s in self.m1 if s in self.k_seine]


def load_fish_props(waterbody: str = config.WATERBODY, data_dir: Path | None = None) -> FishProps:
    mod = _run_module(_data_catch_dir(data_dir) / f"{waterbody}_fish_prop.py")

    weights = {}
    for fish, var_name in mod.get("fish_list_dict", {}).items():
        df = mod.get(var_name)
        if isinstance(df, pd.DataFrame):
            w = df.drop(columns=["LessAge"]).set_index("age")
            w.columns = [int(c) for c in w.columns]
            weights[fish] = w.astype(float)

    return FishProps(
        lake_area_km2=dict(mod["square_by_years"]),
        net_hours=dict(mod["time_net_hour"]),
        net_length=dict(mod["net_length"]),
        cruise_speed=dict(mod["v_cr_dict"]),
        k_net=dict(mod["k_catchability_1"]),
        k_seine=dict(mod["k_catchability_2"]),
        m0=dict(mod["m0_dict"]),
        m1=dict(mod["m1_dict"]),
        m2=dict(mod["m2_dict"]),
        is_predator=dict(mod["fish_is_predator_dict"]),
        fecundity=dict(mod["fecundity_dict"]),
        fry_density=dict(mod["fish_density_dict"]),
        weights=weights,
    )


# ---------------------------------------------------------------------------
# Уловы и возрастные пробы
# ---------------------------------------------------------------------------
def list_catch_years(waterbody: str = config.WATERBODY, data_dir: Path | None = None) -> list[int]:
    years = []
    for p in _data_catch_dir(data_dir).glob(f"{waterbody}_catch_*.py"):
        m = re.search(r"_catch_(\d{4})\.py$", p.name)
        if m:
            years.append(int(m.group(1)))
    return sorted(years)


_NET_RENAME = re.compile(r"^(\s*\w+\.loc\[.*'Instrument'\]\s*=\s*'сеть'\s*)$", re.M)


@lru_cache(maxsize=64)
def _raw_instruments_cached(path_str: str, mtime: float, table: str):
    """Колонка Instrument до замены «Сети 20-80 мм» → «сеть» (строки замены в файле пропускаются)."""
    src = Path(path_str).read_text(encoding="utf-8")
    src = _NET_RENAME.sub(lambda m: "pass  # " + m.group(1).strip(), src)
    try:
        ns: dict = {}
        exec(compile(src, path_str, "exec"), ns)
        tbl = ns.get(table)
        return list(tbl["Instrument"].astype(str)) if isinstance(tbl, pd.DataFrame) else None
    except Exception:
        return None


def net_panel_count(catch_type) -> int:
    """Число сетей одного размера ячеи в лове: по типу лова (config.NET_PANELS_BY_CATCH_TYPE)."""
    return int(config.NET_PANELS_BY_CATCH_TYPE.get(str(catch_type).strip().lower(), config.NET_PANELS_DEFAULT))


def load_year(year: int, waterbody: str = config.WATERBODY, data_dir: Path | None = None):
    """Возвращает (таблица уловов года, возрастная проба года).

    Проба: DataFrame, index = возраст (int), columns = виды, значения = штук рыб.
    """
    mod = _run_module(_data_catch_dir(data_dir) / f"{waterbody}_catch_{year}.py")

    catches = mod.get(f"{waterbody}_catch_{year}")
    if not isinstance(catches, pd.DataFrame):
        raise ValueError(f"В файле {waterbody}_catch_{year}.py нет таблицы {waterbody}_catch_{year}")

    sample_key = f"qty_treated_fish_{year}"
    if sample_key not in mod:  # как в calc_stock_npc.py: ищем любую qty_treated_fish_*
        sample_key = next((k for k in mod if k.startswith("qty_treated_fish_")), None)
    if sample_key is None:
        raise ValueError(f"В файле {waterbody}_catch_{year}.py нет возрастной пробы qty_treated_fish_{year}")

    path = _data_catch_dir(data_dir) / f"{waterbody}_catch_{year}.py"
    raw = _raw_instruments_cached(str(path), path.stat().st_mtime, f"{waterbody}_catch_{year}")
    catches = catches.copy()
    if raw is not None and len(raw) == len(catches):
        catches["Instrument_raw"] = raw
    else:
        catches["Instrument_raw"] = catches["Instrument"].astype(str)
    ctype = catches["CatchType"] if "CatchType" in catches else pd.Series([""] * len(catches))
    catches["NetPanels"] = [net_panel_count(t) if g == config.GEAR_NET else 1
                            for t, g in zip(ctype, catches["Instrument"])]

    sample = mod[sample_key].copy()
    sample = sample.drop(columns=["LessAge"]).set_index("age")
    sample.index = sample.index.astype(int)
    return catches.copy(), sample.astype(float)


def load_npc(waterbody: str = config.WATERBODY, data_dir: Path | None = None):
    """Оценка запаса НПЦ (как в файле) и ПДУ НПЦ в тоннах: два DataFrame, index = год.

    Возвращает (None, None), если файла {водоём}_npc_assessment.py нет.
    """
    path = _data_catch_dir(data_dir) / f"{waterbody}_npc_assessment.py"
    if not path.exists():
        return None, None
    mod = _run_module(path)
    out = []
    for name in ("data_stock_npc", "data_pdu_npc"):
        df = mod.get(name)
        out.append(df.set_index("Id").astype(float) if isinstance(df, pd.DataFrame) else None)
    return tuple(out)


@dataclass
class YearlyCatchByAge:
    """Годовой улов одного вида одним орудием лова по возрастам."""
    species: str
    year: int
    gear: str
    ages: np.ndarray            # все возрасты таблицы пробы (обычно 2..16)
    sample_raw: np.ndarray      # проба, штук (как в исходных данных)
    sample_smoothed: np.ndarray # проба, сглаженная smooth_age_sample (config.AGE_PSEUDOCOUNT_TOTAL)
    shares: np.ndarray          # доли возрастов (сумма = 1)
    total_catch: float          # суммарный улов вида орудием за год, штук
    catch_by_age: np.ndarray    # Y_ij(t) = total_catch * shares, штук
    n_hauls: int                # число уловов орудием за год


def smooth_age_sample(raw, ages, m1: int, neighbours=()) -> np.ndarray:
    """Сглаженная возрастная проба вида за год (config.AGE_PSEUDOCOUNT_TOTAL, AGE_POOL_MIN_SAMPLE).

    raw — проба года по возрастам ages; neighbours — пробы соседних лет (те же возрасты),
    прибавляются, если в пробе года меньше AGE_POOL_MIN_SAMPLE рыб.
    """
    raw = np.asarray(raw, float)
    ages = np.asarray(ages)
    used = raw
    if raw.sum() < config.AGE_POOL_MIN_SAMPLE and len(neighbours):
        used = raw + np.sum([np.asarray(n, float) for n in neighbours], axis=0)
    mask = (ages <= m1).astype(float)
    if config.AGE_PSEUDOCOUNT_TOTAL is None:
        return used + mask
    n_groups = mask.sum()
    return used + (config.AGE_PSEUDOCOUNT_TOTAL / n_groups if n_groups else 0.0) * mask


def neighbour_samples(samples: dict, year: int, fish: str, ages) -> list:
    """Пробы вида в соседних годах (± config.AGE_POOL_NEIGHBOURS), приведённые к возрастам ages."""
    out = []
    for dy in range(1, int(config.AGE_POOL_NEIGHBOURS) + 1):
        for y in (year - dy, year + dy):
            s = samples.get(y)
            if s is not None and fish in s.columns:
                out.append(s[fish].reindex(ages, fill_value=0.0).to_numpy(dtype=float))
    return out


def load_samples(waterbody: str = config.WATERBODY, data_dir: Path | None = None) -> dict:
    """{год: возрастная проба года} для всех лет."""
    return {y: load_year(y, waterbody, data_dir)[1] for y in list_catch_years(waterbody, data_dir)}


def yearly_catch_by_age(
    gear: str = config.GEAR_SEINE,
    waterbody: str = config.WATERBODY,
    data_dir: Path | None = None,
    props: FishProps | None = None,
) -> dict[tuple[str, int], YearlyCatchByAge]:
    """Годовые уловы по возрастам для всех видов и лет: ключ (вид, год)."""
    props = props or load_fish_props(waterbody, data_dir)
    result: dict[tuple[str, int], YearlyCatchByAge] = {}

    samples = load_samples(waterbody, data_dir)
    for year in list_catch_years(waterbody, data_dir):
        catches, sample = load_year(year, waterbody, data_dir)
        gear_rows = catches[catches["Instrument"] == gear]
        ages = sample.index.to_numpy()

        for fish in props.species:
            if fish not in sample.columns:
                continue
            raw = sample[fish].to_numpy(dtype=float)
            smoothed = smooth_age_sample(raw, ages, props.m1[fish], neighbour_samples(samples, year, fish, ages))
            total_sample = smoothed.sum()
            shares = smoothed / total_sample if total_sample > 0 else np.zeros_like(smoothed)

            total = float(gear_rows[fish].sum()) if fish in gear_rows.columns else 0.0
            result[(fish, year)] = YearlyCatchByAge(
                species=fish,
                year=year,
                gear=gear,
                ages=ages,
                sample_raw=raw,
                sample_smoothed=smoothed,
                shares=shares,
                total_catch=total,
                catch_by_age=total * shares,
                n_hauls=int(len(gear_rows)),
            )
    return result
