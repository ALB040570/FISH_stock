"""
Расчёт байесовской модели одного вида и сохранение результатов.

Режимы:
    "new"   — входные данные этапов 2–3, настройки со страницы (NUTS, PyMC; 15 мин – 2 ч на вид);
    "check" — входные данные и настройки старого скрипта (NUTS) — сверка со старыми .nc из data_stock;
    "prior" — только априорные распределения (numpy, секунды): что модель допускает до учёта данных;
    "legacy" — модель старой программы (config.LEGACY, пока только карась) на входных данных этапов 2–3.

Результаты (results/):
    zhaysan_bayes_{вид}[_check|_prior].npz — сводки и 500 выборок параметров (для страницы и прогноза);
    zhaysan_bayes_{вид}[_check].nc         — тот же набор переменных, что в старых .nc (+ интервалы 95 %);
    {вид}/diagnostics[_check|_prior]/      — R̂, ESS, E-BFMI, графики, таблица параметров, монотонность когорт
                                             (core.bayes.diagnostics).
Анализы чувствительности (core.bayes.analyses) вызывают run() с изменёнными настройками (cfg_changes),
обрезанными (year_max) или синтетическими (inputs) данными и пишут результаты в свою папку (results_dir, tag).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from .. import config as app_config
from .config import DEFAULTS, TOKENS, SpeciesConfig, get_config, token
from .dynamics import NumpyOps, simulate
from .inputs import BayesInputs, build_inputs

QUANTILES = (0.025, 0.25, 0.5, 0.75, 0.975)
N_KEEP = 500           # выборок для страницы и прогноза
MODES = ("new", "check", "prior", "legacy")
MODE_TITLES = {"new": "новый расчёт", "check": "сверка с исходным расчётом", "prior": "априорная проверка",
               "legacy": "старая модель на новых данных"}


# ---------------------------------------------------------------- файлы


def result_stem(species: str, mode: str, tag: str = "") -> str:
    suffix = {"new": "", "check": "_check", "prior": "_prior", "legacy": "_legacy"}[mode]
    return f"{app_config.WATERBODY}_bayes_{token(species)}{suffix}{tag}"


def result_path(species: str, mode: str, ext: str = "npz", results_dir: Path | None = None, tag: str = "") -> Path:
    return Path(results_dir or app_config.RESULTS_DIR) / f"{result_stem(species, mode, tag)}.{ext}"


def old_result_path(species: str) -> Path:
    return app_config.OLD_DATA_STOCK_DIR / f"{app_config.WATERBODY}_bayes_2g1p_with_ages_3d_{DEFAULTS[species].old_flag}.nc"


def mode_config(species: str, mode: str) -> SpeciesConfig:
    """Сверка — значения и параметры выборки старого скрипта (вариант (17) старого скрипта, без поправки
    уловистости сети, логнормальное правдоподобие с добавкой obs_pad); иначе — настройки со страницы."""
    if mode == "check":
        d = DEFAULTS[species]
        return replace(d, draws=d.script_draws, tune=d.script_tune, target_accept=d.script_target_accept,
                       catch_mode=d.script_catch_mode or d.catch_mode, gear_effect=False,
                       likelihood="pad")
    if mode == "legacy":
        from .config import LEGACY
        if species not in LEGACY:
            raise ValueError(f"режим legacy: для вида {species} настройки старой программы не заданы (есть: "
                             + ", ".join(LEGACY) + ")")
        return replace(DEFAULTS[species], **LEGACY[species])
    return get_config(species)


# ---------------------------------------------------------------- диагностика


def rhat(x: np.ndarray) -> np.ndarray:
    """Ранговый split-R̂ (Vehtari et al., 2021) по осям (цепь, выборка); NaN для постоянных величин."""
    from scipy.special import ndtri
    from scipy.stats import rankdata

    x = np.asarray(x, float)
    C, D = x.shape[:2]
    half = D // 2
    if half < 2:
        return np.full(x.shape[2:], np.nan)
    z = np.concatenate([x[:, :half], x[:, D - half:]], axis=0)          # (2C, half, …)

    def basic(v):
        m = v.shape[1]
        W = v.var(axis=1, ddof=1).mean(axis=0)
        B = m * v.mean(axis=1).var(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.sqrt(((m - 1) / m * W + B / m) / W)

    def ranknorm(v):
        flat = v.reshape(-1, *v.shape[2:])
        n = flat.shape[0]
        r = rankdata(flat, axis=0)
        return ndtri((r - 0.375) / (n + 0.25)).reshape(v.shape)

    bulk = basic(ranknorm(z))
    tail = basic(ranknorm(np.abs(z - np.median(z, axis=(0, 1)))))
    out = np.fmax(bulk, tail)
    const = np.ptp(x.reshape(-1, *x.shape[2:]), axis=0) == 0
    return np.where(const, np.nan, out)


def _q(flat: np.ndarray) -> np.ndarray:
    return np.quantile(flat, QUANTILES, axis=0)


# ---------------------------------------------------------------- априорные выборки (numpy)


def sample_prior_params(c, cfg: SpeciesConfig, n: int, rng) -> dict:
    """Выборка параметров из априорных распределений (без динамики); массивы (n, …)."""
    from scipy.stats import truncnorm

    Y, A = c.n_years, c.m1
    lo0, hi0, lo1, hi1 = c.fec_limits(cfg)
    a = (cfg.beta_lower - cfg.beta_mu) / cfg.beta_sigma
    b = (cfg.beta_upper - cfg.beta_mu) / cfg.beta_sigma
    p = {
        "density_alpha": rng.lognormal(0.0, cfg.density_sigma, (n, Y)),
        "s_base": rng.lognormal(cfg.s_base_mu, cfg.s_base_sigma, n),
        "s_juvenile_steep": rng.lognormal(cfg.s_juv_mu, cfg.s_juv_sigma, n),
        "s_aging_slow": rng.lognormal(cfg.s_age_mu, cfg.s_age_sigma, n),
        "s_year_fluct": rng.normal(0.0, cfg.s_year_sigma, (n, Y)),
        "beta_1d": truncnorm.rvs(a, b, loc=cfg.beta_mu, scale=cfg.beta_sigma, size=(n, Y), random_state=rng),
        "q_raw": rng.normal(0.0, cfg.q_sigma, (n, A)),
        "egg_survival_base": rng.beta(cfg.egg_alpha, cfg.egg_beta, n),
        "fec_at_m0": rng.uniform(lo0, hi0, n),
        "fec_at_m1": rng.uniform(lo1, hi1, n),
        "X_initial_older_raw": rng.lognormal(np.log(c.x0), cfg.x0_sigma, (n, A - 1)),
        "sigma_stock": np.abs(rng.normal(0.0, cfg.sigma_stock_sd, n)),
    }
    p["q_bias"] = np.exp(p["q_raw"])
    if cfg.gear_effect:
        p["log_q_net"] = rng.normal(0.0, cfg.q_net_sigma, n)
    if cfg.likelihood == "delta":
        p["zero_c"] = rng.normal(0.0, cfg.zero_c_sigma, (n, 2))
        p["zero_b"] = rng.normal(cfg.zero_b_mu, cfg.zero_b_sigma, n)
    if cfg.unused_q_year_dev:
        p["q_year_dev"] = rng.normal(0.0, 0.1, (n, Y, A))
    if cfg.noncentered:
        p["s_year_fluct_z"] = p["s_year_fluct"] / cfg.s_year_sigma
        p["beta_1d_z"] = (p["beta_1d"] - cfg.beta_mu) / cfg.beta_sigma
    return p


def sample_prior(inp: BayesInputs, cfg: SpeciesConfig, n: int = N_KEEP, seed: int | None = None) -> dict:
    """Выборка из априорных распределений и динамика по ним; массивы (1, n, …)."""
    rng = np.random.default_rng(cfg.seed if seed is None else seed)
    c = inp.consts
    p = sample_prior_params(c, cfg, n, rng)
    p.pop("q_year_dev", None)
    det = recompute(p, c, cfg)
    return {k: v[None] for k, v in {**p, **det}.items()}


def recompute(p: dict, c, cfg: SpeciesConfig) -> dict:
    """Динамика (numpy) для каждой выборки параметров p (массивы с первой осью — выборки)."""
    n = len(p["s_base"])
    keys = ("s", "pred_press_cube", "beta", "theta_dyn", "X_estimated", "egg_survival", "removal_ratio")
    out = {k: [] for k in keys}
    for i in range(n):
        one = {k: p[k][i] for k in ("density_alpha", "s_base", "s_juvenile_steep", "s_aging_slow", "s_year_fluct",
                                    "beta_1d", "egg_survival_base", "fec_at_m0", "fec_at_m1",
                                    "X_initial_older_raw")}
        r = simulate(NumpyOps, one, c, cfg)
        for k in keys:
            out[k].append(np.asarray(r[k], float))
    return {k: np.stack(v) for k, v in out.items()}


# ---------------------------------------------------------------- сводки


PARAM_ROWS = [
    # (имя, подпись, ось)
    ("s_base", "база смертности s", None),
    ("s_juvenile_steep", "крутизна смертности молоди", None),
    ("s_aging_slow", "крутизна смертности старших", None),
    ("egg_survival", "выживаемость икры", None),
    ("fec_at_m0", "плодовитость в m0, икринок", None),
    ("fec_at_m1", "плодовитость в m1, икринок", None),
    ("sigma_stock", "шум наблюдений σ", None),
    ("log_q_net", "ln q_net — поправка уловистости сети", None),
    ("zero_b", "b — наклон вероятности пустого лова по ln N", None),
    ("zero_c", "c — уровень вероятности пустого лова (сеть, невод)", "gear"),
    ("beta_1d", "β", "year"),
    ("density_alpha", "множитель ёмкости", "year"),
    ("s_year_fluct", "годовое отклонение s", "year"),
    ("q_bias", "поправка уловистости q", "age"),
]


def summarize(draws: dict, inp: BayesInputs, cfg: SpeciesConfig, with_rhat: bool = True) -> dict:
    """Сводки: квантили, R̂, структура гибели; массивы для .npz."""
    c = inp.consts
    X = draws["X_estimated"]                       # (C, D, Y, A)
    C, D = X.shape[:2]
    flat = lambda k: draws[k].reshape(C * D, *draws[k].shape[2:])  # noqa: E731
    Xf = flat("X_estimated")
    out = {
        "quantiles": np.array(QUANTILES),
        "X_q": _q(Xf),                                              # (5, Y, A)
        "total_obs_q": _q(Xf[:, :, 1:].sum(axis=2)),                # (5, Y) возрасты 2..m1
        "total_all_q": _q(Xf.sum(axis=2)),                          # (5, Y) с сеголетками
        "s_q": _q(flat("s")),
        "pred_q": _q(flat("pred_press_cube")),
        "beta1d_q": _q(flat("beta_1d")),
        "q_bias_q": _q(flat("q_bias")),
        "theta_q": _q(flat("theta_dyn")),
        "density_alpha_q": _q(flat("density_alpha")),
    }
    if "removal_ratio" in draws:
        # доля выборок, где запрошенное изъятие больше removal_cap · выживших (ограничение действует)
        from .diagnostics import cap_active_fraction
        out["cap_active_frac"] = cap_active_fraction(draws["removal_ratio"], cfg.removal_cap)
    if "log_q_net" in draws:
        out["log_q_net_q"] = _q(flat("log_q_net"))
    X_med = out["X_q"][2]
    s_med = out["s_q"][2]
    pred_med = out["pred_q"][2]
    beta_med = np.median(flat("beta"), axis=0)
    out["dead_natural_pcs"] = s_med * X_med
    out["dead_predators_pcs"] = pred_med * X_med
    out["dead_brac_pcs"] = np.maximum((beta_med[:, 1:] - 1.0) * c.pdu, 0.0)
    out["pdu_pcs"] = c.pdu

    rows = []
    for name, label, axis in PARAM_ROWS:
        if name not in draws:
            continue
        arr = draws[name]
        f = arr.reshape(C * D, *arr.shape[2:])
        qs = _q(f)
        rh = rhat(arr) if (with_rhat and C * D >= 8) else np.full(arr.shape[2:], np.nan)
        if axis is None:
            rows.append({"name": name, "label": label, "index": None, "q": qs.tolist(), "rhat": _f(rh)})
        else:
            labels = (inp.years if axis == "year" else ["сеть", "невод"] if axis == "gear"
                      else [int(a) for a in inp.model_ages])
            for i, lab in enumerate(labels):
                rows.append({"name": name, "label": label, "index": lab, "q": qs[:, i].tolist(), "rhat": _f(rh[i])})
    out["_param_rows"] = rows

    if with_rhat and C * D >= 8:
        out["rhat_X"] = rhat(X)
        out["rhat_beta"] = rhat(draws["beta"])
        out["rhat_q_bias"] = rhat(draws["q_bias"])
    return out


def _f(v):
    v = float(v)
    return None if not np.isfinite(v) else v


def thin(draws: dict, n: int = N_KEEP, seed: int = 0) -> dict:
    """n выборок из всех цепей (равномерно по номерам, без повторов)."""
    any_ = next(iter(draws.values()))
    total = any_.shape[0] * any_.shape[1]
    idx = np.linspace(0, total - 1, min(n, total)).round().astype(int)
    return {k: v.reshape(total, *v.shape[2:])[idx] for k, v in draws.items()}


# ---------------------------------------------------------------- сохранение


def save_npz(path: Path, summary: dict, kept: dict, inp: BayesInputs, cfg: SpeciesConfig, meta: dict) -> None:
    c = inp.consts
    arrays = {k: v for k, v in summary.items() if not k.startswith("_")}
    arrays.update({f"draw_{k}": v for k, v in kept.items()})
    nan = np.full((c.n_years, c.m1 - 1), np.nan)
    arrays.update({
        "years": np.array(inp.years), "model_ages": inp.model_ages, "obs_ages": inp.obs_ages,
        "eps": c.eps, "K": c.K, "pdu_clean": c.pdu, "x0": c.x0,
        "pdu_raw": inp.pdu_raw if inp.pdu_raw is not None else nan,
        "yearly_final": inp.yearly_final if inp.yearly_final is not None else nan,
        "yearly_net": inp.yearly_net if inp.yearly_net is not None else nan,
        "yearly_seine": inp.yearly_seine if inp.yearly_seine is not None else nan,
        "npc_total": inp.npc_total if inp.npc_total is not None else np.full(c.n_years, np.nan),
        "obs_year_idx": inp.year_idx, "obs_gear": inp.gear,
        "obs_stock_mean": _obs_mean(inp, cfg.obs_pad),
    })
    meta = {**meta, "species": inp.species, "m0": c.m0, "m1": c.m1, "m2": c.m2,
            "fec_bounds": [float(v) for v in c.fec_bounds], "config": asdict(cfg),
            "notes": inp.notes, "n_obs": int(len(inp.stock)), "dropped": inp.dropped,
            "param_rows": summary.get("_param_rows", [])}
    arrays["meta"] = np.array(json.dumps(meta, ensure_ascii=False, default=_json_default))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)


def _obs_mean(inp: BayesInputs, pad: float = 0.1) -> np.ndarray:
    """(2, годы, m1 − 1) — среднее оценок по ловам (− obs_pad) по орудиям: как видит их модель."""
    Y = inp.consts.n_years
    out = np.full((2, Y, inp.stock.shape[1]), np.nan)
    for g in (0, 1):
        for t in range(Y):
            sel = (inp.gear == g) & (inp.year_idx == t)
            if sel.any():
                out[g, t] = inp.stock[sel].mean(axis=0) - pad
    return out


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def load_npz(path: Path) -> tuple[dict, dict] | None:
    if not Path(path).exists():
        return None
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    meta = json.loads(str(arrays.pop("meta")))
    return arrays, meta


def save_nc(path: Path, summary: dict, inp: BayesInputs, meta: dict) -> str | None:
    """Файл .nc в формате старого calc_stock_twogear (+ интервалы 95 %). Нужны xarray и netCDF4."""
    try:
        import xarray as xr
    except ImportError:
        return "не установлен xarray"
    c = inp.consts
    years, ages, obs_ages = np.array(inp.years), inp.model_ages, inp.obs_ages
    X_q, s_q, pred_q = summary["X_q"], summary["s_q"], summary["pred_q"]
    data = {
        "X_median": (["Year", "age"], X_q[2]), "X_q25": (["Year", "age"], X_q[1]),
        "X_q75": (["Year", "age"], X_q[3]), "X_q025": (["Year", "age"], X_q[0]),
        "X_q975": (["Year", "age"], X_q[4]),
        "s_median": (["Year", "age"], s_q[2]),
        "pred_press_median": (["Year", "age"], pred_q[2]),
        "q_bias_median": (["age"], summary["q_bias_q"][2]), "q_bias_q25": (["age"], summary["q_bias_q"][1]),
        "q_bias_q75": (["age"], summary["q_bias_q"][3]),
        "beta_1d_median": (["Year"], summary["beta1d_q"][2]), "beta_1d_q25": (["Year"], summary["beta1d_q"][1]),
        "beta_1d_q75": (["Year"], summary["beta1d_q"][3]),
        "dead_natural_pcs": (["Year", "age"], summary["dead_natural_pcs"]),
        "dead_predators_pcs": (["Year", "age"], summary["dead_predators_pcs"]),
        "dead_brac_pcs": (["Year", "age_observed"], summary["dead_brac_pcs"]),
        "pdu_pcs": (["Year", "age_observed"], summary["pdu_pcs"]),
    }
    b = summary["beta1d_q"]
    for key, k in (("beta_median", 2), ("beta_q25", 1), ("beta_q75", 3)):
        data[key] = (["Year", "age"], np.repeat(b[k][:, None], c.m1, axis=1))
    for key in ("rhat_X", "rhat_beta", "rhat_q_bias"):
        if key in summary:
            data[key] = ((["age"] if key == "rhat_q_bias" else ["Year", "age"]), summary[key])
    attrs = {"waterbody": app_config.WATERBODY,
             "model_type": f"Two-Gear Bayesian Cohort Assessment fish = {inp.species}",
             "description": "FishStock, этап 4: " + MODE_TITLES[meta["mode"]],
             "total_divergences": int(meta.get("divergences", 0) or 0),
             "config": json.dumps(meta.get("config_short", {}), ensure_ascii=False)}
    ds = xr.Dataset({k: (dims, np.asarray(v, float)) for k, (dims, v) in data.items()},
                    coords={"Year": years, "age": ages, "age_observed": obs_ages}, attrs=attrs)
    try:
        ds.to_netcdf(path, engine="netcdf4")
    except Exception as e:  # noqa: BLE001
        return str(e)
    return None


def compare_with_old(summary: dict, species: str, years: list[int]) -> dict | None:
    """Сравнение медианы численности (возрасты 2..m1) со старым .nc; None, если файла или xarray нет."""
    path = old_result_path(species)
    try:
        import xarray as xr
    except ImportError:
        return None
    if not path.exists():
        return None
    with xr.open_dataset(path) as ds:
        old = ds["X_median"].load()
    old_years = [int(y) for y in old["Year"].values]
    old_tot = old.sel(age=slice(2, None)).sum("age").values
    new_tot = summary["X_q"][2][:, 1:].sum(axis=1)
    rows = []
    for i, y in enumerate(years):
        if y in old_years:
            o = float(old_tot[old_years.index(y)])
            n = float(new_tot[i])
            rows.append({"year": y, "old": o, "new": n, "rel": (n - o) / o if o else None})
    rel = [abs(r["rel"]) for r in rows if r["rel"] is not None]
    return {"file": path.name, "rows": rows, "max_rel": max(rel) if rel else None}


# ---------------------------------------------------------------- запуск


def run(species: str, mode: str = "new", progress=None, log=print, results_dir: Path | None = None,
        stage23=None, cfg_changes: dict | None = None, year_max: int | None = None,
        inputs: BayesInputs | None = None, tag: str = "", plots: bool = True) -> dict:
    """Рассчитать модель вида и сохранить результаты. progress(dict) — ход выборки для страницы.

    cfg_changes — изменения настроек (анализы чувствительности, короткие цепи в тестах);
    year_max — только годы до year_max включительно (ретроспективная проверка);
    inputs — готовые входные данные (проверка восстановления параметров по синтетическим данным);
    tag — добавка к имени файлов результатов и папки диагностики; plots — строить ли графики диагностики.
    """
    if mode not in MODES:
        raise ValueError(f"режим {mode}: ожидается {MODES}")
    t0 = time.time()
    cfg = mode_config(species, mode)
    if cfg_changes:
        cfg = replace(cfg, **cfg_changes)
    report = progress or (lambda d: None)
    rdir = Path(results_dir or app_config.RESULTS_DIR)

    report({"phase": "inputs"})
    log(f"[{species}] {MODE_TITLES[mode]}{tag}: подготовка входных данных")
    if inputs is not None:
        inp = inputs
    else:
        kw = {}
        if mode != "check" and stage23 is not None:
            kw = dict(zip(("res", "pdu", "props"), stage23))
        inp = build_inputs(species, cfg, "check" if mode == "check" else "new", **kw)
    if year_max is not None:
        from .inputs import truncate_inputs
        inp = truncate_inputs(inp, year_max)
    for n in inp.notes:
        log(f"  {n}")
    c = inp.consts
    log(f"  годы {inp.years[0]}–{inp.years[-1]}, возрасты 1..{c.m1}, ловов в правдоподобии: {len(inp.stock)}")

    meta = {"mode": mode, "mode_title": MODE_TITLES[mode], "started": datetime.now().isoformat(timespec="seconds"),
            "tag": tag, "year_max": year_max}
    from .diagnostics import diag_dir, monotonicity, run_diagnostics

    ddir = diag_dir(token(species), rdir, mode, tag)
    diag = None
    if mode == "prior":
        draws = sample_prior(inp, cfg)
        stats = {"divergences": None}
        numpy_check = None
    else:
        from .model import build_model, extract_draws, free_names, sample

        report({"phase": "compile"})
        log(f"  сборка модели PyMC; выборка: {cfg.draws} выборок, {cfg.tune} шагов настройки, "
            f"target_accept {cfg.target_accept}, seed {cfg.seed}")
        model = build_model(inp, cfg)
        cb = _Callback(cfg, report, log)
        idata = sample(model, cfg, callback=cb)
        report({"phase": "save"})
        draws, stats = extract_draws(idata)
        log(f"  выборка закончена за {_hms(time.time() - t0)}; расходимостей: {stats.get('divergences')}")
        numpy_check = _numpy_check(draws, c, cfg)
        log(f"  сверка уравнений numpy и PyMC: наибольшее относительное отличие X = {numpy_check:.2e}")
        report({"phase": "diagnostics"})
        prior = sample_prior_params(c, cfg, 4000, np.random.default_rng(cfg.seed + 1))
        diag = run_diagnostics(idata, free_names(model), draws["X_estimated"], draws.get("removal_ratio"), prior,
                               inp, cfg, ddir, plots=plots, log=log)
        log(f"  диагностика: R̂ max {diag['rhat_max_params']}, ESS bulk min {diag['ess_bulk_min_params']}, "
            f"ESS tail min {diag['ess_tail_min_params']}, E-BFMI {diag['ebfmi_by_chain']}; файлы: {ddir}")

    mono = diag["monotonicity"] if diag else monotonicity(draws["X_estimated"])
    if not mono["ok"]:
        log(f"  ВНИМАНИЕ: нарушена монотонность когорт X_j(t+1) ≤ X_(j−1)(t): {mono['violations']} "
            f"из {mono['checked']} (наибольшее превышение {mono.get('worst_rel_excess', 0):.2e})")

    summary = summarize(draws, inp, cfg, with_rhat=(mode != "prior"))
    kept = thin({k: v for k, v in draws.items() if k not in ("s", "pred_press_cube", "beta", "removal_ratio")})
    rh = summary.get("rhat_X")
    meta.update({
        "finished": datetime.now().isoformat(timespec="seconds"), "seconds": round(time.time() - t0, 1),
        "chains": int(draws["X_estimated"].shape[0]), "draws_per_chain": int(draws["X_estimated"].shape[1]),
        "tune": cfg.tune if mode != "prior" else 0, **stats,
        "rhat_X_max": None if rh is None else _f(np.nanmax(rh)),
        "numpy_check": numpy_check,
        "monotonic_violations": mono["violations"], "monotonic_ok": mono["ok"],
        "cap_active_cells": int((summary["cap_active_frac"] > 0.5).sum()) if "cap_active_frac" in summary else None,
        "diagnostics": None if diag is None else {k: v for k, v in diag.items()
                                                   if k not in ("monotonicity", "plots", "worst_rhat")},
        "diagnostics_dir": None if diag is None else str(ddir),
        "config_short": {k: v for k, v in asdict(cfg).items() if not k.startswith("script") and k != "old_flag"},
    })
    if mode == "check":
        cmp_ = compare_with_old(summary, species, inp.years)
        meta["check_vs_old"] = cmp_
        if cmp_:
            log(f"  сравнение со старым {cmp_['file']}: наибольшее отличие суммарной численности "
                f"{100 * cmp_['max_rel']:.1f} %")

    npz = result_path(species, mode, "npz", rdir, tag)
    save_npz(npz, summary, kept, inp, cfg, meta)
    log(f"  сохранено: {npz}")
    if mode != "prior":
        err = save_nc(result_path(species, mode, "nc", rdir, tag), summary, inp, meta)
        log("  .nc: " + (f"не записан — {err}" if err else "записан"))
    report({"phase": "done"})
    return meta


def _numpy_check(draws: dict, c, cfg) -> float:
    """Пересчитать X по выборкам параметров на numpy и сравнить с X из PyMC."""
    kept = thin(draws, 50)
    X_np = recompute(kept, c, cfg)["X_estimated"]
    X_pm = kept["X_estimated"]
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(X_np - X_pm) / np.maximum(np.abs(X_pm), 1.0)
    return float(np.nanmax(rel))


def _hms(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600} ч {sec % 3600 // 60:02d} мин" if sec >= 3600 else f"{sec // 60} мин {sec % 60:02d} с"


class _Callback:
    """Ход выборки: число шагов по цепям, фаза, расходимости. Пишет не чаще раза в секунду."""

    def __init__(self, cfg: SpeciesConfig, report, log):
        self.total = cfg.tune + cfg.draws
        self.report, self.log = report, log
        self.done: dict[int, int] = {}
        self.div = 0
        self.last = 0.0
        self.t0 = time.time()
        self.first = None

    def __call__(self, trace=None, draw=None, **_):
        now = time.time()
        if self.first is None:
            self.first = now
            self.log(f"  модель собрана за {_hms(now - self.t0)}, идёт выборка")
        chain = int(getattr(draw, "chain", 0) or 0)
        idx = getattr(draw, "draw_idx", None)
        self.done[chain] = max(self.done.get(chain, 0) + 1, (idx + 1) if isinstance(idx, (int, np.integer)) else 0)
        tuning = bool(getattr(draw, "tuning", False))
        if not tuning:
            try:
                st = draw.stats[0] if isinstance(draw.stats, (list, tuple)) else draw.stats
                self.div += int(bool(st.get("diverging", False)))
            except Exception:  # noqa: BLE001
                pass
        if now - self.last >= 1.0 or getattr(draw, "is_last", False):
            self.last = now
            self.report({"phase": "tune" if tuning else "draws", "total": self.total,
                         "chains": {str(k): v for k, v in sorted(self.done.items())},
                         "divergences": self.div, "sampling_seconds": round(now - self.first, 1)})
