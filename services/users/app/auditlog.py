"""
Журнал действий: по файлу JSONL на день (audit/2026-10-18.jsonl). Записи только добавляются.
Хранение — 365 дней: файлы старше удаляются при записи (не чаще раза в сутки).
"""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fishcommon.storage import dumps, locked


class AuditLog:
    def __init__(self, root: Path, retention_days: int = 365):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self._last_purge: date | None = None
        self._mx = threading.Lock()

    def _file(self, day: str) -> Path:
        return self.root / f"{day}.jsonl"

    def write(self, events: list[dict]) -> None:
        by_day: dict[str, list[dict]] = {}
        for ev in events:
            ts = ev.get("ts") or datetime.now(timezone.utc).isoformat(timespec="seconds")
            ev["ts"] = ts
            by_day.setdefault(ts[:10], []).append(ev)
        with self._mx:
            for day, evs in by_day.items():
                path = self._file(day)
                with locked(path):
                    with open(path, "a", encoding="utf-8") as f:
                        for ev in evs:
                            f.write(dumps(ev).replace("\n", " ") + "\n")
            self.purge()

    def purge(self, today: date | None = None) -> int:
        today = today or datetime.now(timezone.utc).date()
        if self._last_purge == today:
            return 0
        self._last_purge = today
        limit = today - timedelta(days=self.retention_days)
        removed = 0
        for p in self.root.glob("*.jsonl"):
            try:
                d = date.fromisoformat(p.stem)
            except ValueError:
                continue
            if d < limit:
                p.unlink(missing_ok=True)
                removed += 1
        return removed

    def query(self, date_from=None, date_to=None, login=None, action=None, service=None, text=None) -> list[dict]:
        files = sorted(self.root.glob("*.jsonl"), reverse=True)
        out = []
        for p in files:
            day = p.stem
            if date_from and day < date_from[:10]:
                continue
            if date_to and day > date_to[:10]:
                continue
            with open(p, encoding="utf-8") as f:
                rows = [json.loads(x) for x in f if x.strip()]
            for r in reversed(rows):
                if login and (r.get("login") or "") != login.strip().lower():
                    continue
                if action and not (r.get("action") or "").startswith(action):
                    continue
                if service and r.get("service") != service:
                    continue
                if text and text.lower() not in json.dumps(r, ensure_ascii=False).lower():
                    continue
                out.append(r)
        return out
