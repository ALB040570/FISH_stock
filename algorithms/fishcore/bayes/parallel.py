"""Одновременный расчёт байесовской модели для нескольких видов и проверок (FishStock, решение № 64).

Формулы, настройки и seed не меняются: каждый расчёт вида (или проверки) идёт в отдельном процессе так же, как шёл
бы по очереди, — со своим seed и своими 4 цепями. Меняется только то, что независимые расчёты идут одновременно.

Число одновременных процессов — из лимита ядер ``FISH_CALC_CORES`` (по умолчанию 32, не больше числа ядер машины),
делённого на число цепей. Если получается 1 процесс (например, на компьютере с 2–4 ядрами), расчёты идут по очереди
в том же процессе — как до этого изменения.
"""
from __future__ import annotations

import importlib
import multiprocessing as mp
import os
import queue as _queue
import time
import traceback

DEFAULT_CORES = 32


def core_budget() -> int:
    """Явно заданный FISH_CALC_CORES берётся как есть; по умолчанию — 32, но не больше ядер машины."""
    try:
        n = int(os.environ.get("FISH_CALC_CORES") or 0)
    except ValueError:
        n = 0
    return max(1, n) if n > 0 else max(1, min(DEFAULT_CORES, os.cpu_count() or 1))


def n_procs(n_tasks: int, chains: int = 4) -> int:
    return max(1, min(n_tasks, core_budget() // max(1, chains)))


def snapshot() -> dict:
    """Состояние модулей настроек, которое алгоритм задал до расчёта: неизменяемые параметры fishcore.config,
    настройки видов из профиля водоёма (set_runtime) и коды видов (register_tokens) — их получит каждый процесс."""
    from .. import config as app_config
    from . import config as bc
    from pathlib import PurePath
    simple = (int, float, str, bool, type(None), tuple, list, dict, PurePath)
    cfg = {k: getattr(app_config, k) for k in dir(app_config) if k.isupper() and isinstance(getattr(app_config, k), simple)}
    return {"app_config": cfg, "runtime": bc._RUNTIME, "tokens": dict(bc._EXTRA_TOKENS)}


def _restore(state: dict) -> None:
    from .. import config as app_config
    from . import config as bc
    for k, v in state["app_config"].items():
        setattr(app_config, k, v)
    bc.set_runtime(state["runtime"])
    bc._EXTRA_TOKENS.update(state["tokens"])


def _child(key, target, kwargs, state, q, threads):
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = str(threads)
    base = None                                     # свой каталог компиляции: процессы не ждут общей блокировки
    flags = os.environ.get("PYTENSOR_FLAGS", "")
    for part in flags.split(","):
        if part.startswith("base_compiledir="):
            base = part.split("=", 1)[1]
    if base:
        rest = [p for p in flags.split(",") if p and not p.startswith("base_compiledir=")]
        os.environ["PYTENSOR_FLAGS"] = ",".join(rest + [f"base_compiledir={base}/{key}"])
    try:
        _restore(state)
        mod, name = target.split(":")
        fn = getattr(importlib.import_module(mod), name)
        last = [0.0]

        def progress(d):
            now = time.time()
            if now - last[0] >= 1.0 or d.get("phase") in ("done", "save"):
                last[0] = now
                q.put(("progress", key, d))

        def log(*msg):
            q.put(("log", key, " ".join(str(m) for m in msg)))
        out = fn(progress=progress, log=log, **kwargs)
        q.put(("done", key, out))
    except BaseException as e:  # noqa: BLE001
        q.put(("error", key, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))


def _kill(p):
    """Остановить процесс расчёта; оставшиеся процессы цепей завершит исполнитель шага (вся группа процессов шага)."""
    p.kill()
    p.join(5)


def run_tasks(tasks, target: str, on_progress, log, check, chains: int = 4) -> dict:
    """tasks — [(ключ, kwargs)]; target — 'модуль:функция(progress, log, **kwargs)'. Возвращает {ключ: результат}.

    on_progress(доли {ключ: 0..1}, текущие {ключ: последнее сообщение}) — ход выполнения; check() — проверка отмены
    (исключение прерывает расчёт, процессы завершаются). Ошибка любого расчёта прерывает все.
    """
    procs = n_procs(len(tasks), chains)
    frac = {k: 0.0 for k, _ in tasks}
    info: dict = {}
    if procs <= 1:                                  # по очереди, в этом же процессе — как раньше
        out = {}
        mod, name = target.split(":")
        fn = getattr(importlib.import_module(mod), name)
        for key, kw in tasks:
            def progress(d, key=key):
                frac[key] = _fraction(d, frac[key])
                info[key] = d
                on_progress(frac, info)
            out[key] = fn(progress=progress, log=log, **kw)
            frac[key] = 1.0
            info.pop(key, None)
        return out
    threads = max(1, core_budget() // (procs * max(1, chains)))
    log(f"одновременно: {procs} расчётов по {chains} цепи (лимит ядер {core_budget()}; всего расчётов {len(tasks)})")
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    state = snapshot()
    pending = list(tasks)
    running: dict = {}
    out: dict = {}
    def handle(msg):
        kind, key, data = msg
        if kind == "progress":
            frac[key] = _fraction(data, frac[key])
            info[key] = data
        elif kind == "log":
            log(data if data.startswith("[") else f"[{key}] {data}")
        elif kind == "done":
            out[key] = data
            frac[key] = 1.0
            info.pop(key, None)
            running.pop(key).join(30)
            log(f"готов расчёт: {key}")
        elif kind == "error":
            raise RuntimeError(f"расчёт «{key}» завершился с ошибкой: {data}")

    try:
        while pending or running:
            while pending and len(running) < procs:
                key, kw = pending.pop(0)
                p = ctx.Process(target=_child, args=(key, target, kw, state, q, threads), daemon=False)
                p.start()
                running[key] = p
                log(f"начат расчёт: {key}")
            try:
                handle(q.get(timeout=1.0))
            except _queue.Empty:
                pass
            for key, p in list(running.items()):     # процесс завершился без «готово» (нехватка памяти и т.п.)
                if key in running and not p.is_alive():
                    while True:                       # сначала дочитать его сообщения
                        try:
                            handle(q.get(timeout=2.0))
                        except _queue.Empty:
                            break
                    if key in running:
                        raise RuntimeError(f"расчёт «{key}» прерван: процесс завершился с кодом {p.exitcode}")
            on_progress(frac, info)
            check()
    finally:
        for p in running.values():
            _kill(p)
    return out


def _fraction(d: dict, cur: float) -> float:
    if d.get("total") and d.get("chains"):
        done = sum(d["chains"].values()) / max(1, len(d["chains"]))
        return max(cur, min(0.99, done / d["total"]))
    return cur


# ---------------------------------------------------------------- функции, которые выполняются в процессах
def fit_species(progress, log, species, mode, results_dir, stage23):
    """Расчёт модели вида — то же, что шаг «Байесовская когортная модель» делал для вида по очереди."""
    from pathlib import Path
    from . import run as R
    return R.run(species, mode, progress=progress, log=log, results_dir=Path(results_dir), stage23=stage23, plots=False)


def check_species(progress, log, name, species, kw):
    """Одна проверка модели для вида (ретроспектива, априорные, пустые ловы — один вариант, синтетические данные)."""
    from . import analyses as A
    from . import run as R
    orig = R.run

    def run_with_progress(*a, **k):
        k.setdefault("progress", progress)
        return orig(*a, **k)
    R.run = run_with_progress
    try:
        fn = {"retro": A.retro, "prior": A.prior_sensitivity, "pad": A.pad_sensitivity, "recovery": A.recovery}[name]
        return fn(species, log=log, **kw)
    finally:
        R.run = orig
