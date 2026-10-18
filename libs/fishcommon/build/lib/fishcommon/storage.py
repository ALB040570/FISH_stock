"""
Файловое хранилище v1.

Структура коллекции:
    <root>/<коллекция>/<id>/meta.json              — текущие метаданные объекта
    <root>/<коллекция>/<id>/versions/<n>/...       — неизменяемые версии (n = 1, 2, ...)
    <root>/<коллекция>/<id>/versions/<n>/version.json — метаданные версии (автор, дата, комментарий)

Запись: во временный файл в том же каталоге + os.replace (атомарно), под блокировкой объекта
(filelock), поэтому одновременная работа пользователей не портит файлы. Версии только добавляются.

Интерфейс Repository описывает операции так, чтобы на следующем этапе добавить реализацию
для PostgreSQL без изменения API сервисов.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

from filelock import FileLock
from ulid import ULID


def new_id() -> str:
    return str(ULID())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_default(o):
    if isinstance(o, (set, tuple)):
        return list(o)
    if isinstance(o, Path):
        return str(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "item"):  # numpy scalar
        return o.item()
    raise TypeError(f"не сериализуется в JSON: {type(o).__name__}")


def _clean_nan(o):
    """NaN/inf → None: в JSON пропуск остаётся пропуском, а не нулём."""
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean_nan(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean_nan(v) for v in o]
    return o


def dumps(data: Any) -> str:
    return json.dumps(_clean_nan(data), ensure_ascii=False, indent=1, default=_json_default)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_bytes(path, dumps(data).encode("utf-8"))


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


@contextmanager
def locked(path: Path, timeout: float = 30) -> Iterator[None]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + ".lock", timeout=timeout):
        yield


class Repository(Protocol):
    def create(self, meta: dict, actor: str | None = None) -> dict: ...
    def get(self, obj_id: str) -> dict | None: ...
    def list(self) -> list[dict]: ...
    def update(self, obj_id: str, changes: dict, actor: str | None = None) -> dict: ...
    def delete(self, obj_id: str) -> None: ...


class Collection:
    """Коллекция объектов с метаданными и неизменяемыми версиями (файловая реализация Repository)."""

    def __init__(self, root: Path, name: str):
        self.dir = Path(root) / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.name = name

    # ---------------------------------------------------------------- объекты
    def obj_dir(self, obj_id: str) -> Path:
        if not obj_id or "/" in obj_id or "\\" in obj_id or obj_id.startswith("."):
            raise ValueError("некорректный идентификатор")
        return self.dir / obj_id

    def _meta_path(self, obj_id: str) -> Path:
        return self.obj_dir(obj_id) / "meta.json"

    def create(self, meta: dict, actor: str | None = None, obj_id: str | None = None) -> dict:
        obj_id = obj_id or new_id()
        data = {**meta, "id": obj_id, "created_at": now_iso(), "created_by": actor,
                "updated_at": now_iso(), "updated_by": actor}
        with locked(self._meta_path(obj_id)):
            if self._meta_path(obj_id).exists():
                raise FileExistsError(obj_id)
            atomic_write_json(self._meta_path(obj_id), data)
        return data

    def get(self, obj_id: str) -> dict | None:
        try:
            return read_json(self._meta_path(obj_id))
        except ValueError:
            return None

    def exists(self, obj_id: str) -> bool:
        return self.get(obj_id) is not None

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.dir.iterdir()):
            if p.is_dir() and not p.name.startswith("."):
                m = read_json(p / "meta.json")
                if m is not None:
                    out.append(m)
        return out

    def update(self, obj_id: str, changes: dict, actor: str | None = None) -> dict:
        with locked(self._meta_path(obj_id)):
            cur = read_json(self._meta_path(obj_id))
            if cur is None:
                raise KeyError(obj_id)
            protected = {"id", "created_at", "created_by"}
            cur.update({k: v for k, v in changes.items() if k not in protected})
            cur["updated_at"] = now_iso()
            cur["updated_by"] = actor
            atomic_write_json(self._meta_path(obj_id), cur)
            return cur

    def delete(self, obj_id: str) -> None:
        """Логическое удаление (история сохраняется)."""
        self.update(obj_id, {"deleted": True})

    def purge(self, obj_id: str) -> None:
        shutil.rmtree(self.obj_dir(obj_id), ignore_errors=True)

    # ---------------------------------------------------------------- версии
    def versions_dir(self, obj_id: str) -> Path:
        return self.obj_dir(obj_id) / "versions"

    def version_dir(self, obj_id: str, n: int) -> Path:
        return self.versions_dir(obj_id) / str(int(n))

    def list_versions(self, obj_id: str) -> list[dict]:
        d = self.versions_dir(obj_id)
        if not d.exists():
            return []
        out = []
        for p in d.iterdir():
            if p.is_dir() and p.name.isdigit():
                info = read_json(p / "version.json") or {"n": int(p.name)}
                out.append(info)
        return sorted(out, key=lambda v: v["n"])

    def add_version(self, obj_id: str, files: dict[str, bytes], info: dict | None = None,
                    actor: str | None = None) -> dict:
        """Новая неизменяемая версия: files — {имя файла: содержимое}."""
        with locked(self._meta_path(obj_id)):
            existing = self.list_versions(obj_id)
            n = (existing[-1]["n"] + 1) if existing else 1
            vdir = self.version_dir(obj_id, n)
            tmp = vdir.with_name(f".{n}.tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            for name, content in files.items():
                target = tmp / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            vinfo = {**(info or {}), "n": n, "created_at": now_iso(), "created_by": actor}
            (tmp / "version.json").write_text(dumps(vinfo), encoding="utf-8")
            os.replace(tmp, vdir)
            cur = read_json(self._meta_path(obj_id)) or {}
            cur["current_version"] = n
            cur["updated_at"] = now_iso()
            cur["updated_by"] = actor
            atomic_write_json(self._meta_path(obj_id), cur)
            return vinfo

    def read_version_file(self, obj_id: str, n: int, name: str) -> bytes:
        return (self.version_dir(obj_id, n) / name).read_bytes()

    def version_info(self, obj_id: str, n: int) -> dict | None:
        return read_json(self.version_dir(obj_id, n) / "version.json")
