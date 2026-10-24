import importlib, os, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FISH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FISH_ADMIN_PASSWORD", "admin-pass-1")
    sys.path.insert(0, str(ROOT))
    for m in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    main = importlib.import_module("app.main")
    yield TestClient(main.app)
    sys.path.remove(str(ROOT))


def login(c, l, p):
    r = c.post("/auth/login", json={"login": l, "password": p})
    return r


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_flow(client):
    c = client
    assert login(c, "admin", "wrong").status_code == 401
    r = login(c, "admin", "admin-pass-1"); assert r.status_code == 200
    adm = r.json()["access_token"]
    r = c.post("/users", headers=h(adm), json={"login": "ivan", "name": "Иван", "role": "ichthyologist", "password": "secret-123"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    assert c.post("/users", headers=h(adm), json={"login": "ivan", "name": "x", "role": "viewer", "password": "secret-123"}).status_code == 409
    iv = login(c, "ivan", "secret-123").json()
    # нет прав на пользователей и журнал
    assert c.get("/users", headers=h(iv["access_token"])).status_code == 403
    assert c.get("/audit", headers=h(iv["access_token"])).status_code == 403
    # блокировка
    assert c.post(f"/users/{uid}/block", headers=h(adm)).status_code == 200
    assert login(c, "ivan", "secret-123").status_code == 403
    assert c.post("/auth/refresh", json={"refresh_token": iv["refresh_token"]}).status_code == 401
    assert c.post(f"/users/{uid}/unblock", headers=h(adm)).status_code == 200
    assert login(c, "ivan", "secret-123").status_code == 200
    # последний админ
    me = c.get("/auth/me", headers=h(adm)).json()
    assert c.post(f"/users/{me['id']}/block", headers=h(adm)).status_code == 400
    assert c.patch(f"/users/{me['id']}", headers=h(adm), json={"role": "viewer"}).status_code == 400
    # журнал
    j = c.get("/audit", headers=h(adm)).json()
    actions = [x["action"] for x in j["items"]]
    assert "user.create" in actions and "user.block" in actions and "auth.login" in actions
    assert any(not x["ok"] for x in j["items"])
    r = c.get("/audit/export.xlsx", headers=h(adm)); assert r.status_code == 200 and r.content[:2] == b"PK"
    # служебный приём событий
    r = c.post("/internal/audit", headers={"X-Service-Token": "dev-service-token"}, json={"events": [{"action": "data.upload", "service": "data_admin", "login": "ivan"}]})
    assert r.status_code == 200
    assert c.get("/audit?service=data_admin", headers=h(adm)).json()["total"] == 1
    assert c.post("/internal/audit", headers=h(adm), json={"events": []}).status_code == 403
    assert c.get("/users", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_retention(tmp_path):
    sys.path.insert(0, str(ROOT))
    from app.auditlog import AuditLog
    from datetime import date
    a = AuditLog(tmp_path)
    a.write([{"ts": "2025-01-01T00:00:00+00:00", "action": "x"}, {"ts": "2026-10-01T00:00:00+00:00", "action": "y"}])
    # старая запись удалена при записи (хранение 365 дней)
    assert [r["action"] for r in a.query()] == ["y"]


# ------------------------------------------------------------------ правка, удаление, профиль, фото (24.10.2026)
import base64

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100   # синтетические байты для теста (не настоящее фото)


def _setup(c):
    adm = login(c, "admin", "admin-pass-1").json()["access_token"]
    r = c.post("/users", headers=h(adm), json={"login": "petr", "name": "Петр Ошибкин", "role": "ichthyologist",
                                                "password": "secret-123", "position": "ихтиолог"})
    assert r.status_code == 201, r.text
    return adm, r.json()["id"]


def test_admin_edits_and_deletes(client):
    c = client
    adm, uid = _setup(c)
    assert c.get("/users", headers=h(adm)).json()[1]["position"] == "ихтиолог"
    # исправить имя, почту, должность, организацию
    r = c.patch(f"/users/{uid}", headers=h(adm), json={"name": "  Пётр   Иванов ", "email": "p@ex.kz",
                                                       "position": "ведущий н. с.", "organization": "org1"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["name"], j["email"], j["position"], j["organization"]) == ("Пётр Иванов", "p@ex.kz", "ведущий н. с.", "org1")
    # логин не меняется, пустое имя и неверная почта — ошибка
    assert c.patch(f"/users/{uid}", headers=h(adm), json={"login": "other"}).status_code == 422
    assert c.patch(f"/users/{uid}", headers=h(adm), json={"name": "   "}).status_code == 422
    assert c.patch(f"/users/{uid}", headers=h(adm), json={"email": "not-mail"}).status_code == 422
    # та же роль — не выход из сеансов; другая — смена версии токена
    tok = login(c, "petr", "secret-123").json()["access_token"]
    assert c.patch(f"/users/{uid}", headers=h(adm), json={"role": "ichthyologist"}).status_code == 200
    assert c.get("/auth/me", headers=h(tok)).status_code == 200
    # удаление: исчезает из списка, вход невозможен, логин можно выдать заново, имя в справочнике авторов остаётся
    assert c.delete(f"/users/{uid}", headers=h(adm)).status_code == 200
    assert all(u["id"] != uid for u in c.get("/users", headers=h(adm)).json())
    assert login(c, "petr", "secret-123").status_code == 401
    assert c.get("/users/directory", headers=h(adm)).json()[uid] == "Пётр Иванов"
    assert c.delete(f"/users/{uid}", headers=h(adm)).status_code == 404
    assert c.post("/users", headers=h(adm), json={"login": "petr", "name": "Петр", "role": "viewer",
                                                  "password": "secret-123"}).status_code == 201
    # нельзя удалить себя и последнего администратора
    me = c.get("/auth/me", headers=h(adm)).json()["id"]
    assert c.delete(f"/users/{me}", headers=h(adm)).status_code == 400


def test_self_profile(client):
    c = client
    adm, uid = _setup(c)
    j = login(c, "petr", "secret-123").json()
    tok = j["access_token"]
    r = c.patch("/auth/me", headers=h(tok), json={"name": "Пётр Иванов", "position": "зав. лабораторией",
                                                   "organization": "org2", "email": ""})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["user"]["name"] == "Пётр Иванов" and j["user"]["organization"] == "org2"
    # новый токен содержит новое имя и действует; старый тоже действует (сеанс не сброшен)
    assert c.get("/auth/me", headers=h(j["access_token"])).json()["position"] == "зав. лабораторией"
    assert c.get("/auth/me", headers=h(tok)).status_code == 200
    # роль и логин сам себе не меняет, чужого пользователя править не может
    assert c.patch("/auth/me", headers=h(tok), json={"role": "admin"}).status_code == 422
    assert c.patch("/auth/me", headers=h(tok), json={"login": "x"}).status_code == 422
    assert c.get("/auth/me", headers=h(tok)).json()["role"] == "ichthyologist"
    me_adm = c.get("/auth/me", headers=h(adm)).json()["id"]
    assert c.patch(f"/users/{me_adm}", headers=h(tok), json={"name": "x"}).status_code == 403
    # в журнале
    rows = c.get("/audit", headers=h(adm), params={"action": "user.profile_update"}).json()["items"]
    assert rows and rows[0]["login"] == "petr"


def test_avatar(client):
    c = client
    adm, uid = _setup(c)
    tok = login(c, "petr", "secret-123").json()["access_token"]
    assert c.get(f"/users/{uid}/avatar", headers=h(tok)).status_code == 404
    data = "data:image/jpeg;base64," + base64.b64encode(JPEG).decode()
    r = c.put("/auth/me/avatar", headers=h(tok), json={"data": data})
    assert r.status_code == 200, r.text
    assert r.json()["avatar_ver"]
    # коллега видит фото
    r = c.get(f"/users/{uid}/avatar", headers=h(adm))
    assert r.status_code == 200 and r.content == JPEG and r.headers["content-type"] == "image/jpeg"
    assert c.get(f"/users/{uid}/avatar").status_code == 401
    # не изображение, не тот формат, слишком большое
    bad = "data:image/jpeg;base64," + base64.b64encode(b"hello world").decode()
    assert c.put("/auth/me/avatar", headers=h(tok), json={"data": bad}).status_code == 400
    assert c.put("/auth/me/avatar", headers=h(tok), json={"data": "data:image/svg+xml;base64,PHN2Zz4="}).status_code == 400
    big = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 600_000).decode()
    assert c.put("/auth/me/avatar", headers=h(tok), json={"data": big}).status_code == 400
    # администратор убирает фото; пользователь — своё
    assert c.delete(f"/users/{uid}/avatar", headers=h(adm)).json()["avatar_ver"] is None
    assert c.get(f"/users/{uid}/avatar", headers=h(adm)).status_code == 404
    c.put("/auth/me/avatar", headers=h(tok), json={"data": data})
    assert c.delete("/auth/me/avatar", headers=h(tok)).json()["avatar_ver"] is None
    # при удалении пользователя фото удаляется
    c.put("/auth/me/avatar", headers=h(tok), json={"data": data})
    c.delete(f"/users/{uid}", headers=h(adm))
    assert c.get(f"/users/{uid}/avatar", headers=h(adm)).status_code == 404


def test_people(client):
    c = client
    adm, uid = _setup(c)
    tok = login(c, "petr", "secret-123").json()["access_token"]
    p = c.get("/users/people", headers=h(tok)).json()
    assert p[uid] == {"name": "Петр Ошибкин", "avatar_ver": None, "position": "ихтиолог", "organization": ""}
    c.patch(f"/users/{uid}", headers=h(adm), json={"name": "Пётр Иванов"})
    assert c.get("/users/people", headers=h(adm)).json()[uid]["name"] == "Пётр Иванов"
    c.delete(f"/users/{uid}", headers=h(adm))
    assert c.get("/users/people", headers=h(adm)).json()[uid] == {"name": "Пётр Иванов", "deleted": True}
    assert c.get("/users/people").status_code == 401


def test_presenter_role(client):
    """Роль «Презентация» (№ 62): администратор создаёт учётную запись, пользователь входит с этой ролью."""
    c = client
    adm = login(c, "admin", "admin-pass-1").json()["access_token"]
    roles = {r["code"]: r["title"] for r in c.get("/roles", headers=h(adm)).json()}
    assert roles["presenter"] == "Презентация"
    r = c.post("/users", headers=h(adm), json={"login": "show", "name": "Показ", "role": "presenter", "password": "secret-123"})
    assert r.status_code == 201, r.text
    j = login(c, "show", "secret-123").json()
    assert j["user"]["role"] == "presenter"
    assert c.get("/users", headers=h(j["access_token"])).status_code == 403
