"""Фабрика FastAPI-приложения сервиса: /health, обработчики ошибок, настройки, журнал."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import settings as settings_mod
from .audit import AuditClient
from .errors import install_handlers

VERSION = "1.0.0"


def create_app(service: str, title: str, description: str = "") -> FastAPI:
    st = settings_mod.load(service)
    if st.jwt_secret == settings_mod.DEV_SECRET or st.service_token == "dev-service-token":
        print(f"[{service}] ВНИМАНИЕ: используются ключи разработки — задайте FISH_JWT_SECRET и FISH_SERVICE_TOKEN",
              flush=True)
    app = FastAPI(title=f"FishStocke — {title}", description=description, version=VERSION,
                  root_path_in_servers=False)
    app.state.settings = st
    app.state.audit = AuditClient(st) if service != "users" else None
    install_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/health", tags=["служебное"])
    def health():
        return {"service": service, "status": "ok", "version": VERSION, "data_dir": str(st.service_dir())}

    return app
