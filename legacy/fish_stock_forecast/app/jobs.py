"""
Фоновый расчёт байесовской модели: отдельный процесс `python -m scripts.run_bayes`.

Один расчёт за раз. Процесс пишет состояние в results/bayes_jobs/<id>.json и журнал в <id>.log;
страница опрашивает /api/bayes/status. Остановка — завершение процесса со всеми дочерними
(PyMC запускает цепи в отдельных процессах).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

from core import config
from core.bayes.jobfiles import jobs_dir, log_path, read_json, status_path, tail, write_json

_lock = threading.RLock()
_proc: subprocess.Popen | None = None
_job_id: str | None = None
STALE_SECONDS = 90      # нет отметки процесса дольше — считаем, что он завершился


def _latest_id() -> str | None:
    files = sorted(p.stem for p in jobs_dir().glob("*.json"))
    return files[-1] if files else None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 timeout=10).stdout
            return str(pid) in out
        except Exception:  # noqa: BLE001
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _alive(st: dict) -> bool:
    if _proc is not None and st.get("id") == _job_id:
        return _proc.poll() is None
    if not _pid_alive(st.get("pid")):
        return False
    return time.time() - float(st.get("updated_ts") or 0) < STALE_SECONDS


def status(job_id: str | None = None) -> dict | None:
    with _lock:
        job_id = job_id or _latest_id()
        if not job_id:
            return None
        st = read_json(status_path(job_id))
        if st is None:
            return None
        if st.get("state") == "running" and not _alive(st):
            st.update(state="failed", error=st.get("error") or "процесс расчёта завершился без отчёта (см. журнал)",
                      ended=datetime.now().isoformat(timespec="seconds"))
            write_json(status_path(job_id), st)
        st["log"] = tail(log_path(job_id))
        st["now_ts"] = time.time()
        return st


def running() -> bool:
    st = status()
    return bool(st and st.get("state") == "running")


def start(species: list[str], mode: str) -> dict:
    global _proc, _job_id
    with _lock:
        if running():
            raise RuntimeError("уже идёт расчёт — дождитесь окончания или остановите его")
        job_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        write_json(status_path(job_id), {"id": job_id, "mode": mode, "species": species, "state": "running",
                                         "started": datetime.now().isoformat(timespec="seconds"),
                                         "updated_ts": time.time(), "progress": {"phase": "start"},
                                         "finished": [], "current": None, "index": 0})
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw["start_new_session"] = True
        logf = open(log_path(job_id), "ab")
        cmd = [sys.executable, "-m", "scripts.run_bayes", "--mode", mode, "--job", job_id, "--species", *species]
        _proc = subprocess.Popen(cmd, cwd=str(config.PROJECT_ROOT), stdout=logf, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, env=env, **kw)
        logf.close()
        _job_id = job_id
        st = read_json(status_path(job_id)) or {}
        if not st.get("pid"):
            st["pid"] = _proc.pid
            write_json(status_path(job_id), st)
        return status(job_id)


def cancel() -> dict | None:
    with _lock:
        st = status()
        if not st or st.get("state") != "running":
            return st
        pid = st.get("pid") or (_proc.pid if _proc is not None else None)
        if pid:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except OSError:
                    pass
        if _proc is not None:
            try:
                _proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                _proc.kill()
        st = read_json(status_path(st["id"])) or st
        st.update(state="cancelled", error=None, current=None, ended=datetime.now().isoformat(timespec="seconds"),
                  progress={"phase": "cancelled"})
        write_json(status_path(st["id"]), st)
        with open(log_path(st["id"]), "ab") as f:
            f.write("остановлено пользователем\n".encode("utf-8"))
        return status(st["id"])
