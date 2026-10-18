import io
import zipfile

from conftest import H


def mod_process(mod):
    """Выполнить один запуск из очереди (как воркер)."""
    from importlib import import_module
    return import_module("app.worker").process_one(mod.E, mod.CLIENTS, log=lambda *a: None)


def test_catalog_and_profiles(calc_stack):
    dm, da, aa, mod = calc_stack
    cat = aa.get("/catalog", headers=H("viewer")).json()
    assert [a["code"] for a in cat] == ["seine_catchability", "stock_by_catch", "pdu_by_age", "bayes_cohort", "forecast_pdu"]
    assert all(a["latest"] == "1.0.0" for a in cat)
    files = aa.get("/catalog/bayes_cohort/versions/1.0.0/files", headers=H("viewer")).json()
    assert any(f["path"] == "fishcore/bayes/dynamics.py" for f in files)
    p = aa.get("/profiles/bayes_cohort/zhaysan", headers=H("viewer")).json()
    assert set(p["profile"]["values"]["species_profiles"]) == {"lesh", "sudak", "okun", "plotva", "shuka", "sazan", "karas", "yaz"}
    # копия профиля для другого водоёма, проверка значений
    r = aa.post("/profiles/bayes_cohort/balkhash/copy-from/zhaysan", headers=H("ichthyologist")); assert r.status_code == 200
    vals = r.json()["profile"]["values"]
    vals["species_profiles"]["lesh"]["beta_lower"] = 5
    r = aa.put("/profiles/bayes_cohort/balkhash", headers=H("mathematician"), json={"values": vals})
    assert r.status_code == 422 and "β" in str(r.json())
    # отключение версии — только математик/админ
    assert aa.post("/catalog/forecast_pdu/versions/1.0.0/disable", headers=H("ichthyologist")).status_code == 403
    assert aa.post("/catalog/forecast_pdu/versions/1.0.0/disable", headers=H("mathematician")).status_code == 200
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan"})
    assert c.status_code == 422 and "нет включённых версий" in str(c.json())
    aa.post("/catalog/forecast_pdu/versions/1.0.0/enable", headers=H("admin"))


def test_run_stock_chain(calc_stack):
    dm, da, aa, mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    chk = aa.post(f"/calculations/{c['id']}/check", headers=H("viewer"), json={}).json()
    assert chk["ok"], chk["errors"]
    assert set(chk["plan"]["datasets"]) >= {"catches", "age_samples", "npc_pdu"}
    # неизменяемый параметр задать нельзя
    r = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={"params": {"pdu_by_age": {"PDU_CAP": 0.5}}})
    assert r.status_code == 422 and "неизменяемый" in str(r.json())
    assert aa.post(f"/calculations/{c['id']}/run", headers=H("viewer"), json={}).status_code == 403
    r = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={}).json()
    assert r["status"] == "queued"
    assert mod_process(mod)
    run = aa.get(f"/runs/{r['id']}", headers=H("viewer")).json()
    assert run["status"] == "done", run.get("message")
    assert [s["status"] for s in run["steps"]] == ["done", "done", "done"]
    res = aa.get(f"/runs/{r['id']}/steps/2/result", headers=H("viewer")).json()
    assert res["tables"]["pdu_by_age"]["rows"]
    f = aa.get(f"/runs/{r['id']}/steps/2/files/pdu_by_age.xlsx", headers=H("viewer")); assert f.status_code == 200
    assert aa.get(f"/runs/{r['id']}/steps/2/files/state.pkl", headers=H("viewer")).status_code == 404
    z = zipfile.ZipFile(io.BytesIO(aa.get(f"/runs/{r['id']}/export.zip", headers=H()).content))
    assert any(n.endswith("zhaysan_pdu_pieces_3d.nc") for n in z.namelist())
    # основной запуск и сводка для карты
    assert aa.post(f"/runs/{r['id']}/main", headers=H("ichthyologist")).status_code == 200
    st = aa.get("/water-bodies/status", headers=H("viewer")).json()["zhaysan"]
    assert st["main_run"]["run_id"] == r["id"]
    mon = aa.get("/water-bodies/zhaysan/monitoring-run", headers=H("viewer")).json()
    assert mon["is_main"] and mon["run"]["id"] == r["id"]
    # отчёты
    d = aa.get(f"/runs/{r['id']}/report.docx", headers=H("viewer")); assert d.status_code == 200 and d.content[:2] == b"PK"
    p = aa.get(f"/runs/{r['id']}/report.pdf", headers=H("viewer")); assert p.status_code == 200 and p.content[:4] == b"%PDF"
    # повтор с шага 3 по базовому запуску: шаги 1–2 берутся из него
    r2 = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"),
                 json={"from_step": "pdu_by_age", "base_run": r["id"]}).json()
    assert mod_process(mod)
    run2 = aa.get(f"/runs/{r2['id']}", headers=H()).json()
    assert [s["status"] for s in run2["steps"]] == ["reused", "reused", "done"]
    a = aa.get(f"/runs/{r['id']}/steps/2/result", headers=H()).json()["tables"]["pdu_by_age"]["rows"]
    b = aa.get(f"/runs/{r2['id']}/steps/2/result", headers=H()).json()["tables"]["pdu_by_age"]["rows"]
    assert a == b


def test_cancel_and_errors(calc_stack):
    dm, da, aa, mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    r = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={}).json()
    x = aa.post(f"/runs/{r['id']}/cancel", headers=H("ichthyologist")).json()
    assert x["status"] == "cancelled"
    assert not mod_process(mod)
    # водоём без данных: понятная ошибка до запуска
    c2 = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "balkhash"}).json()
    chk = aa.post(f"/calculations/{c2['id']}/check", headers=H()).json()
    assert not chk["ok"] and any("не загружен набор" in e for e in chk["errors"])
    assert any("профиля" in e for e in chk["errors"])
