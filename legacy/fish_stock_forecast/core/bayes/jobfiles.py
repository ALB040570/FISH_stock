"""Файлы фонового расчёта: состояние (JSON) и журнал. Общие для приложения и scripts.run_bayes."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .. import config as app_config


def jobs_dir() -> Path:
    d = app_config.RESULTS_DIR / "bayes_jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def status_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


def log_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.log"


def write_json(path: Path, data: dict) -> None:
    """Атомарная запись: сначала во временный файл, затем замена (несколько попыток для Windows)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for _ in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
    return None


def tail(path: Path, lines: int = 40, max_bytes: int = 32768) -> list[str]:
    if not path.exists():
        return []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        data = f.read().decode("utf-8", errors="replace")
    out = [ln.rstrip("\r") for ln in data.splitlines() if ln.strip()]
    return out[-lines:]
