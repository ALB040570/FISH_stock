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


def test_catch_by_age_formula20(calc_stack, tmp_path, monkeypatch):
    """Улов по ловам и возрастам: Y_ijd = Y_id · q_ij(t_d), q — доли пробы года (+1 для j ≤ m1)."""
    dm, da, aa, aa_mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={})
    assert mod_process(aa_mod)
    mod = load_service("dashboards", tmp_path, monkeypatch)
    for k, cl in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        mod.SVC[k] = mod.Svc(k, http=cl)
    db = TestClient(mod.app)
    f = {"water_body": "zhaysan", "species": "sudak"}
    src = {"kind": "insight", "view": "age_catch_hauls"}
    j = db.post("/widgets/data", headers=H("viewer"), json={"source": src, "filters": f,
                                                             "options": {"gear_kind": "net", "year": 2019}}).json()
    assert j["year"] == 2019 and j["meta"]["run_id"] and j["help"] == "method-catch-age"
    row = j["rows"][0]
    e = db.post("/widgets/drill", headers=H("viewer"), json={"source": src, "filters": f, "options": {"gear_kind": "net"},
                                                            "where": {"haul": row["haul"]}, "dataset_type": "catch_by_age"}).json()
    assert "Y_ijd = Y_id · q_ij" in e["formula"]
    assert abs(sum(r["Yj"] for r in e["rows"]) - row["total"]) < 2e-3      # Y_ijd в таблице — 4 знака
    # независимая проверка долей по возрастной пробе 2019 года
    ages = da.get(f"/datasets/{da.get('/datasets', params={'water_body': 'zhaysan', 'dataset_type': 'age_samples'}, headers=H()).json()[0]['id']}/data",
                  headers=H()).json()["table"]["rows"]
    props = da.get(f"/datasets/{da.get('/datasets', params={'water_body': 'zhaysan', 'dataset_type': 'species_props'}, headers=H()).json()[0]['id']}/data",
                   headers=H()).json()["table"]["rows"]
    m1 = next(p["m1"] for p in props if p["species"] == "sudak")
    n = {r["age"]: (r.get("sudak") or 0) for r in ages if r["year"] == 2019}
    sm = {a: v + (1 if a <= m1 else 0) for a, v in n.items()}
    tot = sum(sm.values())
    for r in e["rows"]:
        assert abs(r["q"] - sm[r["age"]] / tot) < 1e-6
        assert abs(r["Yj"] - row["total"] * sm[r["age"]] / tot) < 1e-3
    y = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "insight", "view": "age_catch_year"},
                                                             "filters": f, "options": {"gear_kind": "net"}}).json()
    r19 = next(r for r in y["rows"] if r["year"] == 2019)
    assert abs(sum(v for k, v in r19.items() if k.startswith("a")) - sum(r["total"] for r in j["rows"])) < 0.5
