"""
Сервис 1. Администрирование пользователей: вход, роли, блокировка, журнал действий,
профиль пользователя (имя, почта, должность, организация, фото).
"""
from __future__ import annotations

import base64
import io
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from fishcommon.app import create_app
from fishcommon.auth import ROLE_TITLES, ROLES, User, current_user, decode_token, issue_token, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import Collection, atomic_write_bytes, atomic_write_json, read_json

from .auditlog import AuditLog

app = create_app("users", "Администрирование пользователей",
                 "Пользователи, вход (JWT), роли, блокировка, журнал действий.")
ST = app.state.settings
ROOT = ST.service_dir()
users = Collection(ROOT, "users")
audit = AuditLog(ROOT / "audit")
ph = PasswordHasher()

MAX_FAILED = 10


PUBLIC_FIELDS = ("id", "login", "name", "email", "position", "organization", "role", "blocked", "created_at",
                 "updated_at", "last_login_at", "must_change_password", "avatar_ver")


def _public(u: dict) -> dict:
    return {k: u.get(k) for k in PUBLIC_FIELDS}


def _find_login(login: str) -> dict | None:
    login = login.strip().lower()
    for u in users.list():
        if u.get("login") == login and not u.get("deleted"):
            return u
    return None


def _event(user, action, object_type="", object_id="", details=None, ok=True):
    audit.write([{"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "service": "users",
                  "action": action, "object_type": object_type, "object_id": object_id, "ok": ok,
                  "user_id": getattr(user, "id", None) if not isinstance(user, dict) else user.get("id"),
                  "login": getattr(user, "login", None) if not isinstance(user, dict) else user.get("login"),
                  "details": details}])


def bootstrap() -> None:
    """Первый администратор: логин/пароль из окружения, иначе — случайный пароль в файле."""
    if any(not u.get("deleted") for u in users.list()):
        return
    login = os.environ.get("FISH_ADMIN_LOGIN", "admin").strip().lower()
    password = os.environ.get("FISH_ADMIN_PASSWORD") or ""
    generated = not password
    if generated:
        password = secrets.token_urlsafe(10)
        atomic_write_json(ROOT / "INITIAL_ADMIN_PASSWORD.json",
                          {"login": login, "password": password,
                           "note": "Смените пароль после первого входа и удалите этот файл."})
    users.create({"login": login, "name": "Администратор", "email": "", "role": "admin",
                  "password_hash": ph.hash(password), "blocked": False, "token_version": 0,
                  "failed_logins": 0, "must_change_password": generated}, actor="system")
    print(f"[users] создан администратор '{login}'" + (" (пароль в INITIAL_ADMIN_PASSWORD.json)" if generated else ""))


bootstrap()


# ------------------------------------------------------------------ вход
class LoginIn(BaseModel):
    login: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


def _tokens(u: dict) -> dict:
    return {
        "access_token": issue_token(ST.jwt_secret, u, "access", ST.access_minutes * 60),
        "refresh_token": issue_token(ST.jwt_secret, u, "refresh", ST.refresh_days * 86400),
        "token_type": "bearer", "expires_in": ST.access_minutes * 60, "user": _public(u),
    }


