"""
Авторизация: JWT (HS256), выпускает сервис users, проверяют все сервисы общим секретом.
Права — по ролям (матрица в docs/plan.md, раздел 4).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, Request

from .errors import AppError

ROLES = ("admin", "ichthyologist", "mathematician", "operator", "viewer")

ROLE_TITLES = {
    "admin": "Администратор",
    "ichthyologist": "Ихтиолог-аналитик",
    "mathematician": "Математик",
    "operator": "Оператор ввода данных",
    "viewer": "Наблюдатель",
}

_ALL = set(ROLES)
_WORK = {"admin", "ichthyologist", "mathematician"}
# оператор ввода данных: вводит и правит наборы данных, остальное — только просмотр (docs/decisions.md, № 54)
_DATA = _WORK | {"operator"}

PERMISSIONS: dict[str, set[str]] = {
    "users.manage": {"admin"},
    "audit.view": {"admin"},
    "dict.view": _ALL,
    "dict.edit": _WORK,
    "data.view": _ALL,
    "data.edit": _DATA,
    "profile.view": _ALL,
    "profile.edit": _WORK,
    "algo.develop": {"admin", "mathematician"},
    "catalog.view": _ALL,
    "catalog.manage": {"admin", "mathematician"},
    "run.view": _ALL,
    "run.execute": _WORK,
    "dashboard.view": _ALL,
    "dashboard.edit": _WORK,
    "dashboard.template": {"admin", "mathematician"},
    "help.view": _ALL,
    "help.edit": {"admin", "mathematician"},
}


@dataclass
class User:
    id: str
    login: str
    name: str
    role: str
    token: str = ""
    is_service: bool = False

    def can(self, perm: str) -> bool:
        return self.is_service or self.role in PERMISSIONS.get(perm, set())

    def public(self) -> dict:
        return {"id": self.id, "login": self.login, "name": self.name, "role": self.role}


def issue_token(secret: str, user: dict, kind: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {"sub": user["id"], "login": user["login"], "name": user.get("name", ""),
               "role": user["role"], "typ": kind, "iat": now, "exp": now + ttl_seconds,
               "ver": user.get("token_version", 0)}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(secret: str, token: str, kind: str = "access") -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AppError("auth.expired", "Сеанс истёк, войдите снова", 401)
    except jwt.PyJWTError:
        raise AppError("auth.invalid", "Неверный токен авторизации", 401)
    if payload.get("typ") != kind:
        raise AppError("auth.invalid", "Неверный тип токена", 401)
    return payload


def _settings(request: Request):
    return request.app.state.settings


def current_user(request: Request, authorization: str | None = Header(default=None),
                 x_service_token: str | None = Header(default=None)) -> User:
    st = _settings(request)
    if x_service_token and x_service_token == st.service_token:
        return User(id="service", login="service", name="Служебный вызов", role="admin", is_service=True)
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.query_params.get("access_token")  # для ссылок на скачивание файлов
    if not token:
        raise AppError("auth.required", "Требуется вход в систему", 401)
    p = decode_token(st.jwt_secret, token)
    if p.get("role") not in ROLES:
        raise AppError("auth.invalid", "Неизвестная роль", 401)
    return User(id=p["sub"], login=p["login"], name=p.get("name", ""), role=p["role"], token=token)


def require(perm: str):
    def dep(user: User = Depends(current_user)) -> User:
        if not user.can(perm):
            raise AppError("auth.forbidden", "Недостаточно прав для этого действия", 403,
                           {"permission": perm, "role": user.role})
        return user
    return dep
