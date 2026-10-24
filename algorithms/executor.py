"""
Подготовка и запуск шага расчёта в отдельном процессе (используют воркеры «Администрирования
алгоритмов» и тестовые прогоны «Моделирования алгоритмов»).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def prepare_step(step_dir: Path, package_files: dict[str, bytes], context: dict) -> Path:
    step_dir = Path(step_dir)
    pkg = step_dir / "package"
    pkg.mkdir(parents=True, exist_ok=True)
    for name, content in package_files.items():
        target = pkg / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            raise ValueError(f"недопустимое имя файла в пакете: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (step_dir / "context.json").write_text(json.dumps(context, ensure_ascii=False, default=str), encoding="utf-8")
    return step_dir


def _kill(p) -> None:
    """Завершить шаг вместе с его процессами (группа процессов шага)."""
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        p.kill()
    p.wait()


def _kill_group(p) -> None:
    """После шага не должно остаться его процессов (цепи PyMC, расчёты видов)."""
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_step(step_dir: Path, timeout_s: float | None = None, on_poll=None, poll_s: float = 1.0) -> dict:
    """Запуск fishrunner в отдельном процессе. on_poll() вызывается периодически; вернёт True — отменить."""
    step_dir = Path(step_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTENSOR_FLAGS", f"base_compiledir={step_dir / '.pytensor'}")
    log = open(step_dir / "stdout.txt", "ab")
    # своя группа процессов: при отмене и превышении времени завершаются и процессы цепей и видов (№ 64)
    p = subprocess.Popen([sys.executable, "-m", "fishrunner", str(step_dir)], cwd=step_dir, env=env,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    try:
        while p.poll() is None:
            time.sleep(poll_s)
            if on_poll and on_poll():
                (step_dir / "CANCEL").write_text("1")
            if (step_dir / "CANCEL").exists():
                try:
                    p.wait(30)          # алгоритм сам завершится при ближайшем ctx.progress()
                except subprocess.TimeoutExpired:
                    _kill(p)
                st = {}
                try:
                    st = json.loads((step_dir / "status.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
                if st.get("status") not in ("done", "failed", "cancelled"):
                    st = {"status": "cancelled", "message": "Расчёт отменён пользователем"}
                    (step_dir / "status.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
                return st
            if timeout_s and time.time() - t0 > timeout_s:
                _kill(p)
                st = {"status": "failed", "message": f"Превышено время выполнения шага ({int(timeout_s // 60)} мин)"}
                (step_dir / "status.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
                return st
    finally:
        log.close()
        _kill_group(p)
    try:
        return json.loads((step_dir / "status.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "failed", "message": f"Процесс шага завершился с кодом {p.returncode} без статуса"}


def read_result(step_dir: Path) -> dict | None:
    try:
        return json.loads((Path(step_dir) / "out" / "result.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
