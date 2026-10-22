"""
Кэш результатов этапов 1–3 на диске (results/cache) и журнал времени расчёта.

При запуске сервера этапы 1–3 не пересчитываются, если с прошлого расчёта не изменились:
    исходные данные (data_catch/*.py), старые файлы data_stock/*.nc (кроме байесовских),
    код расчёта (core/*.py) и настройки (core/config.py).
Кнопки «Пересчитать» на страницах всегда считают заново и обновляют кэш.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import config

CACHE_VERSION = 1
_CORE_DIR = Path(__file__).resolve().parent


def cache_dir() -> Path:
    d = config.RESULTS_DIR / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sig(paths) -> list:
    out = []
    for p in sorted(paths):
        try:
            st = p.stat()
            out.append([p.name, st.st_size, st.st_mtime_ns])
        except OSError:
            pass
    return out


def fingerprint(*extra) -> str:
    """Отпечаток всего, от чего зависят этапы 1–3 (без байесовской части)."""
    old = [p for p in config.OLD_DATA_STOCK_DIR.glob("*.nc") if "_bayes_" not in p.name] \
        if config.OLD_DATA_STOCK_DIR.exists() else []
    data = {
        "v": CACHE_VERSION,
        "source": str(config.SOURCE_PROJECT_DIR),
        "data_catch": _sig(config.DATA_CATCH_DIR.glob("*.py")) if config.DATA_CATCH_DIR.exists() else [],
        "data_stock": _sig(old),
        "code": _sig(_CORE_DIR.glob("*.py")),
        "extra": [str(e) for e in extra],
        # сглаживание возрастных проб меняют из командной строки (run_bayes --age-old), а не в коде
        "age": [config.AGE_PSEUDOCOUNT_TOTAL, config.AGE_POOL_MIN_SAMPLE, config.AGE_POOL_NEIGHBOURS],
    }
    return hashlib.sha1(json.dumps(data, ensure_ascii=False).encode("utf-8")).hexdigest()


def load(name: str, fp: str):
    """Объект из кэша или None (нет файла, другой отпечаток, ошибка чтения)."""
    path = cache_dir() / f"{name}.pkl"
    if not path.exists():
        return None
    try:
        with timed(f"чтение кэша {name}"):
            with open(path, "rb") as f:
                data = pickle.load(f)
    except Exception as e:  # noqa: BLE001 — повреждённый или устаревший кэш просто пересчитываем
        log(f"кэш {name} не прочитан ({type(e).__name__}: {e}) — пересчёт")
        return None
    if not isinstance(data, dict) or data.get("fp") != fp:
        log(f"кэш {name} устарел (изменились данные или код) — пересчёт")
        return None
    return data.get("obj")


def save(name: str, fp: str, obj) -> None:
    path = cache_dir() / f"{name}.pkl"
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "wb") as f:
            pickle.dump({"fp": fp, "obj": obj, "saved_at": datetime.now().isoformat(timespec="seconds")},
                        f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    except Exception as e:  # noqa: BLE001 — без кэша всё работает, только медленнее
        log(f"кэш {name} не записан: {type(e).__name__}: {e}")
        try:
            tmp.unlink()
        except OSError:
            pass


def log(msg: str) -> None:
    """Строка в консоль сервера (окно run.bat)."""
    print(f"{datetime.now().strftime('%H:%M:%S')}  {msg}", flush=True)


@contextmanager
def timed(what: str, min_seconds: float = 0.0):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        if dt >= min_seconds:
            seconds = f"{dt:.1f}".replace(".", ",")
            log(f"{what}: {seconds} с")
