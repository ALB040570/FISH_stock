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