@app.post("/auth/login", tags=["вход"])
def login(body: LoginIn, request: Request):
    u = _find_login(body.login)
    ip = request.client.host if request.client else None
    if u is None:
        _event({"login": body.login.strip().lower()}, "auth.login", ok=False, details={"reason": "unknown", "ip": ip})
        raise AppError("auth.bad_credentials", "Неверный логин или пароль", 401)
    if u.get("blocked"):
        _event(u, "auth.login", ok=False, details={"reason": "blocked", "ip": ip})
        raise AppError("auth.blocked", "Учётная запись заблокирована. Обратитесь к администратору", 403)
    try:
        ph.verify(u["password_hash"], body.password)
    except VerifyMismatchError:
        failed = int(u.get("failed_logins", 0)) + 1
        changes = {"failed_logins": failed}
        if failed >= MAX_FAILED:
            changes.update(blocked=True, token_version=int(u.get("token_version", 0)) + 1)
        users.update(u["id"], changes, actor="system")
        _event(u, "auth.login", ok=False, details={"reason": "password", "failed": failed, "ip": ip})
        if failed >= MAX_FAILED:
            raise AppError("auth.blocked", "Слишком много неудачных попыток — учётная запись заблокирована", 403)
        raise AppError("auth.bad_credentials", "Неверный логин или пароль", 401)
    u = users.update(u["id"], {"failed_logins": 0,
                               "last_login_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                     actor=u["id"])
    _event(u, "auth.login", details={"ip": ip})
    return _tokens(u)


@app.post("/auth/refresh", tags=["вход"])
def refresh(body: RefreshIn):
    p = decode_token(ST.jwt_secret, body.refresh_token, "refresh")
    u = users.get(p["sub"])
    if not u or u.get("deleted") or u.get("blocked") or int(u.get("token_version", 0)) != int(p.get("ver", 0)):
        raise AppError("auth.invalid", "Сеанс недействителен, войдите снова", 401)
    return _tokens(u)


@app.get("/auth/me", tags=["вход"])
def me(user: User = Depends(current_user)):
    u = users.get(user.id)
    if not u:
        raise not_found("Пользователь")
    return _public(u)


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


@app.post("/auth/password", tags=["вход"])
def change_password(body: PasswordIn, user: User = Depends(current_user)):
    u = users.get(user.id)
    try:
        ph.verify(u["password_hash"], body.old_password)
    except VerifyMismatchError:
        raise AppError("auth.bad_password", "Текущий пароль указан неверно", 400)
    users.update(u["id"], {"password_hash": ph.hash(body.new_password), "must_change_password": False,
                           "token_version": int(u.get("token_version", 0)) + 1}, actor=user.id)
    _event(user, "user.password_change", "user", user.id)
    return _tokens(users.get(user.id))


# ------------------------------------------------------------------ профиль
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class ProfileFields(BaseModel):
    """Поля профиля, которые может менять сам пользователь (и администратор). Логин и роль сюда не входят."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=200)
    position: str | None = Field(None, max_length=200)
    organization: str | None = Field(None, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("Имя не может быть пустым")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v is None:
            return v
        v = v.strip()
        if v and not EMAIL_RE.match(v):
            raise ValueError("Неверный адрес почты")
        return v

    @field_validator("position")
    @classmethod
    def _position(cls, v):
        return None if v is None else " ".join(v.split())

    @field_validator("organization")
    @classmethod
    def _org(cls, v):
        """Код записи справочника «Организации» (сервис моделирования данных); пустая строка — не указана."""
        if v is None:
            return v
        v = v.strip()
        if v and not ORG_RE.match(v):
            raise ValueError("Неверный код организации")
        return v


def _profile_changes(body: ProfileFields) -> dict:
    return body.model_dump(exclude_unset=True, exclude_none=True)


@app.patch("/auth/me", tags=["профиль"])
def update_me(body: ProfileFields, user: User = Depends(current_user)):
    """Свой профиль: имя, почта, должность, организация. Возвращает новые токены (имя входит в токен)."""
    u = users.get(user.id)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    changes = _profile_changes(body)
    if changes:
        u = users.update(u["id"], changes, actor=user.id)
        _event(user, "user.profile_update", "user", user.id, changes)
    return _tokens(u)


AVATAR_MAX = 512 * 1024
AVATAR_TYPES = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "image/webp": b"RIFF"}


class AvatarIn(BaseModel):
    data: str = Field(description="data:image/jpeg;base64,... (квадрат, уменьшенный в браузере)")


def _avatar_path(uid: str):
    return users.obj_dir(uid) / "avatar.bin"


def _decode_avatar(data: str) -> tuple[str, bytes]:
    m = re.match(r"^data:(image/[a-z]+);base64,(.+)$", data.strip(), re.S)
    if not m or m.group(1) not in AVATAR_TYPES:
        raise AppError("users.avatar_type", "Фото должно быть в формате JPEG, PNG или WebP", 400)
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception:
        raise AppError("users.avatar_type", "Файл фото повреждён", 400)
    if len(raw) > AVATAR_MAX:
        raise AppError("users.avatar_size", "Фото слишком большое (не более 512 КБ)", 400)
    ctype = m.group(1)
    if not raw.startswith(AVATAR_TYPES[ctype]) or (ctype == "image/webp" and raw[8:12] != b"WEBP"):
        raise AppError("users.avatar_type", "Файл не похож на изображение", 400)
    return ctype, raw


def _set_avatar(uid: str, ctype: str | None, raw: bytes | None, actor: str) -> dict:
    path = _avatar_path(uid)
    if raw is None:
        path.unlink(missing_ok=True)
        return users.update(uid, {"avatar_ver": None, "avatar_type": None}, actor=actor)
    atomic_write_bytes(path, raw)
    ver = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return users.update(uid, {"avatar_ver": ver, "avatar_type": ctype}, actor=actor)


@app.put("/auth/me/avatar", tags=["профиль"])
def put_my_avatar(body: AvatarIn, user: User = Depends(current_user)):
    ctype, raw = _decode_avatar(body.data)
    u = _set_avatar(user.id, ctype, raw, user.id)
    _event(user, "user.avatar_set", "user", user.id, {"bytes": len(raw)})
    return _public(u)


@app.delete("/auth/me/avatar", tags=["профиль"])
def delete_my_avatar(user: User = Depends(current_user)):
    u = _set_avatar(user.id, None, None, user.id)
    _event(user, "user.avatar_delete", "user", user.id)
    return _public(u)


@app.get("/users/{uid}/avatar", tags=["профиль"])
def get_avatar(uid: str, user: User = Depends(current_user)):
    """Фото пользователя — для любого вошедшего (аватары коллег). Адрес меняется вместе с avatar_ver."""
    u = users.get(uid)
    path = _avatar_path(uid) if u else None
    if not u or u.get("deleted") or not u.get("avatar_ver") or not path.exists():
        raise not_found("Фото")
    return Response(path.read_bytes(), media_type=u.get("avatar_type") or "image/jpeg",
                    headers={"Cache-Control": "private, max-age=31536000"})


# ------------------------------------------------------------------ пользователи
@app.get("/roles", tags=["пользователи"])
def roles():
    return [{"code": r, "title": ROLE_TITLES[r]} for r in ROLES]


class UserIn(ProfileFields):
    login: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")
    name: str = Field(min_length=1, max_length=200)
    role: str
    password: str = Field(min_length=8)


class UserPatch(ProfileFields):
    """Правка администратором: поля профиля и роль. Логин не меняется (по нему ведётся журнал)."""
    role: str | None = None


@app.get("/users", tags=["пользователи"])
def list_users(user: User = Depends(require("users.manage"))):
    return [_public(u) for u in users.list() if not u.get("deleted")]


@app.post("/users", tags=["пользователи"], status_code=201)
def create_user(body: UserIn, user: User = Depends(require("users.manage"))):
    if body.role not in ROLES:
        raise AppError("users.bad_role", "Неизвестная роль", 400)
    if _find_login(body.login):
        raise AppError("users.exists", "Пользователь с таким логином уже есть", 409)
    u = users.create({"login": body.login.strip().lower(), "name": body.name, "email": body.email or "",
                      "position": body.position or "", "organization": body.organization or "",
                      "role": body.role, "password_hash": ph.hash(body.password), "blocked": False,
                      "token_version": 0, "failed_logins": 0, "must_change_password": True}, actor=user.id)
    _event(user, "user.create", "user", u["id"], {"login": u["login"], "role": u["role"]})
    return _public(u)


@app.patch("/users/{uid}", tags=["пользователи"])
def update_user(uid: str, body: UserPatch, user: User = Depends(require("users.manage"))):
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("role") == u["role"]:
        changes.pop("role")
    if "role" in changes:
        if changes["role"] not in ROLES:
            raise AppError("users.bad_role", "Неизвестная роль", 400)
        if u["role"] == "admin" and changes["role"] != "admin" and _admins_left(exclude=uid) == 0:
            raise AppError("users.last_admin", "Нельзя снять роль с последнего администратора", 400)
        changes["token_version"] = int(u.get("token_version", 0)) + 1
    u = users.update(uid, changes, actor=user.id)
    _event(user, "user.update", "user", uid, {k: v for k, v in changes.items() if k != "token_version"})
    return _public(u)


def _admins_left(exclude: str) -> int:
    return sum(1 for x in users.list() if x["role"] == "admin" and not x.get("blocked")
               and not x.get("deleted") and x["id"] != exclude)


@app.post("/users/{uid}/block", tags=["пользователи"])
def block_user(uid: str, user: User = Depends(require("users.manage"))):
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    if uid == user.id:
        raise AppError("users.self_block", "Нельзя заблокировать самого себя", 400)
    if u["role"] == "admin" and _admins_left(exclude=uid) == 0:
        raise AppError("users.last_admin", "Нельзя заблокировать последнего администратора", 400)
    u = users.update(uid, {"blocked": True, "token_version": int(u.get("token_version", 0)) + 1}, actor=user.id)
    _event(user, "user.block", "user", uid, {"login": u["login"]})
    return _public(u)


@app.post("/users/{uid}/unblock", tags=["пользователи"])
def unblock_user(uid: str, user: User = Depends(require("users.manage"))):
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    u = users.update(uid, {"blocked": False, "failed_logins": 0}, actor=user.id)
    _event(user, "user.unblock", "user", uid, {"login": u["login"]})
    return _public(u)


class ResetIn(BaseModel):
    password: str = Field(min_length=8)


@app.post("/users/{uid}/reset-password", tags=["пользователи"])
def reset_password(uid: str, body: ResetIn, user: User = Depends(require("users.manage"))):
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    users.update(uid, {"password_hash": ph.hash(body.password), "must_change_password": True,
                       "token_version": int(u.get("token_version", 0)) + 1, "failed_logins": 0}, actor=user.id)
    _event(user, "user.reset_password", "user", uid, {"login": u["login"]})
    return {"ok": True}


@app.delete("/users/{uid}/avatar", tags=["пользователи"])
def delete_user_avatar(uid: str, user: User = Depends(require("users.manage"))):
    """Администратор убирает фото пользователя (например, неподходящее)."""
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    u = _set_avatar(uid, None, None, user.id)
    _event(user, "user.avatar_delete", "user", uid, {"login": u["login"]})
    return _public(u)


@app.delete("/users/{uid}", tags=["пользователи"])
def delete_user(uid: str, user: User = Depends(require("users.manage"))):
    u = users.get(uid)
    if not u or u.get("deleted"):
        raise not_found("Пользователь")
    if uid == user.id:
        raise AppError("users.self_delete", "Нельзя удалить самого себя", 400)
    if u["role"] == "admin" and _admins_left(exclude=uid) == 0:
        raise AppError("users.last_admin", "Нельзя удалить последнего администратора", 400)
    _avatar_path(uid).unlink(missing_ok=True)  # фото — личные данные, при удалении не храним
    users.update(uid, {"deleted": True, "blocked": True, "avatar_ver": None, "avatar_type": None,
                       "token_version": int(u.get("token_version", 0)) + 1}, actor=user.id)
    _event(user, "user.delete", "user", uid, {"login": u["login"]})
    return {"ok": True}


@app.get("/users/directory", tags=["пользователи"])
def directory(user: User = Depends(current_user)):
    """Имена пользователей для подписей «автор» в других экранах (без служебных полей)."""
    return {u["id"]: u.get("name") or u["login"] for u in users.list()}


@app.get("/users/people", tags=["пользователи"])
def people(user: User = Depends(current_user)):
    """Подписи и аватары авторов (комментарии и др.): актуальное имя, фото, должность, организация.
    Удалённые — только имя (их записи остаются подписанными)."""
    out = {}
    for u in users.list():
        name = u.get("name") or u["login"]
        if u.get("deleted"):
            out[u["id"]] = {"name": name, "deleted": True}
        else:
            out[u["id"]] = {"name": name, "avatar_ver": u.get("avatar_ver"), "position": u.get("position") or "",
                            "organization": u.get("organization") or ""}
    return out


# ------------------------------------------------------------------ журнал
class AuditIn(BaseModel):
    events: list[dict]


@app.post("/internal/audit", tags=["журнал"], include_in_schema=False)
def internal_audit(body: AuditIn, user: User = Depends(current_user)):
    if not user.is_service:
        raise AppError("auth.forbidden", "Только для сервисов", 403)
    audit.write(body.events)
    return {"ok": True, "count": len(body.events)}


def _audit_query(date_from, date_to, login, action, service, text):
    return audit.query(date_from=date_from, date_to=date_to, login=login, action=action,
                       service=service, text=text)


@app.get("/audit", tags=["журнал"])
def audit_list(date_from: str | None = None, date_to: str | None = None, login: str | None = None,
               action: str | None = None, service: str | None = None, text: str | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
               user: User = Depends(require("audit.view"))):
    rows = _audit_query(date_from, date_to, login, action, service, text)
    return {"total": len(rows), "items": rows[offset:offset + limit], "retention_days": audit.retention_days}


@app.get("/audit/export.xlsx", tags=["журнал"])
def audit_export(date_from: str | None = None, date_to: str | None = None, login: str | None = None,
                 action: str | None = None, service: str | None = None, text: str | None = None,
                 user: User = Depends(require("audit.view"))):
    from openpyxl import Workbook
    rows = _audit_query(date_from, date_to, login, action, service, text)
    wb = Workbook()
    ws = wb.active
    ws.title = "Журнал"
    head = ["Время (UTC)", "Пользователь", "Сервис", "Действие", "Объект", "Идентификатор", "Успешно", "Подробности"]
    ws.append(head)
    for r in rows:
        ws.append([r.get("ts"), r.get("login"), r.get("service"), r.get("action"), r.get("object_type"),
                   r.get("object_id"), "да" if r.get("ok", True) else "нет",
                   str(r.get("details")) if r.get("details") else ""])
    for col, w in zip("ABCDEFGH", (22, 18, 12, 26, 16, 30, 9, 60)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    _event(user, "audit.export", details={"rows": len(rows)})
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="audit.xlsx"'})
