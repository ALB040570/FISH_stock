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


@pytest.fixture()
def data_stack(tmp_path, monkeypatch):
    """data-model + data-admin в одном процессе (data-admin читает справочники через TestClient)."""
    dm = TestClient(load_service("data_model", tmp_path, monkeypatch).app)
    da_mod = load_service("data_admin", tmp_path, monkeypatch)
    da_mod.DICT = da_mod.DictClient(http=dm)
    return dm, TestClient(da_mod.app), da_mod


def upload_samples(da, water_body="zhaysan", folder=None):
    """Загрузить контрольные данные Жайсана; вернуть {тип: таблица}."""
    folder = folder or (REPO / "samples" / "zhaysan")
    tables = {}
    for f in sorted(folder.glob("*.xlsx")):
        t = f.stem
        r = da.post("/upload", headers=H("ichthyologist"), data={"water_body": water_body, "dataset_type": t},
                    files={"file": (f.name, f.read_bytes())}).json()
        assert r["ok"], (t, r["errors"][:3])
        tables[t] = da.get(f"/datasets/{r['dataset']['id']}/data", headers=H()).json()["table"]
    return tables


def dict_maps(dm):
    sp = {r["values"]["code"]: r["values"]["name_ru"] for r in dm.get("/entities/species/records", headers=H()).json()}
    gk = {r["values"]["code"]: r["values"]["kind"] for r in dm.get("/entities/gears/records", headers=H()).json()}
    return sp, gk


@pytest.fixture()
def calc_stack(tmp_path, monkeypatch):
    """data-model + data-admin + algo-admin в одном процессе, данные Жайсана загружены."""
    dm = TestClient(load_service("data_model", tmp_path, monkeypatch).app)
    da_mod = load_service("data_admin", tmp_path, monkeypatch)
    da_mod.DICT = da_mod.DictClient(http=dm)
    da = TestClient(da_mod.app)
    upload_samples(da)
    aa_mod = load_service("algo_admin", tmp_path, monkeypatch)
    aa_mod.CLIENTS = aa_mod.Clients(aa_mod.ST, data_admin=da, data_model=dm)
    return dm, da, TestClient(aa_mod.app), aa_mod


@pytest.fixture()
def algo_stack(tmp_path, monkeypatch):
    """Все сервисы, кроме пользователей и дашбордов; algo-model обращается к остальным через TestClient."""
    dm, da, aa, aa_mod = None, None, None, None
    dm = TestClient(load_service("data_model", tmp_path, monkeypatch).app)
    da_mod = load_service("data_admin", tmp_path, monkeypatch)
    da_mod.DICT = da_mod.DictClient(http=dm)
    da = TestClient(da_mod.app)
    upload_samples(da)
    aa_mod = load_service("algo_admin", tmp_path, monkeypatch)
    aa_mod.CLIENTS = aa_mod.Clients(aa_mod.ST, data_admin=da, data_model=dm)
    aa = TestClient(aa_mod.app)
    am_mod = load_service("algo_model", tmp_path, monkeypatch)
    for k, c in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        am_mod.SVC[k] = am_mod.Svc(k, http=c)
    return dm, da, aa, TestClient(am_mod.app), am_mod
