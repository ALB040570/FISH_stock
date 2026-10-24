"""Что видят роли в дашбордах (docs/decisions.md, № 62).

Наблюдатель, оператор ввода данных и «Презентация» видят в мониторинге только «Исходные данные» и раздел
«ПДУ НПЦ (официальный)»; «Уловистость», «Запасы» и «ПДУ, рассчитанный в приложении» — только администратор,
математик и ихтиолог. Ограничение — в сервисе: шаблон без скрытых вкладок, данные скрытых представлений — 403.
"""
import importlib

from fastapi.testclient import TestClient

from conftest import H, load_service

FULL = ("admin", "mathematician", "ichthyologist")
LIMITED = ("viewer", "operator", "presenter")
F = {"water_body": "zhaysan", "species": "lesh"}


def mod_process(mod):
    from importlib import import_module
    return import_module("app.worker").process_one(mod.E, mod.CLIENTS, log=lambda *a: None)


def _post(db, role, w):
    return db.post("/widgets/data", headers=H(role), json={"source": w["source"], "filters": F,
                                                            "options": {**w.get("options", {}), "raw": w["type"] == "table"}})


def test_roles_monitoring(calc_stack, tmp_path, monkeypatch):
    dm, da, aa, aa_mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={})
    assert mod_process(aa_mod)
    mod = load_service("dashboards", tmp_path, monkeypatch)
    for k, cl in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        mod.SVC[k] = mod.Svc(k, http=cl)
    db = TestClient(mod.app)
    access = importlib.import_module(mod.__package__ + ".access")

    full = db.get("/dashboards/monitoring", headers=H("mathematician")).json()
    assert [t["code"] for t in full["tabs"]] == ["data", "catchability", "stock", "pdu"]
    # «Проверки модели» скрыты для всех (№ 65): нет раздела и слайдов, данные — 404
    assert [x["code"] for x in full["tabs"][2]["sections"]] == ["summary", "by_catch", "bayes"]
    assert not [w for w in full["widgets"] if w["id"].startswith("bc_")]
    for role in FULL + LIMITED:
        r = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "insight", "view": "bc_net"}, "filters": F, "options": {}})
        assert r.status_code == 404, role
        r = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "payload", "algorithm": "bayes_checks"}, "filters": F, "options": {}})
        assert r.status_code == 404, role
    # дашборд, сохранённый со старым разделом (копия шаблона), отдаётся без него
    mod.boards.update("monitoring", {"tabs": full["tabs"][:2] + [{**full["tabs"][2], "sections": full["tabs"][2]["sections"] + [
        {"code": "model_checks", "title_ru": "Проверки модели"}]}] + full["tabs"][3:],
        "widgets": full["widgets"] + [{"id": "bc_retro", "tab": "stock", "section": "model_checks", "type": "view",
                                       "source": {"kind": "insight", "view": "bc_retro"}, "options": {}}]}, actor="system")
    old = db.get("/dashboards/monitoring", headers=H("admin")).json()
    assert "model_checks" not in [x["code"] for x in old["tabs"][2]["sections"]] and "bc_retro" not in [w["id"] for w in old["widgets"]]
    mod.boards.update("monitoring", {"tabs": full["tabs"], "widgets": full["widgets"]}, actor="system")
    hidden = [w for w in full["widgets"] if w["tab"] in ("catchability", "stock") or (w["tab"], w.get("section")) == ("pdu", "app")]
    open_ = [w for w in full["widgets"] if w not in hidden]
    assert len(hidden) > 40 and {w["id"] for w in hidden} == access.hidden_widgets(full)

    # ---- администратор, математик, ихтиолог: всё
    for role in FULL:
        b = db.get("/dashboards/monitoring", headers=H(role)).json()
        assert [t["code"] for t in b["tabs"]] == ["data", "catchability", "stock", "pdu"] and len(b["widgets"]) == len(full["widgets"])
        assert [s["code"] for s in b["tabs"][3]["sections"]] == ["npc", "app"]
        for w in hidden[::7]:
            assert _post(db, role, w).status_code == 200, (role, w["id"])

    # ---- наблюдатель, оператор, «Презентация»: «Исходные данные» и «ПДУ НПЦ»
    for role in LIMITED:
        b = db.get("/dashboards/monitoring", headers=H(role)).json()
        assert [t["code"] for t in b["tabs"]] == ["data", "pdu"], role
        assert [s["code"] for s in b["tabs"][1]["sections"]] == ["npc"], role
        assert [t["sections"] for t in b["tabs"] if t["code"] == "data"] == [t["sections"] for t in full["tabs"] if t["code"] == "data"]
        assert {w["id"] for w in b["widgets"]} == {w["id"] for w in open_}, role
        for w in hidden:                                                     # прямой запрос данных скрытого слайда
            r = _post(db, role, w)
            assert r.status_code == 403 and r.json()["error"]["code"] == "auth.forbidden", (role, w["id"])
        for w in open_:
            assert _post(db, role, w).status_code == 200, (role, w["id"])
        for src in ({"kind": "payload", "algorithm": "seine_catchability"}, {"kind": "payload", "algorithm": "stock_by_catch"},
                    {"kind": "payload", "algorithm": "bayes_cohort"}, {"kind": "payload", "algorithm": "forecast_pdu"},
                    {"kind": "run", "algorithm": "stock_by_catch", "table": "yearly_stock"},
                    {"kind": "insight", "view": "st_trust"}, {"kind": "insight", "view": "fc_species"}):
            r = db.post("/widgets/data", headers=H(role), json={"source": src, "filters": F, "options": {}})
            assert r.status_code == 403, (role, src)
        # ПДУ НПЦ — открыт
        pl = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "payload", "algorithm": "pdu_by_age"}, "filters": F, "options": {}})
        assert pl.status_code == 200 and pl.json()["payload"]
        # «Что смотреть дальше» — без ссылок на скрытые слайды (pn_ages → st_ages)
        pa = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "insight", "view": "pn_ages"}, "filters": F, "options": {}}).json()
        assert "st_ages" not in [n["widget"] for n in pa["explain"]["next"]] and pa["explain"]["next"]
        ps = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "insight", "view": "pn_species"}, "filters": F, "options": {}}).json()
        assert ps["explain"]["how"] and not any("приложени" in x for x in ps["explain"]["how"] + ps["explain"]["now"])
        psk = db.post("/widgets/data", headers=H(role), json={"source": {"kind": "insight", "view": "pn_species"}, "filters": {**F, "lang": "kk"}, "options": {}}).json()
        assert len(psk["explain"]["how"]) == len(ps["explain"]["how"]) and not any("қосымша" in x.lower() for x in psk["explain"]["how"])

        # общий дашборд «Сравнение»: запас по уловам скрыт, ПДУ НПЦ — открыт
        cmp_ = db.get("/dashboards/compare", headers=H(role)).json()
        assert [w["id"] for w in cmp_["widgets"]] == ["cmp_pdu"], role
        lst = {d["id"]: d for d in db.get("/dashboards", headers=H(role)).json()}
        assert lst["compare"]["widgets"] == 1 and lst["monitoring"]["widgets"] == len(open_)
        assert "уловистость" not in lst["monitoring"]["description"].lower()

    pa = db.post("/widgets/data", headers=H("ichthyologist"), json={"source": {"kind": "insight", "view": "pn_ages"}, "filters": F, "options": {}}).json()
    assert "st_ages" in [n["widget"] for n in pa["explain"]["next"]]
    ps = db.post("/widgets/data", headers=H("ichthyologist"), json={"source": {"kind": "insight", "view": "pn_species"}, "filters": F, "options": {}}).json()
    assert any("рассчитанный в приложении" in x for x in ps["explain"]["how"])

    # ---- сводка водоёма: вместо ПДУ приложения — ПДУ НПЦ
    st = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "status"}, "filters": F, "options": {}}).json()
    assert st["runs"]["pdu"]["source"] == "npc" and st["runs"]["pdu"]["rows"]

    # ---- комментарии к скрытым слайдам: не видны и не открываются
    key = {"board": "monitoring", "widget": "st_trust", "water_body": "zhaysan", "species": "lesh"}
    assert db.post("/comments", headers=H("ichthyologist"), json={**key, "text": "Модель у леща выше уловов в 2,7 раза"}).status_code == 201
    assert db.post("/comments", headers=H("ichthyologist"), json={**key, "widget": "pn_tiles", "text": "Квота"}).status_code == 201
    q = {"board": "monitoring", "water_body": "zhaysan", "species": "lesh"}
    assert db.get("/comments/counts", headers=H("mathematician"), params=q).json() == {"st_trust": 1, "pn_tiles": 1}
    for role in LIMITED:
        assert db.get("/comments/counts", headers=H(role), params=q).json() == {"pn_tiles": 1}
        assert db.get("/comments", headers=H(role), params=key).status_code == 403
        assert db.post("/comments", headers=H(role), json={**key, "widget": "pn_tiles", "text": "x"}).status_code == 403
    assert len(db.get("/comments", headers=H("viewer"), params={**key, "widget": "pn_tiles"}).json()) == 1
