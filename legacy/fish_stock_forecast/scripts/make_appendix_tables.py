"""
Таблицы приложения A1–A8: численность X_estimated по возрастам и годам (медиана и 95 %-й интервал)
по результатам основного расчёта (results/zhaysan_bayes_{вид}.npz).

    python -m scripts.make_appendix_tables
    python -m scripts.make_appendix_tables --out results/appendix --units 1000

Файлы (results/appendix/):
    table_A{n}_{вид}.csv       — возрасты × годы, ячейка «медиана [2,5 %; 97,5 %]» в выбранных единицах;
    appendix_X_long.csv        — все виды в длинном формате (вид, возраст, год, медиана, 2,5 %, 97,5 %), штук;
    appendix_tables.md         — те же таблицы в Markdown (вставляются в Word через Pandoc или копированием).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from core import config as app_config
from core.ages import age_title
from core.bayes import run as R

# порядок таблиц приложения
APPENDIX_ORDER = (("лещ", "Лещ"), ("судак", "Судак"), ("окунь", "Окунь"), ("плотва", "Плотва"),
                  ("щука", "Щука"), ("сазан", "Сазан"), ("карась", "Карась"), ("язь", "Язь"))
UNIT_NAMES = {1: "шт.", 1000: "тыс. шт.", 1_000_000: "млн шт."}


def _fmt(v: float, units: float) -> str:
    x = v / units
    if not np.isfinite(x):
        return "—"
    if abs(x) >= 100:
        s = f"{x:,.0f}"
    elif abs(x) >= 10:
        s = f"{x:,.1f}"
    else:
        s = f"{x:,.2f}"
    return s.replace(",", " ").replace(".", ",")


def species_table(arrays: dict, units: float) -> pd.DataFrame:
    """Возрасты × годы: «медиана [2,5 %; 97,5 %]»."""
    X_q = arrays["X_q"]
    years = [int(y) for y in arrays["years"]]
    ages = [int(a) for a in arrays["model_ages"]]
    data = {y: [f"{_fmt(X_q[2, t, j], units)} [{_fmt(X_q[0, t, j], units)}; {_fmt(X_q[4, t, j], units)}]"
                for j in range(len(ages))] for t, y in enumerate(years)}
    df = pd.DataFrame(data, index=[age_title(a) for a in ages])
    df.index.name = "возраст"
    return df


def to_markdown(df: pd.DataFrame) -> str:
    head = "| " + " | ".join([df.index.name] + [str(c) for c in df.columns]) + " |"
    sep = "|" + "|".join(["---"] * (len(df.columns) + 1)) + "|"
    body = ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |" for i, row in zip(df.index, df.values)]
    return "\n".join([head, sep, *body])


def make_tables(out_dir: Path | None = None, units: float = 1000, results_dir: Path | None = None,
                log=print) -> Path:
    rd = Path(results_dir or app_config.RESULTS_DIR)
    out_dir = Path(out_dir or rd / "appendix")
    out_dir.mkdir(parents=True, exist_ok=True)
    unit = UNIT_NAMES.get(int(units), f"× {units:g} шт.")
    md = ["# Приложение. Численность по возрастам и годам (байесовская модель)", "",
          f"Медиана и 95 %-й интервал апостериорного распределения X_estimated; единицы — {unit}", ""]
    long_rows = []
    for n, (sp, title) in enumerate(APPENDIX_ORDER, start=1):
        loaded = R.load_npz(R.result_path(sp, "new", "npz", rd))
        if loaded is None:
            log(f"  {sp}: нет результата {R.result_path(sp, 'new', 'npz', rd).name} — таблица A{n} пропущена")
            md += [f"## Таблица A{n}. {title}", "", "_Нет результата расчёта._", ""]
            continue
        arrays, meta = loaded
        df = species_table(arrays, units)
        tok = R.TOKENS[sp]
        df.to_csv(out_dir / f"table_A{n}_{tok}.csv", encoding="utf-8-sig")
        md += [f"## Таблица A{n}. {title}: численность X_estimated, {unit}, медиана [95 %-й интервал]", "",
               to_markdown(df), "",
               f"_Расчёт: {meta.get('finished')}, цепей {meta.get('chains')}, выборок на цепь "
               f"{meta.get('draws_per_chain')}, расходимостей {meta.get('divergences')}._", ""]
        X_q = arrays["X_q"]
        for t, y in enumerate(arrays["years"]):
            for j, a in enumerate(arrays["model_ages"]):
                long_rows.append({"table": f"A{n}", "species": sp, "age": int(a), "age_title": age_title(a),
                                  "year": int(y), "median": X_q[2, t, j], "q025": X_q[0, t, j], "q975": X_q[4, t, j]})
        log(f"  A{n} {sp}: {df.shape[0]} возрастов × {df.shape[1]} лет")
    pd.DataFrame(long_rows).to_csv(out_dir / "appendix_X_long.csv", index=False, encoding="utf-8-sig")
    path = out_dir / "appendix_tables.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Таблицы приложения A1–A8 (численность X_estimated)")
    ap.add_argument("--out", default=None, help="папка (по умолчанию results/appendix)")
    ap.add_argument("--units", type=float, default=1000, help="единицы: 1, 1000 (тыс. шт.), 1000000")
    args = ap.parse_args(argv)
    path = make_tables(args.out, args.units)
    print(f"записано: {path}")


if __name__ == "__main__":
    main()
