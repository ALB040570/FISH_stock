"""
Исполнитель шага расчёта (запускается воркером в отдельном процессе):

    python -m fishrunner <каталог шага>

Каталог шага:
    context.json    — водоём, параметры, наборы данных, каталоги результатов предыдущих шагов
    package/        — распакованный пакет алгоритма (manifest.json + код), добавляется в sys.path
    out/            — результаты: result.json, файлы, state.pkl (для следующих шагов цепочки)
    status.json     — состояние: running | done | failed | cancelled, сообщение, ошибка
    progress.json   — ход выполнения (для интерфейса)
    log.txt         — журнал шага
    CANCEL          — появляется, если пользователь отменил расчёт

Контракт алгоритма: функция run(ctx) из точки входа manifest["entrypoint"] ("модуль:функция").
"""
from __future__ import annotations

import importlib
import json
import math
import os
import pickle
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(o):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return _clean(o.tolist())
        if isinstance(o, np.generic):
            o = o.item()
    except ImportError:
        pass
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def write_json(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(_clean(data), ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


class Cancelled(Exception):
    pass


class UserError(Exception):
    """Ошибка, понятная пользователю (нет данных, неверный параметр): показывается без трассировки."""


class Context:
    def __init__(self, step_dir: Path):
        self.dir = Path(step_dir)
        c = json.loads((self.dir / "context.json").read_text(encoding="utf-8"))
        self.raw = c
        self.run_id = c.get("run_id")
        self.step = c.get("step")
        self.water_body = c["water_body"]
        self.params = c.get("params", {})
        self.species_names = c.get("species_names", {})
        self.gear_kinds = c.get("gear_kinds", {})
        self.inputs = {k: Path(v) for k, v in c.get("inputs", {}).items()}
        self.dataset_sources = c.get("dataset_sources", {})
        tables_path = c.get("tables_path")
        self.tables = json.loads(Path(tables_path).read_text(encoding="utf-8")) if tables_path else {}
        self.out_dir = self.dir / "out"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.result = {"tables": {}, "files": [], "payload": None, "metrics": {}, "notes": []}
        self._log = open(self.dir / "log.txt", "a", encoding="utf-8")
        self._last_progress = 0.0

    # ---- журнал и ход выполнения
    def log(self, *msg) -> None:
        line = " ".join(str(m) for m in msg)
        self._log.write(f"{datetime.now().strftime('%H:%M:%S')}  {line}\n")
        self._log.flush()

    def progress(self, fraction: float | None = None, **info) -> None:
        self.check_cancel()
        now = time.time()
        if now - self._last_progress < 0.5 and fraction not in (0, 1):
            return
        self._last_progress = now
        write_json(self.dir / "progress.json", {"fraction": fraction, "ts": _now(), **info})

    def check_cancel(self) -> None:
        if (self.dir / "CANCEL").exists():
            raise Cancelled()

    # ---- результаты
    def add_table(self, code: str, title: str, columns: list[dict], rows: list[dict], description: str = "") -> None:
        """columns: [{"code", "title", "unit"?, "type"?: number|integer|string}]"""
        self.result["tables"][code] = {"title": title, "description": description, "columns": columns, "rows": rows}

    def add_frame(self, code: str, title: str, df, units: dict | None = None, description: str = "") -> None:
        """Таблица из pandas.DataFrame (заголовки столбцов — названия)."""
        import pandas as pd
        cols, mapping = [], {}
        for i, name in enumerate(df.columns):
            key = f"c{i}"
            mapping[name] = key
            kind = "number" if pd.api.types.is_numeric_dtype(df[name]) else "string"
            if pd.api.types.is_bool_dtype(df[name]):
                kind = "boolean"
            cols.append({"code": key, "title": str(name), "type": kind, "unit": (units or {}).get(name)})
        rows = [{mapping[k]: v for k, v in r.items()} for r in df.to_dict(orient="records")]
        self.add_table(code, title, cols, rows, description)

    def add_file(self, name: str, title: str, fmt: str | None = None) -> Path:
        p = self.out_dir / name
        self.result["files"].append({"name": name, "title": title, "format": fmt or p.suffix.lstrip(".")})
        return p

    def set_payload(self, payload: dict) -> None:
        self.result["payload"] = payload

    def metric(self, key: str, value, title: str | None = None, unit: str | None = None) -> None:
        self.result["metrics"][key] = {"value": value, "title": title or key, "unit": unit}

    def note(self, text: str) -> None:
        self.result["notes"].append(text)

    # ---- передача состояния по цепочке
    def save_state(self, obj) -> None:
        with open(self.out_dir / "state.pkl", "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_state(self, step_code: str):
        d = self.inputs.get(step_code)
        if d is None:
            return None
        p = d / "state.pkl"
        if not p.exists():
            raise UserError(f"Нет результатов шага «{step_code}» для продолжения цепочки")
        with open(p, "rb") as f:
            return pickle.load(f)

    def input_dir(self, step_code: str) -> Path | None:
        return self.inputs.get(step_code)


def _apply_fixed_early(manifest: dict, params: dict) -> None:
    """Неизменяемые параметры с именами настроек fishcore.config применяются ДО загрузки кода алгоритма:
    часть функций ядра берёт их значениями аргументов по умолчанию при импорте."""
    if not (Path(sys.path[0]) / "fishcore" / "config.py").exists():
        return
    cfg = importlib.import_module("fishcore.config")
    for p in manifest.get("parameters", []):
        code = p["code"]
        if p.get("category") == "fixed" and hasattr(cfg, code) and params.get(code) is not None:
            cur = getattr(cfg, code)
            setattr(cfg, code, params[code] if isinstance(cur, str) else type(cur)(params[code]))


def main(step_dir: str) -> int:
    step_dir = Path(step_dir)
    status = {"status": "running", "started_at": _now(), "pid": os.getpid()}
    write_json(step_dir / "status.json", status)
    pkg = step_dir / "package"
    sys.path.insert(0, str(pkg))
    ctx = None
    try:
        manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
        mod_name, func_name = manifest.get("entrypoint", "algorithm:run").split(":")
        ctx = Context(step_dir)
        _apply_fixed_early(manifest, ctx.params)
        ctx.log(f"алгоритм {manifest['code']} {manifest['version']}, водоём {ctx.water_body}")
        func = getattr(importlib.import_module(mod_name), func_name)
        t0 = time.time()
        ret = func(ctx)
        if isinstance(ret, dict):
            ctx.result.setdefault("summary", ret)
        ctx.result["seconds"] = round(time.time() - t0, 2)
        write_json(ctx.out_dir / "result.json", ctx.result)
        ctx.progress(1.0)
        status.update(status="done", finished_at=_now(), seconds=ctx.result["seconds"])
        ctx.log(f"готово за {ctx.result['seconds']} с")
        code = 0
    except Cancelled:
        status.update(status="cancelled", finished_at=_now(), message="Расчёт отменён пользователем")
        code = 3
    except UserError as e:
        status.update(status="failed", finished_at=_now(), message=str(e))
        if ctx:
            ctx.log(f"ошибка: {e}")
        code = 2
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        status.update(status="failed", finished_at=_now(), message=f"{type(e).__name__}: {e}", traceback=tb)
        if ctx:
            ctx.log(tb)
        code = 1
    write_json(step_dir / "status.json", status)
    return code


if __name__ == "__main__":
    # алгоритмы делают «from fishrunner import UserError»: это должен быть тот же модуль, что выполняется
    sys.modules.setdefault("fishrunner", sys.modules["__main__"])
    sys.exit(main(sys.argv[1]))
