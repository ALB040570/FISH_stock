"""
Рисунки статьи по результатам основного расчёта (results/zhaysan_bayes_{вид}.npz), PNG для Word.

    python -m scripts.make_figures
    python -m scripts.make_figures --out results/figures --dpi 300

Файлы (results/figures/):
    fig02_bream.png … fig09_ide.png — суммарная численность по годам: медиана и 95 %-й интервал модели
        (все возрасты и возраст 2+), оценки методом площадей (невод) и балансовым методом (сеть), ПДУ, млн шт.;
    fig10_crucian_carp_ages.png, fig11_zander_ages.png, fig12_roach_ages.png — численность по возрастам
        за последние 5 лет (медиана), тыс. шт.
Подписи на английском (для статьи). Прямые оценки — те, что вошли в правдоподобие (yearly_seine, yearly_net).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from core import config as app_config
from core.bayes import run as R

# номер рисунка, вид, название в статье
STOCK_FIGURES = ((2, "лещ", "Bream"), (3, "судак", "Zander"), (4, "окунь", "Perch"), (5, "плотва", "Roach"),
                 (6, "щука", "Pike"), (7, "сазан", "Common carp"), (8, "карась", "Crucian carp"), (9, "язь", "Ide"))
AGE_FIGURES = ((10, "карась", "Crucian carp"), (11, "судак", "Zander"), (12, "плотва", "Roach"))

COLORS = {"model": "#1f5fa8", "model2": "#2a9d8f", "seine": "#e07b39", "net": "#7b4fa8", "tac": "#c0392b"}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def stock_figure(plt, arrays: dict, title: str, path: Path, dpi: int) -> None:
    years = np.array([int(y) for y in arrays["years"]])
    mil = 1e6
    all_q, obs_q = arrays["total_all_q"] / mil, arrays["total_obs_q"] / mil      # квантили 2,5/25/50/75/97,5 %
    seine = np.nansum(arrays["yearly_seine"], axis=1) / mil
    net = np.nansum(arrays["yearly_net"], axis=1) / mil
    tac = np.nansum(arrays["pdu_raw"], axis=1) / mil

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.fill_between(years, all_q[0], all_q[4], color=COLORS["model"], alpha=0.15, lw=0,
                    label="Model, all ages: 95% interval")
    ax.plot(years, all_q[2], color=COLORS["model"], lw=2.2, marker="o", ms=4, label="Model, all ages: median")
    ax.fill_between(years, obs_q[0], obs_q[4], color=COLORS["model2"], alpha=0.15, lw=0,
                    label="Model, age 2+: 95% interval")
    ax.plot(years, obs_q[2], color=COLORS["model2"], lw=2.0, ls="--", marker="o", ms=4,
            label="Model, age 2+: median")
    ax.plot(years, seine, color=COLORS["seine"], lw=1.4, marker="s", ms=4, label="Swept-area method (seine)")
    ax.plot(years, net, color=COLORS["net"], lw=1.4, marker="^", ms=4, label="Balance method (net)")
    ax.plot(years, tac, color=COLORS["tac"], lw=1.4, ls=":", marker="x", ms=4, label="Total allowable catch")
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Abundance, million fish")
    ax.set_xticks(years)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#dddddd", lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=7.5, ncol=2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def age_figure(plt, arrays: dict, title: str, path: Path, dpi: int, last: int = 5) -> None:
    years = [int(y) for y in arrays["years"]][-last:]
    ages = np.array([int(a) for a in arrays["model_ages"]])
    med = arrays["X_q"][2, -last:, :] / 1e3
    width = 0.8 / len(years)
    cmap = plt.get_cmap("viridis")

    fig, ax = plt.subplots(figsize=(8.0, 3.4))
    for k, y in enumerate(years):
        ax.bar(ages - 0.4 + width * (k + 0.5), med[k], width=width, color=cmap(k / max(len(years) - 1, 1)),
               label=str(y))
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel("Age, years")
    ax.set_ylabel("Abundance, thousand fish")
    ax.set_xticks(ages)
    ax.grid(axis="y", color="#dddddd", lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(title="Year", fontsize=8, title_fontsize=8, frameon=False, ncol=len(years))
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def make_figures(out_dir: Path | None = None, dpi: int = 300, results_dir: Path | None = None, log=print) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rd = Path(results_dir or app_config.RESULTS_DIR)
    out_dir = Path(out_dir or rd / "figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict | None] = {}

    def arrays_of(sp: str) -> dict | None:
        if sp not in cache:
            loaded = R.load_npz(R.result_path(sp, "new", "npz", rd))
            cache[sp] = loaded[0] if loaded else None
            if loaded is None:
                log(f"  {sp}: нет результата {R.result_path(sp, 'new', 'npz', rd).name} — рисунок пропущен")
        return cache[sp]

    for n, sp, name in STOCK_FIGURES:
        a = arrays_of(sp)
        if a is not None:
            path = out_dir / f"fig{n:02d}_{_slug(name)}.png"
            stock_figure(plt, a, f"Figure {n}. {name}: stock estimates by year", path, dpi)
            log(f"  {path.name}")
    for n, sp, name in AGE_FIGURES:
        a = arrays_of(sp)
        if a is not None:
            path = out_dir / f"fig{n:02d}_{_slug(name)}_ages.png"
            age_figure(plt, a, f"Figure {n}. {name}: abundance by age, last 5 years", path, dpi)
            log(f"  {path.name}")
    return out_dir


def main() -> None:
    ap = argparse.ArgumentParser(description="Рисунки статьи (PNG) по результатам байесовской модели")
    ap.add_argument("--out", type=Path, default=None, help="папка для PNG (по умолчанию results/figures)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--results", type=Path, default=None, help="папка результатов (по умолчанию results)")
    args = ap.parse_args()
    out = make_figures(args.out, args.dpi, args.results)
    print(f"Рисунки: {out}")


if __name__ == "__main__":
    main()
