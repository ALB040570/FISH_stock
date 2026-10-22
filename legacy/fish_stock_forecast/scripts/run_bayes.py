"""
Байесовская модель (этап 4) из командной строки.

    python -m scripts.run_bayes --species окунь
    python -m scripts.run_bayes --species все                      # все 8 видов подряд (можно на ночь)
    python -m scripts.run_bayes --species лещ судак --mode check   # сверка со старыми скриптами
    python -m scripts.run_bayes --species все --mode prior         # априорная проверка, секунды
    python -m scripts.run_bayes --species карась --mode legacy     # старая модель (calc_stock_bayes_2g1p_karas.py) на новых данных
    python -m scripts.run_bayes --species карась --mode legacy --age-old   # то же, возрастные пробы: +1 к каждой группе, как раньше
    python -m scripts.run_bayes --species карась --set delta_pos=gamma sigma_stock_sd=3 --tag _gamma   # другие настройки

Режимы: new (= main) — новые входные данные и настройки со страницы; check — входные данные и настройки
старого скрипта (сравнение со старыми .nc); prior — только априорные распределения (без PyMC).
Параметр --job используется приложением: состояние пишется в results/bayes_jobs/<job>.json.

Проверки для ответа рецензентам (core.bayes.analyses; результаты в results/<вид>/<проверка>/):
    python -m scripts.run_bayes --species все --mode retro --year-max 2021   # ретроспектива 2022–2024
    python -m scripts.run_bayes --species все --mode prior_sens --factor 2   # σ смертности и β × 2
    python -m scripts.run_bayes --species лещ --mode pad --pads 0.1 1 10     # добавка к оценкам по ловам
    python -m scripts.run_bayes --species лещ --mode recovery                # восстановление параметров
Без MCMC:
    python -m scripts.run_bayes --mode diag_summary   # сводка диагностики → results/bayes_diagnostics_summary.csv
    python -m scripts.run_bayes --mode appendix       # таблицы A1–A8 → results/appendix/
    python -m scripts.run_bayes --mode balance        # чувствительность модели баланса сети
    python -m scripts.run_bayes --mode retro_metrics  # метрики ретроспективы по сохранённым выборкам
Короткие цепи для пробы: --chains 2 --draws 200 --tune 200; без графиков диагностики: --no-plots.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import threading
import time
import traceback
from datetime import datetime

from core.bayes import run as R
from core.bayes.config import DEFAULTS, TOKENS, SpeciesConfig, _coerce
from core.bayes.jobfiles import read_json, status_path, write_json

ALL = ("все", "all")
ANALYSES = ("retro", "prior_sens", "pad", "recovery")
NO_MCMC = ("diag_summary", "appendix", "balance", "retro_metrics")
CLI_MODES = ("main",) + R.MODES + ANALYSES + NO_MCMC


def resolve_species(items: list[str]) -> list[str]:
    by_token = {v: k for k, v in TOKENS.items()}
    out = []
    for it in items:
        it = it.strip().lower()
        if it in ALL:
            return list(DEFAULTS)
        name = by_token.get(it, it)
        if name not in DEFAULTS:
            raise SystemExit(f"неизвестный вид: {it}; допустимо: {', '.join(DEFAULTS)} или «все»")
        if name not in out:
            out.append(name)
    return out


class Status:
    """Состояние расчёта для страницы (если задан --job)."""

    def __init__(self, job: str | None, species: list[str], mode: str):
        self.path = status_path(job) if job else None
        self.lock = threading.Lock()
        self.data = (read_json(self.path) if self.path else None) or {}
        self.data.update({"id": job, "mode": mode, "species": species, "pid": os.getpid(), "state": "running",
                          "started": self.data.get("started") or _now(), "finished": [], "current": None,
                          "index": 0, "progress": {"phase": "start"}, "error": None})
        self.write()
        if self.path:
            threading.Thread(target=self._heartbeat, daemon=True).start()

    def _heartbeat(self):
        while True:
            time.sleep(10)
            self.write()

    def write(self):
        if not self.path:
            return
        with self.lock:
            self.data["updated"] = _now()
            self.data["updated_ts"] = time.time()
            write_json(self.path, self.data)

    def begin(self, sp: str, i: int):
        self.data.update(current=sp, index=i, progress={"phase": "inputs"}, species_started=_now(),
                         species_started_ts=time.time())
        self.write()

    def progress(self, d: dict):
        self.data["progress"] = d
        self.write()

    def finish(self, sp: str, meta: dict | None, error: str | None = None):
        row = {"species": sp, "error": error}
        if meta:
            row.update({k: meta.get(k) for k in ("seconds", "divergences", "rhat_X_max", "chains", "draws_per_chain")})
        self.data["finished"].append(row)
        self.write()

    def done(self, state: str = "done", error: str | None = None):
        self.data.update(state=state, error=error, current=None, progress={"phase": state}, ended=_now())
        self.write()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(*a):
    print(*a, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Байесовская когортная модель (этап 4)")
    ap.add_argument("--species", nargs="+", default=None, help="виды через пробел или «все»")
    ap.add_argument("--mode", choices=CLI_MODES, default="new")
    ap.add_argument("--job", default=None)
    ap.add_argument("--chains", type=int, default=None, help="цепей (иначе — из настроек вида)")
    ap.add_argument("--draws", type=int, default=None)
    ap.add_argument("--tune", type=int, default=None)
    ap.add_argument("--target-accept", type=float, default=None)
    ap.add_argument("--noncentered", action="store_true", help="нецентрированные годовые эффекты s и β")
    ap.add_argument("--no-plots", action="store_true", help="не строить графики диагностики")
    ap.add_argument("--year-max", type=int, default=2021, help="retro: последний год оценки")
    ap.add_argument("--factor", type=float, default=2.0, help="prior_sens: множитель σ")
    ap.add_argument("--pads", type=float, nargs="+", default=[0.1, 1.0, 10.0], help="pad: значения obs_pad")
    ap.add_argument("--seed", type=int, default=0, help="retro, recovery: seed моделирования")
    ap.add_argument("--results-dir", default=None, help="папка результатов (по умолчанию results/)")
    ap.add_argument("--set", nargs="+", default=[], metavar="ключ=значение",
                    help="изменить настройки вида на этот запуск, напр. delta_pos=gamma sigma_stock_sd=3")
    ap.add_argument("--tag", default="", help="добавка к имени файлов результатов, напр. _gamma")
    ap.add_argument("--age-old", action="store_true",
                    help="сглаживание возрастных проб как в старом проекте: +1 рыба к каждой группе, без объединения лет")
    args = ap.parse_args(argv)
    if args.results_dir:
        from pathlib import Path

        from core import config as app_config
        app_config.RESULTS_DIR = Path(args.results_dir)
    if args.mode == "main":
        args.mode = "new"
    tag = args.tag
    if args.age_old:
        from core import config as app_config
        app_config.AGE_PSEUDOCOUNT_TOTAL = None
        app_config.AGE_POOL_MIN_SAMPLE = 0
        tag = tag or "_age1"
    if args.mode in NO_MCMC:
        return run_no_mcmc(args)
    if not args.species:
        ap.error("нужен --species")
    species = resolve_species(args.species)
    changes = {k: v for k, v in (("chains", args.chains), ("draws", args.draws), ("tune", args.tune),
                                 ("target_accept", args.target_accept)) if v is not None}
    if args.noncentered:
        changes["noncentered"] = True
    for item in args.set:
        key, _, value = item.partition("=")
        if key not in {f.name for f in dataclasses.fields(SpeciesConfig)}:
            ap.error(f"--set: нет настройки {key}")
        changes[key] = _coerce(key, value)
    if args.mode in ANALYSES:
        return run_analyses(args, species, changes)
    st = Status(args.job, species, args.mode)
    log(f"{_now()}  {R.MODE_TITLES[args.mode]}: {', '.join(species)}")

    stage23 = None
    try:
        if args.mode != "check":
            from core.data_source import load_fish_props
            from core.pdu_npc import compute_pdu
            from core.stock import compute_stock

            log("Этапы 2–3: запас по уловам и ПДУ по возрастам…")
            props = load_fish_props()
            res, _, _ = compute_stock(props=props)
            stage23 = (res, compute_pdu(res, props), props)
        errors = 0
        for i, sp in enumerate(species):
            st.begin(sp, i)
            try:
                meta = R.run(sp, args.mode, progress=st.progress, log=log, stage23=stage23,
                             cfg_changes=changes or None, plots=not args.no_plots, tag=tag)
                st.finish(sp, meta)
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001 — один вид не должен останавливать остальные
                errors += 1
                traceback.print_exc()
                sys.stdout.flush()
                st.finish(sp, None, f"{type(e).__name__}: {e}")
        st.done("done" if errors < len(species) else "failed",
                None if not errors else f"с ошибкой: {errors} из {len(species)}")
        log(f"{_now()}  завершено")
    except KeyboardInterrupt:
        st.done("cancelled")
        log("остановлено")
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        st.done("failed", f"{type(e).__name__}: {e}")
        raise


def _stage23():
    from core.data_source import load_fish_props
    from core.pdu_npc import compute_pdu
    from core.stock import compute_stock

    log("Этапы 2–3: запас по уловам и ПДУ по возрастам…")
    props = load_fish_props()
    res, _, _ = compute_stock(props=props)
    return res, compute_pdu(res, props), props


def run_analyses(args, species: list[str], changes: dict) -> int:
    """retro / prior_sens / pad / recovery для каждого вида; ошибка одного вида не останавливает остальные."""
    from core.bayes import analyses as A

    log(f"{_now()}  проверка {args.mode}: {', '.join(species)}")
    stage23 = _stage23()
    plots = not args.no_plots
    errors = 0
    for sp in species:
        try:
            if args.mode == "retro":
                r = A.retro(sp, args.year_max, stage23, cfg_changes=changes, log=log, plots=plots, seed=args.seed)
                for m in r["metrics"][:2]:
                    log(f"  [{sp}] {m['subset']}: RMSE {m.get('rmse_log')}, MAE {m.get('mae_log')}, "
                        f"покрытие 95 % {m.get('coverage95')}")
            elif args.mode == "prior_sens":
                A.prior_sensitivity(sp, args.factor, stage23, cfg_changes=changes, log=log, plots=plots)
            elif args.mode == "pad":
                A.pad_sensitivity(sp, tuple(args.pads), stage23, cfg_changes=changes, log=log, plots=plots)
            else:
                r = A.recovery(sp, stage23, cfg_changes=changes, log=log, plots=plots, seed=args.seed)
                for m in r["coverage"]:
                    log(f"  [{sp}] {m['quantity']}: покрытие 95 % {m['coverage95']:.2f} (n = {m['n']})")
        except KeyboardInterrupt:
            raise
        except Exception:  # noqa: BLE001
            errors += 1
            traceback.print_exc()
            sys.stdout.flush()
    log(f"{_now()}  завершено" + (f", с ошибкой: {errors}" if errors else ""))
    return 1 if errors else 0


def run_no_mcmc(args) -> int:
    if args.mode == "diag_summary":
        from core.bayes.diagnostics import collect_summary
        log(f"записано: {collect_summary()}")
    elif args.mode == "retro_metrics":
        from core.bayes import analyses as A
        for sp in resolve_species(args.species or ["все"]):
            rows = A.retro_metrics(sp, args.year_max, seed=args.seed)["metrics"]
            log(f"[{sp}] " + "; ".join(f"{r['subset']}: RMSE {r['rmse_log']:.2f}, покрытие {r['coverage95']:.2f}"
                                        for r in rows[:2] if r.get("n")))
    elif args.mode == "appendix":
        from scripts.make_appendix_tables import make_tables
        log(f"записано: {make_tables(log=log)}")
    else:
        from core.net_sensitivity import balance_sensitivity
        sp = resolve_species(args.species) if args.species else None
        log(f"записано: {balance_sensitivity(sp)}")
    return 0


if __name__ == "__main__":
    main()
