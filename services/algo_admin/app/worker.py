"""
Воркер очереди расчётов:  python -m app.worker   (FISH_WORKERS — число одновременных расчётов).

Каждый поток берёт следующий запуск из очереди (атомарно, под блокировкой файла запуска) и выполняет
его шаги в отдельных процессах (algorithms/executor.py). Длительные расчёты не блокируют интерфейс.
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


def process_one(engine: Engine, clients: Clients, log=print) -> bool:
    run = engine.claim(worker_name())
    if run is None:
        return False
    try:
        engine.execute(run, clients, log)
    except Exception as e:  # noqa: BLE001
        log(traceback.format_exc())
        engine.update_run(run["id"], status="failed", finished_at=now_iso(), message=f"Внутренняя ошибка воркера: {e}")
    return True


def main():
    st = settings_mod.load("algo_admin")
    engine = Engine(st.service_dir())
    clients = Clients(st)
    n = max(1, int(os.environ.get("FISH_WORKERS", "2")))
    rec = engine.recover_stale(socket.gethostname())
    print(f"[worker] потоков: {n}; прерванных запусков отмечено: {rec}", flush=True)
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
