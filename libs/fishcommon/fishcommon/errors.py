"""Единый формат ошибок API: {"error": {"code", "message", "details"}}.

code — стабильный ключ (по нему фронтенд показывает перевод), message — текст на русском.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def not_found(what: str = "Объект") -> AppError:
    return AppError("not_found", f"{what} не найден", 404)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status,
                            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(x) for x in e.get("loc", [])[1:]), "message": e.get("msg")}
                   for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation", "message": "Проверьте заполнение полей", "details": details}})

    @app.exception_handler(KeyError)
    async def _key(_: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={"error": {
            "code": "not_found", "message": "Объект не найден", "details": str(exc)}})
