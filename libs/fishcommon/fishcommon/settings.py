"""Настройки сервисов из переменных окружения (секреты — только из окружения / .env, не из Git)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    service: str
    data_dir: Path
    jwt_secret: str
    service_token: str
    access_minutes: int
    refresh_days: int
    urls: dict[str, str]

    def service_dir(self, name: str | None = None) -> Path:
        d = self.data_dir / (name or self.service)
        d.mkdir(parents=True, exist_ok=True)
        return d


DEV_SECRET = "dev-only-secret-change-me-0123456789abcdef"

SERVICE_PORTS = {
    "users": 8001, "data_model": 8002, "data_admin": 8003,
    "algo_model": 8004, "algo_admin": 8005, "dashboards": 8006, "help": 8007,
}


def load(service: str) -> Settings:
    data_dir = Path(_env("FISH_DATA_DIR", str(Path.cwd() / "data"))).resolve()
    urls = {}
    for name, port in SERVICE_PORTS.items():
        urls[name] = _env(f"FISH_URL_{name.upper()}", f"http://127.0.0.1:{port}")
    return Settings(
        service=service,
        data_dir=data_dir,
        jwt_secret=_env("FISH_JWT_SECRET", DEV_SECRET),
        service_token=_env("FISH_SERVICE_TOKEN", "dev-service-token"),
        access_minutes=int(_env("FISH_ACCESS_MINUTES", "60")),
        refresh_days=int(_env("FISH_REFRESH_DAYS", "14")),
        urls=urls,
    )
