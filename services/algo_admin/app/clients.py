"""Вызовы других сервисов (служебный токен)."""
from __future__ import annotations

import httpx

from fishcommon.errors import AppError


class Svc:
    def __init__(self, settings, name: str, http=None):
        self.settings = settings
        self.name = name
        self.http = http or httpx.Client(base_url=settings.urls[name], timeout=60)

    def get(self, path, **params):
        try:
            r = self.http.get(path, params=params or None, headers={"X-Service-Token": self.settings.service_token})
        except httpx.HTTPError:
            raise AppError("service.unavailable", f"Сервис «{self.name}» недоступен, повторите позже", 503)
        if r.status_code == 404:
            raise AppError("not_found", f"Не найдено ({self.name}: {path})", 404)
        if r.status_code >= 300:
            raise AppError("service.error", f"Ошибка сервиса «{self.name}» ({r.status_code})", 502)
        return r.json()


class Clients:
    def __init__(self, settings, data_admin=None, data_model=None):
        self.data_admin = Svc(settings, "data_admin", data_admin)
        self.data_model = Svc(settings, "data_model", data_model)

    def species_names(self) -> dict:
        return {r["values"]["code"]: r["values"]["name_ru"] for r in self.data_model.get("/entities/species/records")}

    def gear_kinds(self) -> dict:
        return {r["values"]["code"]: r["values"]["kind"] for r in self.data_model.get("/entities/gears/records")}

    def water_bodies(self) -> dict:
        return {r["values"]["code"]: r["values"] for r in self.data_model.get("/entities/water_bodies/records")}

    def current_datasets(self, water_body: str) -> dict:
        return self.data_admin.get(f"/bundle/{water_body}")

    def table(self, dataset_id: str, version: int) -> dict:
        return self.data_admin.get(f"/datasets/{dataset_id}/data", version=version)["table"]
