"""
Запуск FishStocke без Docker (разработка, проверка, Windows/macOS/Linux).

    python deploy/run_local.py            # все 6 сервисов + воркеры + шлюз на http://127.0.0.1:8080
    python deploy/run_local.py --port 9000 --workers 1

Перед первым запуском: pip install -r requirements-dev.txt; cd frontend && npm ci && npm run build.
Данные — в каталоге ./data (переменная FISH_DATA_DIR).
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "libs" / "fishcommon"))
from fishcommon.settings import SERVICE_PORTS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("FISH_HTTP_PORT", 8080)))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("FISH_WORKERS", 2)))
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()

    env = dict(os.environ)
    env.setdefault("FISH_DATA_DIR", str(REPO / "data"))
    env["PYTHONPATH"] = os.pathsep.join([str(REPO / "libs" / "fishcommon"), str(REPO), env.get("PYTHONPATH", "")])
    env["FISH_WORKERS"] = str(args.workers)
    procs = []

    def spawn(cmd, cwd):
        procs.append(subprocess.Popen(cmd, cwd=cwd, env=env))

    # users первым: другие сервисы пишут в его журнал
    order = ["users"] + [s for s in SERVICE_PORTS if s != "users"]
    for name in order:
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(SERVICE_PORTS[name])]
        if args.reload:
            cmd += ["--reload"]
        spawn(cmd, REPO / "services" / name)
        if name == "users":
            time.sleep(1.5)
    if (REPO / "services" / "algo_admin" / "app" / "worker.py").exists():
        spawn([sys.executable, "-m", "app.worker"], REPO / "services" / "algo_admin")
    spawn([sys.executable, "-m", "uvicorn", "devgateway:app", "--host", args.host, "--port", str(args.port)],
          REPO / "deploy")
    print(f"\nFishStocke: http://{args.host}:{args.port}  (Ctrl+C — остановить)\n", flush=True)

    def stop(*_):
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while True:
        time.sleep(1)
        for p in procs:
            if p.poll() is not None:
                print(f"Процесс {p.args} завершился с кодом {p.returncode}", flush=True)
                stop()


if __name__ == "__main__":
    main()
