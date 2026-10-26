"""
Входные данные байесовской модели одного вида.

Режим "new" — из результатов этапов 2–3 этого приложения:
    правдоподобие — оценки запаса по каждому лову (сеть, затем невод) с учётом возрастов, возрасты 2..m1;
    орудие каждого лова (gear) известно — по нему в модели применяется поправка уловистости сети q_net;
    вылов A_j(t) — ПДУ НПЦ по возрастам в штуках (этап 3);
    начальный запас — окончательный годовой запас по возрастам за первый год (средневзвешенное сети
    и невода по числу ловов, «по запасам»); сеголетки 0–1 рассчитываются внутри модели, как в старом коде.

Режим "check" — входные данные старого проекта: вызывается prepare_data_for_bayes из скрипта вида
(папка src исходного проекта). Нужен, чтобы сравнить новую модель со старыми .nc.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config as app_config
from .config import GEAR_CODES, SpeciesConfig, parse_stocking
from .dynamics import Constants, maturity, zero_log_ref

GEAR_NAMES = ("сеть", "невод")
GEAR_TITLES = {"net": "сеть", "seine": "невод"}


@dataclass
class BayesInputs:
    species: str
    mode: str                         # "new" | "check"
    years: list[int]
    consts: Constants
    stock: np.ndarray                 # (ловы, m1 − 1) оценки запаса по ловам, возрасты 2..m1, + obs_pad
    year_idx: np.ndarray              # (ловы,) номер года лова
    gear: np.ndarray                  # (ловы,) 0 — сеть, 1 — невод (для поправки уловистости сети q_net)
    zero: np.ndarray | None = None    # (ловы,) True — в лове нет рыбы вида (все оценки 0 до добавки obs_pad)
    zero_ref: float | None = None     # ln N̄ для вероятности пустого лова — константа исходных данных (не меняется
                                      # при отсечении лет и в синтетических данных проверки восстановления)
    dropped: int = 0                  # ловов исключено (вид не учитывался)
    # для графиков: данные, по которым оценивалась модель (NaN — нет оценки)
    yearly_final: np.ndarray | None = None    # (годы, m1 − 1) окончательный запас по возрастам
    yearly_net: np.ndarray | None = None      # (годы, m1 − 1)
    yearly_seine: np.ndarray | None = None    # (годы, m1 − 1)
    npc_total: np.ndarray | None = None       # (годы,) оценка НПЦ, штук
    pdu_raw: np.ndarray | None = None         # (годы, m1 − 1) ПДУ без +0,1
    notes: list[str] = field(default_factory=list)

    @property
    def zero_mask(self) -> np.ndarray:
        """Пустые ловы; если не заданы — восстанавливаются по добавке obs_pad (все оценки ≤ добавки)."""
        if self.zero is not None:
            return np.asarray(self.zero, bool)
        return np.all(self.stock <= self.stock.min() * (1 + 1e-9), axis=1)

    def log_ref(self, cfg) -> float:
        return float(self.zero_ref) if self.zero_ref is not None else zero_log_ref(self.stock, self.zero_mask, cfg)

    @property
    def obs_ages(self) -> np.ndarray:
        return np.arange(2, self.consts.m1 + 1)

    @property
    def model_ages(self) -> np.ndarray:
        return np.arange(1, self.consts.m1 + 1)


def _capacity(area_km2: np.ndarray, density: float) -> np.ndarray:
    """Ёмкость нерестилищ по малькам: 10 % площади водоёма × норматив × 10 (как в старом коде)."""
    square_m2 = np.asarray(area_km2, float) * 1000000
    return square_m2 * 0.10 * density * 10


# ---------------------------------------------------------------- режим "new"


def build_new_inputs(species: str, cfg: SpeciesConfig, res=None, pdu=None, props=None) -> BayesInputs:
    """Входные данные из результатов этапов 2–3 (если не переданы — рассчитываются)."""
    from ..data_source import load_fish_props
    from ..pdu_npc import compute_pdu
    from ..stock import MEAN, compute_stock

    props = props or load_fish_props()
    if res is None:
        res, _, _ = compute_stock(props=props)
    if pdu is None:
        pdu = compute_pdu(res, props)

    si = list(res.species).index(species)
    m0, m1, m2 = int(props.m0[species]), int(props.m1[species]), int(props.m2[species])
    ages = np.asarray(res.ages)
    sel = np.array([int(np.where(ages == a)[0][0]) for a in range(2, m1 + 1)])
    years = list(res.years)
    notes = []

    # правдоподобие: ловы сети, затем невода
    parts, yidx, gears = [], [], []
    for g, gear in enumerate((app_config.GEAR_NET, app_config.GEAR_SEINE)):
        arr = res.per_haul[(gear, "with_ages")][:, si, :][:, sel]
        parts.append(arr)
        yidx.append(res.catches[gear].year_index)
        gears.append(np.full(len(arr), g))
    stock = np.concatenate(parts)
    year_idx = np.concatenate(yidx)
    gear = np.concatenate(gears)
    if cfg.likelihood_gears != "both":
        # в правдоподобии только одно орудие (решение № 73): ловы другого орудия не используются
        g_keep = GEAR_CODES[cfg.likelihood_gears]
        keep_g = gear == g_keep
        if not keep_g.any():
            raise ValueError(f"Вид «{species}»: в правдоподобии выбрано «только {GEAR_TITLES[cfg.likelihood_gears]}», "
                             f"но ловов этим орудием в данных нет — выберите другое орудие")
        notes.append(f"в правдоподобии — только оценки по ловам: {GEAR_TITLES[cfg.likelihood_gears]} "
                     f"({int(keep_g.sum())} ловов); поправка уловистости сети q_net не используется")
        stock, year_idx, gear = stock[keep_g], year_idx[keep_g], gear[keep_g]
    unrecorded = np.isnan(stock).all(axis=1)
    dropped = 0
    if cfg.unrecorded == "drop":
        dropped = int(unrecorded.sum())
        keep = ~unrecorded
        stock, year_idx, gear = stock[keep], year_idx[keep], gear[keep]
        if dropped:
            notes.append(f"исключено ловов, где вид не учитывался: {dropped}")
    elif unrecorded.any():
        notes.append(f"ловов, где вид не учитывался, считаются нулевыми: {int(unrecorded.sum())}")
    stock = np.nan_to_num(stock, nan=0.0)
    zero = stock.sum(axis=1) <= 0
    stock = stock + cfg.obs_pad

    # вылов: ПДУ НПЦ в штуках по возрастам 2..m1
    pdu_raw = np.nan_to_num(pdu.pieces[:, si, :][:, sel], nan=0.0)
    pdu_clean = (pdu_raw + 0.1) * cfg.pdu_scale

    # начальный запас (первый год), возрасты 2..m1
    meth = getattr(res, "method", "on_stock")          # способ годового запаса расчёта g (решение № 70)
    yearly_final = res.yearly[(MEAN, "with_ages", meth)][:, si, :][:, sel]
    yearly_net = res.yearly[(app_config.GEAR_NET, "with_ages", meth)][:, si, :][:, sel]
    yearly_seine = res.yearly[(app_config.GEAR_SEINE, "with_ages", meth)][:, si, :][:, sel]
    x0_src = cfg.likelihood_gears if cfg.likelihood_gears != "both" else cfg.x0_source
    src = {"seine": yearly_seine, "net": yearly_net}.get(x0_src, yearly_final)
    if cfg.likelihood_gears != "both":
        notes.append(f"начальный запас — по оценкам: {GEAR_TITLES[cfg.likelihood_gears]}")
    x0 = np.nan_to_num(src[0], nan=0.0)
    low = x0 < 1.0
    if low.any():
        notes.append("начальный запас меньше 1 шт. заменён на 1 шт. для возрастов: "
                     + ", ".join(f"{a - 1}–{a}" for a in np.arange(2, m1 + 1)[low]))
    x0 = np.maximum(x0, 1.0)

    area = np.array([props.lake_area_km2[y] for y in years], float)
    stocked = parse_stocking(cfg.stocking)
    stock_z = None                                      # зарыбление по годам (не путать с оценками stock)
    if stocked:
        stock_z = np.array([stocked.get(int(y), 0.0) for y in years], float)
        notes.append("зарыбление учтено (выпущено молоди, шт): "
                     + ", ".join(f"{int(y)} — {v:,.0f}".replace(",", " ") for y, v in zip(years, stock_z) if v > 0)
                     + f"; выживаемость выпущенной молоди φ ~ Beta({cfg.stock_surv_alpha:g}; {cfg.stock_surv_beta:g})")
    consts = Constants(m0=m0, m1=m1, m2=m2, n_years=len(years), eps=maturity(m0, m1),
                       K=_capacity(area, float(props.fry_density[species])), pdu=pdu_clean, x0=x0,
                       fec_bounds=tuple(props.fecundity[species]), stock=stock_z)
    npc_total = res.npc_stock[:, si] if res.npc_stock is not None else None
    return BayesInputs(species=species, mode="new", years=years, consts=consts, stock=stock, year_idx=year_idx,
                       gear=gear, zero=zero, zero_ref=zero_log_ref(stock, zero, cfg), dropped=dropped, yearly_final=yearly_final, yearly_net=yearly_net,
                       yearly_seine=yearly_seine, npc_total=npc_total, pdu_raw=pdu_raw, notes=notes)


# ---------------------------------------------------------------- режим "check"


def _old_module(script: str):
    """Загрузить скрипт вида из src исходного проекта (нужны PyMC и старые файлы data_stock)."""
    root = app_config.SOURCE_PROJECT_DIR
    src = root / "src"
    path = src / f"{script}.py"
    if not path.exists():
        raise FileNotFoundError(f"не найден скрипт {path}")
    for p in (str(src), str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    name = f"_old_{script}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_check_inputs(species: str, cfg: SpeciesConfig) -> BayesInputs:
    """Входные данные старого проекта (prepare_data_for_bayes из скрипта вида)."""
    mod = _old_module(cfg.script)
    d = mod.prepare_data_for_bayes(app_config.WATERBODY, species, True)
    m0, m1, m2 = int(d["m0"]), int(d["m1"]), int(d["m2"])

    pdu_da = d["pdu_yearly_fish"].transpose("Year", "age")
    years = [int(y) for y in pdu_da.Year.values]
    pdu_raw = np.nan_to_num(pdu_da.values, nan=0.0)
    pdu_clean = (pdu_raw + 0.1) * cfg.pdu_scale

    st = d["stock_by_date_fish"].transpose("Id", "age")
    stock = np.nan_to_num(st.values, nan=0.0)
    zero = stock.sum(axis=1) <= 0
    stock = stock + cfg.obs_pad
    dates = pd.to_datetime(st.Date.values, dayfirst=True)
    y_to_idx = {yr: i for i, yr in enumerate(years)}
    year_idx = np.array([y_to_idx[dt.year] for dt in dates])
    gear = np.asarray(st["Gear"].values, int)

    x0 = np.asarray(d["yearly_stock_0"].values, float)
    consts = Constants(m0=m0, m1=m1, m2=m2, n_years=len(years), eps=maturity(m0, m1),
                       K=np.asarray(d["square_years_np"], float) * 0.10 * d["density_norms"] * 10,
                       pdu=pdu_clean, x0=x0, fec_bounds=tuple(d["fecundity_bounds_dict"]))

    def yearly(key):
        da = d.get(key)
        return None if da is None else np.asarray(da.transpose("Year", "age").values, float)

    return BayesInputs(species=species, mode="check", years=years, consts=consts, stock=stock,
                       year_idx=year_idx, gear=gear, zero=zero, zero_ref=zero_log_ref(stock, zero, cfg), yearly_net=yearly("yearly_stock_net_fish"),
                       yearly_seine=yearly("yearly_stock_seine_fish"), pdu_raw=pdu_raw,
                       notes=[f"входные данные старого проекта: {cfg.script}.prepare_data_for_bayes"])


def truncate_inputs(inp: BayesInputs, year_max: int) -> BayesInputs:
    """Входные данные только за годы ≤ year_max (ретроспективная проверка): ловы, ПДУ, ёмкость."""
    from dataclasses import replace

    n = sum(1 for y in inp.years if y <= year_max)
    if n < 3:
        raise ValueError(f"до {year_max} года меньше трёх лет данных")
    c = inp.consts
    consts = replace(c, n_years=n, K=np.asarray(c.K)[:n], pdu=np.asarray(c.pdu)[:n],
                     stock=None if c.stock is None else np.asarray(c.stock)[:n])
    keep = inp.year_idx < n

    def cut(a):
        return None if a is None else np.asarray(a)[:n]

    return replace(inp, years=list(inp.years[:n]), consts=consts, stock=inp.stock[keep], year_idx=inp.year_idx[keep],
                   gear=inp.gear[keep], zero=inp.zero_mask[keep], yearly_final=cut(inp.yearly_final), yearly_net=cut(inp.yearly_net),
                   yearly_seine=cut(inp.yearly_seine), npc_total=cut(inp.npc_total), pdu_raw=cut(inp.pdu_raw),
                   notes=inp.notes + [f"только годы до {year_max} включительно"])


def build_inputs(species: str, cfg: SpeciesConfig, mode: str = "new", **kw) -> BayesInputs:
    if mode == "check":
        return build_check_inputs(species, cfg)
    return build_new_inputs(species, cfg, **kw)
