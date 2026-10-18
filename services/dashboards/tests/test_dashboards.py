from fastapi.testclient import TestClient

from conftest import H, load_service


def mod_process(mod):
    from importlib import import_module
    return import_module("app.worker").process_one(mod.E, mod.CLIENTS, log=lambda *a: None)


def test_dashboards(calc_stack, tmp_path, monkeypatch):
    dm, da, aa, aa_mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={})
    assert mod_process(aa_mod)
    mod = load_service("dashboards", tmp_path, monkeypatch)
    for k, cl in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        mod.SVC[k] = mod.Svc(k, http=cl)
    db = TestClient(mod.app)
    lst = db.get("/dashboards", headers=H("viewer")).json()
    assert {d["id"] for d in lst} >= {"monitoring", "compare"} and not any(d["can_edit"] for d in lst)
    mon = db.get("/dashboards/monitoring", headers=H("mathematician")).json()
    assert mon["can_edit"] and len(mon["widgets"]) > 10
    f = {"water_body": "zhaysan", "species": "lesh"}
    for w in mon["widgets"]:
        r = db.post("/widgets/data", headers=H("viewer"), json={"source": w["source"], "filters": f,
                                                                 "options": {**w["options"], "raw": w["type"] == "table"}})
        assert r.status_code == 200, (w["id"], r.text)
        j = r.json()
        if w["source"].get("algorithm") in ("bayes_cohort", "forecast_pdu"):
            assert j.get("empty") and j["reason"] == "no_step", w["id"]
        else:
            assert not j.get("empty"), (w["id"], j)
    j = db.post("/widgets/data", headers=H(), json={"source": {"kind": "dataset", "dataset_type": "npc_pdu"}, "filters": f,
                                                   "options": {"x": "year", "y": "$species"}}).json()
    assert j["x"][0] == 2015 and j["series"][0]["values"][0] == 3597
    j = db.post("/widgets/data", headers=H(), json={"source": {"kind": "run", "algorithm": "stock_by_catch", "table": "yearly_stock"},
                                                   "filters": f, "options": {"x": "year", "y": "stock", "series": "gear",
                                                                             "filter": {"variant": "with_ages", "method": "on_stock"}}}).json()
    assert {s["name"] for s in j["series"]} == {"сеть", "невод", "сеть+невод"}
    # копия шаблона и права
    cp = db.post("/dashboards/monitoring/copy", headers=H("ichthyologist"), json={}).json()
    assert cp["can_edit"] and cp["visibility"] == "private"
    assert db.get(f"/dashboards/{cp['id']}", headers=H("viewer", uid="other")).status_code == 404
    body = {k: cp[k] for k in ("title_ru", "title_kk", "description", "filters", "tabs", "widgets")}
    body["visibility"] = "shared"
    body["widgets"] = body["widgets"][:3]
    assert db.put(f"/dashboards/{cp['id']}", headers=H("ichthyologist"), json=body).status_code == 200
    assert db.get(f"/dashboards/{cp['id']}", headers=H("viewer", uid="other")).status_code == 200
    assert db.put(f"/dashboards/{cp['id']}", headers=H("ichthyologist", uid="other2"), json=body).status_code == 403
    assert db.put("/dashboards/monitoring", headers=H("ichthyologist"), json=body).status_code == 403
    assert db.delete("/dashboards/monitoring", headers=H("admin")).status_code == 400
    bad = {**body, "widgets": [{"id": "x", "type": "pie", "source": {}}]}
    assert db.post("/dashboards", headers=H("ichthyologist"), json=bad).status_code == 422
