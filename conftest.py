"""Общие фикстуры тестов: каждый сервис импортируется как пакет app из своего каталога."""
import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "libs" / "fishcommon"))


def load_service(name: str, tmp_path, monkeypatch, **env):
    monkeypatch.setenv("FISH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FISH_URL_USERS", "http://127.0.0.1:9")  # журнал уходит в локальную очередь
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sdir = str(REPO / "services" / name)
    for m in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, sdir)
    try:
        mod = importlib.import_module("app.main")
    finally:
        sys.path.remove(sdir)
    return mod


def token(role="admin", uid="u1", login="tester"):
    from fishcommon.auth import issue_token
    from fishcommon.settings import DEV_SECRET
    return issue_token(DEV_SECRET, {"id": uid, "login": login, "name": login, "role": role}, "access", 3600)


def H(role="admin", **kw):
    return {"Authorization": f"Bearer {token(role, **kw)}"}


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    def make(name, **env):
        return TestClient(load_service(name, tmp_path, monkeypatch, **env).app)
    return make
