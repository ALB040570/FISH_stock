"""
Воркер очереди расчётов:  python -m app.worker   (FISH_WORKERS — число одновременных расчётов).

Каждый поток берёт следующий расчёт из очереди (атомарно, под блокировкой файла расчёта; расчёт, чьи входы ещё
в очереди или выполняются, ждёт) и выполняет алгоритм в отдельном процессе (algorithms/executor.py). Длительные
расчёты не блокируют интерфейс (решение № 70).
"""
from __future__ import annotations

import os
import socket
import threading
import time
import traceback

from fishcommon import settings as settings_mod
from fishcommon.storage import now_iso

from .clients import Clients
from .engine import Engine, worker_name
from .planning import plan


def process_one(engine: Engine, clients: Clients, log=print) -> bool:
    c = engine.claim(worker_name())
    if c is None:
        return False
    try:
        engine.execute(c, clients, lambda x: plan(engine, clients, x), log)
    except Exception as e:  # noqa: BLE001
        log(traceback.format_exc())
        msg = f"Внутренняя ошибка воркера: {e}"
        engine.update_calc(c["id"], state="failed", finished_at=now_iso(), message=msg, progress=None)
        engine.add_journal(c["id"], {"action": "run", "status": "failed", "message": msg})
    return True


def main():
    st = settings_mod.load("algo_admin")
    engine = Engine(st.service_dir())
    clients = Clients(st)
    n = max(1, int(os.environ.get("FISH_WORKERS", "2")))
    rec = engine.recover_stale(socket.gethostname())
    print(f"[worker] потоков: {n}; прерванных расчётов отмечено: {rec}", flush=True)
    stop = threading.Event()

    def loop(k):
        while not stop.is_set():
            try:
                if not process_one(engine, clients, lambda m: print(f"[worker {k}] {m}", flush=True)):
                    time.sleep(2)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                time.sleep(5)

    threads = [threading.Thread(target=loop, args=(k,), daemon=True) for k in range(n)]
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
