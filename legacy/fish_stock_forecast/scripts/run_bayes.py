"""
Байесовская модель (этап 4) из командной строки.

    python -m scripts.run_bayes --species окунь
    python -m scripts.run_bayes --species все                      # все 8 видов подряд (можно на ночь)
    python -m scripts.run_bayes --species лещ судак --mode check   # сверка со старыми скриптами
    python -m scripts.run_bayes --species все --mode prior         # априорная проверка, секунды

Режимы: new — новые входные данные и настройки со страницы; check — входные данные и настройки
старого скрипта (сравнение со старыми .nc); prior — только априорные распределения (без PyMC).
Параметр --job используется приложением: состояние пишется в results/bayes_jobs/<job>.json.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import traceback
from datetime import datetime

from core.bayes import run as R
from core.bayes.config import DEFAULTS, TOKENS
from core.bayes.jobfiles import read_json, status_path, write_json

ALL = ("все", "all")


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
    ap.add_argument("--species", nargs="+", required=True, help="виды через пробел или «все»")
    ap.add_argument("--mode", choices=R.MODES, default="new")
    ap.add_argument("--job", default=None)
    args = ap.parse_args(argv)
    species = resolve_species(args.species)
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
                meta = R.run(sp, args.mode, progress=st.progress, log=log, stage23=stage23)
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


if __name__ == "__main__":
    main()
