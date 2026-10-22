"""
Диагностика байесовской модели одного вида (ответ рецензентам).

После выборки NUTS (ArviZ, если установлен; иначе — собственный R̂ и NaN для ESS):
    R̂ (ранговый split-R̂), ESS bulk и tail по каждому свободному параметру и по X_estimated;
    расходимости; E-BFMI по цепям;
    графики трасс и «априорное против апостериорного» (PNG, matplotlib);
    таблица параметров: число свободных параметров по группам, число наблюдений,
    отношение апостериорного SD к априорному по каждому параметру;
    проверка монотонности когорт: X_j(t+1) ≤ X_{j−1}(t)·(1 + 10⁻⁹), j ≥ 2, по всем выборкам;
    где действует ограничение изъятия (запрошенное β·A > removal_cap · выживших).

Файлы: results/<вид>/diagnostics/ (вид — латинское имя: lesh, sudak, …):
    diagnostics.json, params.csv, param_counts.csv, cap_active.csv, trace_*.png, prior_posterior_*.png.
Сводка по всем видам — collect_summary() → results/bayes_diagnostics_summary.csv.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MONO_REL_TOL = 1e-9

# группы параметров для таблицы B5
PARAM_GROUPS = {
    "s_base": "естественная смертность", "s_juvenile_steep": "естественная смертность",
    "s_aging_slow": "естественная смертность", "s_year_fluct": "естественная смертность",
    "s_year_fluct_z": "естественная смертность",
    "beta_1d": "изъятие β", "beta_1d_z": "изъятие β",
    "density_alpha": "пополнение", "egg_survival_base": "пополнение", "fec_at_m0": "пополнение",
    "fec_at_m1": "пополнение",
    "q_raw": "уловистость", "log_q_net": "уловистость", "q_year_dev": "уловистость (не используется)",
    "X_initial_older_raw": "начальный запас",
    "sigma_stock": "шум наблюдений",
    "zero_c": "пустые ловы", "zero_b": "пустые ловы",
}

# цвета цепей (категориальная палитра, фиксированный порядок)
CHAIN_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300")
PRIOR_COLOR = "#9a9a94"
POST_COLOR = "#2a78d6"


def diag_dir(species_token: str, results_dir: Path, mode: str = "new", tag: str = "") -> Path:
    """Папка диагностики: results/<вид>/diagnostics[_check|_prior]; у проверок (tag задан) results_dir — уже
    папка вида и проверки (results/<вид>/retro и т. п.): <results_dir>/diagnostics[_режим]<тег>."""
    suffix = "" if mode == "new" else f"_{mode}"
    if tag:
        return Path(results_dir) / f"diagnostics{suffix}{tag}"
    return Path(results_dir) / species_token / f"diagnostics{suffix}"


# ---------------------------------------------------------------- проверки без ArviZ


def monotonicity(X: np.ndarray, rel_tol: float = MONO_REL_TOL) -> dict:
    """X (…, годы, возрасты): нарушения X_j(t+1) ≤ X_{j−1}(t)·(1 + tol) вдоль диагоналей когорт, j ≥ 2."""
    X = np.asarray(X, float)
    nxt, prev = X[..., 1:, 1:], X[..., :-1, :-1]
    bad = nxt > prev * (1.0 + rel_tol)
    n_bad = int(bad.sum())
    out = {"violations": n_bad, "checked": int(bad.size), "rel_tol": rel_tol, "ok": n_bad == 0}
    if n_bad:
        cells = bad.reshape(-1, *bad.shape[-2:]).sum(axis=0)          # (годы − 1, возрасты − 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            excess = np.where(bad, nxt / np.where(prev > 0, prev, np.nan) - 1.0, np.nan)
        out["worst_rel_excess"] = float(np.nanmax(excess))
        out["cells"] = [{"t_index": int(t + 1), "age": int(a + 2), "draws": int(cells[t, a])}
                        for t, a in zip(*np.nonzero(cells))]
    return out


def cap_active_fraction(ratio: np.ndarray, cap: float) -> np.ndarray:
    """Доля выборок, в которых запрошенное изъятие больше cap · выживших: (годы, возрасты)."""
    r = np.asarray(ratio, float)
    return (r > cap).reshape(-1, *r.shape[-2:]).mean(axis=0)


def ebfmi(energy: np.ndarray) -> np.ndarray:
    """E-BFMI по цепям: mean((ΔE)²) / var(E) (формула ArviZ)."""
    e = np.asarray(energy, float)
    try:
        import arviz as az
        return np.atleast_1d(np.asarray(az.bfmi(e), float))
    except Exception:  # noqa: BLE001 — без ArviZ или другая версия API
        return np.square(np.diff(e, axis=1)).mean(axis=1) / np.var(e, axis=1)


# ---------------------------------------------------------------- R̂ и ESS (ArviZ)


def _az_scalar(fn, arr2d, **kw) -> float:
    v = np.asarray(fn(arr2d, **kw))
    if v.dtype == object or v.size != 1:
        v = np.asarray([float(x) for x in np.ravel(v)])
    return float(np.ravel(v)[0])


def chain_stats(arr: np.ndarray) -> dict:
    """arr (цепь, выборка, …) → R̂, ESS bulk, ESS tail по каждому элементу (массивы формы …)."""
    from .run import rhat as rhat_np

    arr = np.asarray(arr, float)
    C, D = arr.shape[:2]
    shape = arr.shape[2:]
    flat = arr.reshape(C, D, -1)
    n = flat.shape[2]
    rh, eb, et = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    try:
        import arviz as az
    except ImportError:
        az = None
    for i in range(n):
        x = flat[:, :, i]
        if np.ptp(x) == 0 or not np.all(np.isfinite(x)):
            continue
        if az is not None:
            try:
                rh[i] = _az_scalar(az.rhat, x, method="rank")
            except Exception:  # noqa: BLE001
                pass
            try:
                eb[i] = _az_scalar(az.ess, x, method="bulk")
            except Exception:  # noqa: BLE001
                pass
            try:
                et[i] = _az_scalar(az.ess, x, method="tail")
            except TypeError:  # ArviZ ≥ 1: нужен prob
                try:
                    et[i] = _az_scalar(az.ess, x, method="tail", prob=(0.05, 0.95))
                except Exception:  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                pass
        if not np.isfinite(rh[i]) and C * D >= 8:
            rh[i] = float(rhat_np(x[:, :, None])[0])
    return {"rhat": rh.reshape(shape), "ess_bulk": eb.reshape(shape), "ess_tail": et.reshape(shape)}


def _index_labels(name: str, shape: tuple, years: list, ages, obs_ages) -> list:
    """Подписи элементов параметра: год, возраст или (год, возраст)."""
    if not shape:
        return [None]
    n = int(np.prod(shape))
    if name == "zero_c":
        return ["сеть", "невод"][:n]
    if len(shape) == 1:
        if shape[0] == len(years) and name not in ("q_raw", "X_initial_older_raw"):
            return list(years)
        if name == "X_initial_older_raw":
            return [int(a) for a in obs_ages]
        if shape[0] == len(ages):
            return [int(a) for a in ages]
        return list(range(n))
    if len(shape) == 2 and shape == (len(years), len(ages)):
        return [f"{y}/{int(a)}" for y in years for a in ages]
    return list(range(n))


def param_rows(post: dict, prior: dict, years: list, ages, obs_ages) -> list[dict]:
    """По каждому элементу свободного параметра: среднее, SD, априорное SD, отношение SD, R̂, ESS."""
    rows = []
    for name, arr in post.items():
        arr = np.asarray(arr, float)
        st = chain_stats(arr)
        flat = arr.reshape(arr.shape[0] * arr.shape[1], -1)
        mean, sd = flat.mean(axis=0), flat.std(axis=0, ddof=1)
        pr = prior.get(name)
        psd = (np.asarray(pr, float).reshape(len(pr), -1).std(axis=0, ddof=1) if pr is not None
               else np.full(flat.shape[1], np.nan))
        if psd.size == 1 and flat.shape[1] > 1:
            psd = np.repeat(psd, flat.shape[1])
        labels = _index_labels(name, arr.shape[2:], years, ages, obs_ages)
        for i, lab in enumerate(labels):
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = sd[i] / psd[i] if psd[i] > 0 else np.nan
            rows.append({"name": name, "group": PARAM_GROUPS.get(name, "другое"), "index": lab,
                         "post_mean": float(mean[i]), "post_sd": float(sd[i]), "prior_sd": float(psd[i]),
                         "sd_ratio": float(ratio), "rhat": float(np.ravel(st["rhat"])[i]),
                         "ess_bulk": float(np.ravel(st["ess_bulk"])[i]),
                         "ess_tail": float(np.ravel(st["ess_tail"])[i])})
    return rows


def n_observations(inp, cfg) -> tuple[int, int]:
    """(ловов, наблюдений): при дельта-логнормальном правдоподобии — ненулевые ловы × возрасты + все ловы
    (событие «лов пуст / не пуст»); иначе ловы × возрасты."""
    n_ages = inp.stock.shape[1] - (cfg.likelihood_from - 2)
    n = int(len(inp.stock))
    if cfg.likelihood == "delta":
        return n, int((~inp.zero_mask).sum()) * n_ages + n
    return n, n * n_ages


def param_counts(rows: list[dict], n_hauls: int, n_obs_values: int, n_zero: int | None = None) -> list[dict]:
    """Число свободных параметров по группам и число наблюдений."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    out = [{"group": g, "n_params": n} for g, n in counts.items()]
    out.append({"group": "всего параметров", "n_params": sum(counts.values())})
    out.append({"group": "ловов в правдоподобии", "n_params": n_hauls})
    if n_zero is not None:
        out.append({"group": "из них пустых (без рыбы вида)", "n_params": n_zero})
    out.append({"group": "наблюдений (ловы × возрасты)" if n_zero is None
                else "наблюдений (ненулевые ловы × возрасты + ловы)", "n_params": n_obs_values})
    return out


