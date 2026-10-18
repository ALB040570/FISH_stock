"""
Клиент журнала действий: события отправляются в сервис users (/internal/audit).
Если users недоступен, событие пишется в локальную очередь <data>/<сервис>/audit_spool.jsonl
и досылается при следующем успешном вызове — журнал не теряет записи.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx

from .storage import dumps, now_iso

_lock = threading.Lock()


class AuditClient:
    def __init__(self, settings):
        self.settings = settings
        self.url = settings.urls["users"].rstrip("/") + "/internal/audit"
        self.spool = settings.service_dir() / "audit_spool.jsonl"

    def _post(self, events: list[dict]) -> bool:
        try:
            r = httpx.post(self.url, json={"events": events}, timeout=3,
                           headers={"X-Service-Token": self.settings.service_token})
            return r.status_code < 300
        except httpx.HTTPError:
            return False

    def _flush_spool(self) -> None:
        if not self.spool.exists():
            return
        lines = [json.loads(x) for x in self.spool.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines and self._post(lines):
            self.spool.unlink(missing_ok=True)

    def log(self, user, action: str, object_type: str = "", object_id: str = "", details=None,
            ok: bool = True) -> None:
        ev = {
            "ts": now_iso(), "service": self.settings.service, "action": action,
            "object_type": object_type, "object_id": object_id, "ok": ok,
            "user_id": getattr(user, "id", None), "login": getattr(user, "login", None),
            "details": details,
        }
        with _lock:
            self._flush_spool()
            if not self._post([ev]):
                with open(self.spool, "a", encoding="utf-8") as f:
                    f.write(dumps(ev).replace("\n", " ") + "\n")


class LocalAudit:
    """Журнал внутри сервиса users (без HTTP)."""

    def __init__(self, writer):
        self.writer = writer

    def log(self, user, action, object_type="", object_id="", details=None, ok=True):
        self.writer([{"ts": now_iso(), "service": "users", "action": action, "object_type": object_type,
                      "object_id": object_id, "ok": ok, "user_id": getattr(user, "id", None),
                      "login": getattr(user, "login", None), "details": details}])