# ---------------------------------------------------------------- графики


def _elements(arr: np.ndarray, k: int = 6) -> list[int]:
    n = int(np.prod(arr.shape[2:])) if arr.ndim > 2 else 1
    return sorted(set(np.linspace(0, n - 1, min(k, n)).round().astype(int).tolist()))


def plot_traces(post: dict, out_dir: Path, labels: dict | None = None) -> list[str]:
    """Трассы по цепям и плотности: один PNG на параметр (до 6 элементов векторных параметров)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = []
    for name, arr in post.items():
        arr = np.asarray(arr, float)
        C = arr.shape[0]
        flat = arr.reshape(C, arr.shape[1], -1)
        idx = _elements(arr)
        fig, axes = plt.subplots(len(idx), 2, figsize=(10, 1.8 * len(idx) + 0.6), squeeze=False,
                                 gridspec_kw={"width_ratios": [3, 1]})
        for row, i in enumerate(idx):
            lab = (labels or {}).get(name, [None] * flat.shape[2])
            title = name if lab[i] is None else f"{name} [{lab[i]}]"
            for ch in range(C):
                col = CHAIN_COLORS[ch % len(CHAIN_COLORS)]
                axes[row, 0].plot(flat[ch, :, i], lw=0.6, color=col, label=f"цепь {ch + 1}")
                axes[row, 1].hist(flat[ch, :, i], bins=30, histtype="step", color=col, lw=1.2)
            axes[row, 0].set_title(title, fontsize=9, loc="left")
            for ax in axes[row]:
                ax.ticklabel_format(useOffset=False, style="plain", axis="both")
                ax.tick_params(labelsize=7)
                ax.spines[["top", "right"]].set_visible(False)
        axes[0, 0].legend(fontsize=7, ncol=min(C, 6), frameon=False, loc="upper right")
        axes[-1, 0].set_xlabel("номер выборки", fontsize=8)
        fig.tight_layout()
        path = Path(out_dir) / f"trace_{name}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        files.append(path.name)
    return files


def plot_prior_posterior(post: dict, prior: dict, out_dir: Path, labels: dict | None = None) -> list[str]:
    """Априорное (серое) и апостериорное (синее) распределения: один PNG на параметр."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = []
    for name, arr in post.items():
        if name not in prior:
            continue
        arr = np.asarray(arr, float)
        flat = arr.reshape(arr.shape[0] * arr.shape[1], -1)
        pr = np.asarray(prior[name], float).reshape(len(prior[name]), -1)
        idx = _elements(arr)
        ncol = min(3, len(idx))
        nrow = int(np.ceil(len(idx) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.4 * nrow + 0.4), squeeze=False)
        for k, i in enumerate(idx):
            ax = axes[k // ncol, k % ncol]
            p_i = pr[:, min(i, pr.shape[1] - 1)]
            lo = np.nanmin([np.quantile(p_i, 0.005), np.quantile(flat[:, i], 0.005)])
            hi = np.nanmax([np.quantile(p_i, 0.995), np.quantile(flat[:, i], 0.995)])
            bins = np.linspace(lo, hi, 40) if hi > lo else 20
            ax.hist(p_i, bins=bins, density=True, color=PRIOR_COLOR, alpha=0.55, label="априорное")
            ax.hist(flat[:, i], bins=bins, density=True, histtype="step", color=POST_COLOR, lw=2,
                    label="апостериорное")
            lab = (labels or {}).get(name, [None] * flat.shape[1])
            ax.set_title(name if lab[i] is None else f"{name} [{lab[i]}]", fontsize=9, loc="left")
            ax.tick_params(labelsize=7)
            ax.spines[["top", "right"]].set_visible(False)
        for k in range(len(idx), nrow * ncol):
            axes[k // ncol, k % ncol].axis("off")
        axes[0, 0].legend(fontsize=7, frameon=False)
        fig.tight_layout()
        path = Path(out_dir) / f"prior_posterior_{name}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        files.append(path.name)
    return files


# ---------------------------------------------------------------- сборка


def write_csv(path: Path, rows: list[dict]) -> None:
    import pandas as pd

    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def run_diagnostics(idata, free: list[str], X: np.ndarray, ratio: np.ndarray | None, prior: dict,
                    inp, cfg, out_dir: Path, plots: bool = True, log=print) -> dict:
    """Полная диагностика после NUTS; пишет файлы в out_dir и возвращает сводку для meta."""
    from .model import _group

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    post_ds = _group(idata, "posterior")
    post = {k: np.asarray(post_ds[k].values, float) for k in free if k in post_ds.data_vars}
    years, ages, obs_ages = list(inp.years), inp.model_ages, inp.obs_ages

    rows = param_rows(post, prior, years, ages, obs_ages)
    n_hauls, n_obs = n_observations(inp, cfg)
    n_zero = int(inp.zero_mask.sum()) if cfg.likelihood == "delta" else None
    counts = param_counts(rows, n_hauls, n_obs, n_zero)
    xs = chain_stats(X)

    div_by_chain, bfmi = [], []
    try:
        ss = _group(idata, "sample_stats")
        div_by_chain = np.asarray(ss["diverging"].values, bool).sum(axis=1).astype(int).tolist()
        if "energy" in ss.data_vars:
            bfmi = [float(v) for v in ebfmi(np.asarray(ss["energy"].values, float))]
    except Exception as e:  # noqa: BLE001
        log(f"  диагностика: нет статистики выборки ({e})")

    def _nanf(fn, vals):
        vals = np.asarray(vals, float)
        vals = vals[np.isfinite(vals)]
        return float(fn(vals)) if vals.size else None

    mono = monotonicity(X)
    summ = {
        "rhat_max_params": _nanf(np.max, [r["rhat"] for r in rows]),
        "ess_bulk_min_params": _nanf(np.min, [r["ess_bulk"] for r in rows]),
        "ess_tail_min_params": _nanf(np.min, [r["ess_tail"] for r in rows]),
        "rhat_max_X": _nanf(np.max, xs["rhat"]),
        "ess_bulk_min_X": _nanf(np.min, xs["ess_bulk"]),
        "ess_tail_min_X": _nanf(np.min, xs["ess_tail"]),
        "divergences": int(sum(div_by_chain)), "divergences_by_chain": div_by_chain,
        "ebfmi_by_chain": bfmi, "ebfmi_min": min(bfmi) if bfmi else None,
        "n_free_params": len(rows), "n_hauls": n_hauls, "n_obs_values": n_obs,
        "likelihood": cfg.likelihood, "n_zero_hauls": int(inp.zero_mask.sum()),
        "monotonicity": mono,
    }
    worst = sorted(rows, key=lambda r: -(r["rhat"] if np.isfinite(r["rhat"]) else 0))[:10]
    summ["worst_rhat"] = [{k: r[k] for k in ("name", "index", "rhat", "ess_bulk", "ess_tail")} for r in worst]
    if ratio is not None:
        frac = cap_active_fraction(ratio, cfg.removal_cap)
        summ["cap_active_cells"] = int((frac > 0.5).sum())
        summ["cap_active_any"] = int((frac > 0).sum())
        write_csv(out_dir / "cap_active.csv",
                  [{"year": y, **{f"age_{int(a)}": float(frac[t, j]) for j, a in enumerate(ages)}}
                   for t, y in enumerate(years)])

    write_csv(out_dir / "params.csv", rows)
    write_csv(out_dir / "param_counts.csv", counts)
    if plots:
        labels = {k: _index_labels(k, v.shape[2:], years, ages, obs_ages) for k, v in post.items()}
        try:
            summ["plots"] = plot_traces(post, out_dir, labels) + plot_prior_posterior(post, prior, out_dir, labels)
        except Exception as e:  # noqa: BLE001 — графики не обязательны
            summ["plots_error"] = f"{type(e).__name__}: {e}"
            log(f"  графики диагностики не построены: {e}")
    (out_dir / "diagnostics.json").write_text(
        json.dumps({"species": inp.species, **summ}, ensure_ascii=False, indent=1, default=_json_default),
        encoding="utf-8")
    return summ


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


# ---------------------------------------------------------------- сводка по видам (B2)


SUMMARY_COLUMNS = ("species", "token", "finished", "chains", "draws_per_chain", "divergences", "ebfmi_min",
                   "rhat_max_params", "rhat_max_X", "ess_bulk_min_params", "ess_tail_min_params", "ess_bulk_min_X",
                   "ess_tail_min_X", "monotonic_violations", "cap_active_cells", "n_free_params", "n_hauls",
                   "n_obs_values", "likelihood", "n_zero_hauls")


def collect_summary(results_dir: Path | None = None, out: Path | None = None) -> Path:
    """Сводная таблица диагностики по всем видам → results/bayes_diagnostics_summary.csv."""
    from .. import config as app_config
    from .config import DEFAULTS, TOKENS
    from .run import load_npz, result_path

    rd = Path(results_dir or app_config.RESULTS_DIR)
    rows = []
    for sp in DEFAULTS:
        tok = TOKENS[sp]
        row = {"species": sp, "token": tok}
        p = diag_dir(tok, rd) / "diagnostics.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            row.update({k: d.get(k) for k in SUMMARY_COLUMNS if k in d})
            row["monotonic_violations"] = (d.get("monotonicity") or {}).get("violations")
        loaded = load_npz(result_path(sp, "new", "npz", rd))
        if loaded is not None:
            meta = loaded[1]
            row.update({k: meta.get(k) for k in ("finished", "chains", "draws_per_chain")})
        rows.append({k: row.get(k) for k in SUMMARY_COLUMNS})
    out = Path(out or rd / "bayes_diagnostics_summary.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, rows)
    return out
