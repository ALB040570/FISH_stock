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
    assert [a["code"] for a in cat] == ["seine_catchability", "stock_by_catch", "pdu_by_age", "bayes_cohort", "forecast_pdu", "bayes_checks"]
    latest = {a["code"]: a["latest"] for a in cat}
    assert latest == {"seine_catchability": "2.0.0", "stock_by_catch": "2.0.0", "pdu_by_age": "2.0.0",
                      "bayes_cohort": "2.0.2", "forecast_pdu": "2.0.0", "bayes_checks": "2.0.2"}
    files = aa.get("/catalog/bayes_cohort/versions/2.0.2/files", headers=H("viewer")).json()
    assert any(f["path"] == "fishcore/bayes/dynamics.py" for f in files)
    p = aa.get("/profiles/bayes_cohort/zhaysan", headers=H("viewer")).json()
    assert set(p["profile"]["values"]["species_profiles"]) == {"lesh", "sudak", "okun", "plotva", "shuka", "sazan", "karas", "yaz"}
    # «Презентация» (№ 62): каталог — названия, версии, описания; без кода, пакета и параметров водоёмов
    assert len(aa.get("/catalog", headers=H("presenter")).json()) == 6
    for url in ("/catalog/bayes_cohort/versions/2.0.2/files", "/catalog/bayes_cohort/versions/2.0.2/package.zip",
                "/profiles/bayes_cohort/zhaysan"):
        assert aa.get(url, headers=H("presenter")).status_code == 403, url
    # копия профиля для другого водоёма, проверка значений
    r = aa.post("/profiles/bayes_cohort/balkhash/copy-from/zhaysan", headers=H("ichthyologist")); assert r.status_code == 200
    vals = r.json()["profile"]["values"]
    vals["species_profiles"]["lesh"]["beta_lower"] = 5
    r = aa.put("/profiles/bayes_cohort/balkhash", headers=H("mathematician"), json={"values": vals})
    assert r.status_code == 422 and "β" in str(r.json())
    # отключение версии — только математик/админ
    assert aa.post("/catalog/forecast_pdu/versions/2.0.0/disable", headers=H("ichthyologist")).status_code == 403
    assert aa.post("/catalog/forecast_pdu/versions/2.0.0/disable", headers=H("mathematician")).status_code == 200
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan"})
    assert c.status_code == 422 and "нет включённых версий" in str(c.json())
    aa.post("/catalog/forecast_pdu/versions/2.0.0/enable", headers=H("admin"))


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
    res = aa.get(f"/runs/{r['id']}/steps/2/result", headers=H("ichthyologist")).json()
    assert res["tables"]["pdu_by_age"]["rows"]
    f = aa.get(f"/runs/{r['id']}/steps/2/files/pdu_by_age.xlsx", headers=H("ichthyologist")); assert f.status_code == 200
    assert aa.get(f"/runs/{r['id']}/steps/2/files/state.pkl", headers=H("ichthyologist")).status_code == 404
    # результаты, файлы, журнал, выгрузка и отчёты шагов — только с правом results.view (№ 62);
    # список и статусы шагов видны всем
    for role in ("viewer", "operator", "presenter"):
        assert aa.get(f"/runs/{r['id']}", headers=H(role)).status_code == 200
        for url in (f"/runs/{r['id']}/steps/2/result", f"/runs/{r['id']}/steps/0/log", f"/runs/{r['id']}/steps/2/files/pdu_by_age.xlsx",
                    f"/runs/{r['id']}/export.zip", f"/runs/{r['id']}/report.pdf"):
            assert aa.get(url, headers=H(role)).status_code == 403, (role, url)
    z = zipfile.ZipFile(io.BytesIO(aa.get(f"/runs/{r['id']}/export.zip", headers=H()).content))
    assert any(n.endswith("zhaysan_pdu_pieces_3d.nc") for n in z.namelist())
    # основной запуск и сводка для карты
    assert aa.post(f"/runs/{r['id']}/main", headers=H("ichthyologist")).status_code == 200
    st = aa.get("/water-bodies/status", headers=H("viewer")).json()["zhaysan"]
    assert st["main_run"]["run_id"] == r["id"]
    # ПДУ на карте: без права на результаты — ПДУ НПЦ последнего года (из шага 3), не ПДУ приложения
    assert st["pdu"]["source"] == "npc" and st["pdu"] == st["pdu_npc"] and st["pdu"]["rows"][0]["pdu_t"] > 0
    assert aa.get("/water-bodies/status", headers=H("ichthyologist")).json()["zhaysan"]["pdu"] is None  # прогноза нет
    mon = aa.get("/water-bodies/zhaysan/monitoring-run", headers=H("viewer")).json()
    assert mon["is_main"] and mon["run"]["id"] == r["id"]
    # отчёты
    d = aa.get(f"/runs/{r['id']}/report.docx", headers=H("ichthyologist")); assert d.status_code == 200 and d.content[:2] == b"PK"
    p = aa.get(f"/runs/{r['id']}/report.pdf", headers=H("ichthyologist")); assert p.status_code == 200 and p.content[:4] == b"%PDF"
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


def test_classification(calc_stack):
    """Тип модели и метод расчёта запаса (классификатор ТОФИ) — в каталоге; значения параметров — в профиле."""
    dm, da, aa, mod = calc_stack
    cl = aa.get("/classifiers", headers=H("viewer")).json()
    assert [m["code"] for m in cl["model_types"]] == ["deterministic", "stochastic"]
    assert [m["code"] for m in cl["stock_methods"]] == ["area", "balance", "model"]
    assert cl["param_values"][0]["tofi_code"] == "_FV_1124"
    cat = {a["code"]: a["classification"] for a in aa.get("/catalog", headers=H("viewer")).json()}
    assert cat["bayes_cohort"] == {"model_type": "stochastic", "stock_methods": ["model"]}
    assert cat["stock_by_catch"]["stock_methods"] == ["area", "balance"]
    body = {"model_type": "deterministic", "stock_methods": ["balance"]}
    assert aa.put("/catalog/pdu_by_age/classification", headers=H("ichthyologist"), json=body).status_code == 403
    assert aa.put("/catalog/pdu_by_age/classification", headers=H("mathematician"),
                  json={"model_type": "x", "stock_methods": ["kushnarenko"]}).status_code == 422
    assert aa.put("/catalog/pdu_by_age/classification", headers=H("mathematician"), json=body).status_code == 200
    assert aa.get("/catalog/pdu_by_age", headers=H()).json()["classification"] == body
    p = aa.get("/profiles/bayes_cohort/zhaysan", headers=H("viewer")).json()
    kinds = {r["key"]: r.get("value_kind") for r in p["schema"]}
    assert kinds["beta_mu"] == "mu" and kinds["beta_sigma"] == "sigma"
    assert kinds["beta_lower"] == "lower" and kinds["x0_hi"] == "upper" and kinds["s_clip_lo"] == "lower"
    assert kinds.get("draws") is None


def test_reference_change_migration(tmp_path, monkeypatch):
    """Переход на эталон 22.10.2026: прежние эталонные версии удаляются, профили водоёмов получают новые значения
    по умолчанию с сохранением изменений пользователей; закреплённая в расчёте удалённая версия заменяется новой."""
    import json
    from conftest import load_service
    mod = load_service("algo_admin", tmp_path, monkeypatch)
    E = mod.E
    prev = json.loads((mod.build.PACKAGES / "bayes_cohort" / "previous_defaults_1.0.json").read_text(encoding="utf-8"))
    # как на сервере до обновления: эталонная версия 1.0.3 и профиль со значениями прежнего эталона
    man = json.loads(json.dumps(E.manifest("seine_catchability", "2.0.0")))
    man["version"] = "1.0.3"
    E.publish(man, {"manifest.json": json.dumps(man).encode()}, actor="system", source="builtin")
    old_vals = json.loads(json.dumps(prev))
    old_vals["lesh"]["draws"] = 3000                       # изменено пользователем
    E.save_profile("bayes_cohort", "balkhash", {"species_profiles": old_vals}, "u1", "до обновления")
    E.profiles.update(E.profile_id("bayes_cohort", "balkhash"), {"migrated_to": None}, actor="system")  # профиль версии 1.x
    E.seed_builtin()
    assert [v["version"] for v in E.versions("seine_catchability")] == ["2.0.0"]
    lesh = E.get_profile("bayes_cohort", "balkhash")["values"]["species_profiles"]["lesh"]
    assert lesh["draws"] == 3000 and lesh["catch_mode"] == "cap" and lesh["likelihood"] == "delta"
    assert "press_mu" not in lesh and lesh["target_accept"] == 0.95
    E.seed_builtin()                                       # второй запуск ничего не меняет
    assert len(E.profiles.list_versions(E.profile_id("bayes_cohort", "balkhash"))) == 2


def test_recover_stale_after_restart(tmp_path, monkeypatch):
    """Запуск, оборванный перезапуском воркера, помечается прерванным, а не висит «выполняется»."""
    import os
    from conftest import load_service
    mod = load_service("algo_admin", tmp_path, monkeypatch)
    from importlib import import_module
    eng_mod = import_module("app.engine")
    E = eng_mod.Engine(tmp_path / "recover")
    me = eng_mod.worker_name()
    host = me.split(":")[0]
    mk = lambda w, st="running": E.runs.create({"status": st, "worker": w, "water_body": "zhaysan", "steps": []})
    old_container = mk("3f2a9c1b7d4e:1:aaaa")             # контейнер пересоздан: другое имя хоста
    same_pid_new_boot = mk(f"{host}:{os.getpid()}:bbbb")    # тот же номер процесса, прежний запуск процесса
    mine = mk(me)                                           # выполняется этим процессом
    queued = mk("x:1:c", st="queued")
    # без признака «единственный воркер» — только этот хост
    assert E.recover_stale(host, sole=False) == 1
    assert E.runs.get(same_pid_new_boot["id"])["status"] == "failed"
    assert E.runs.get(old_container["id"])["status"] == "running"
    # единственный воркер каталога данных (Docker, run_local) — все прежние «выполняется»
    monkeypatch.setenv("FISH_WORKER_SOLE", "1")
    assert E.recover_stale(host) == 1
    r = E.runs.get(old_container["id"])
    assert r["status"] == "failed" and "перезапуск" in r["message"]
    assert E.runs.get(mine["id"])["status"] == "running"
    assert E.runs.get(queued["id"])["status"] == "queued"


def test_fix_version_keeps_previous_and_profiles(tmp_path, monkeypatch):
    """Исправление 2.0.1 поверх 2.0.0 (как на сервере 24.10): 2.0.0 остаётся в каталоге, профили водоёмов
    повторно не переносятся (значения пользователей не трогаются, новых версий профиля нет)."""
    import json
    from conftest import load_service
    mod = load_service("algo_admin", tmp_path, monkeypatch)
    E = mod.E
    files = E.package_files("bayes_cohort", "2.0.2")
    man = json.loads(files["manifest.json"])
    man["version"] = "2.0.0"
    old = dict(files, **{"manifest.json": json.dumps(man).encode(), "algorithm.py": files["algorithm.py"] + b"\n# 2.0.0\n"})
    E.publish(man, old, actor="system", source="builtin")
    pid = E.profile_id("bayes_cohort", "zhaysan")
    E.profiles.update(pid, {"migrated_to": "defaults 2.0.0"}, actor="system")   # перенесён при переходе на 2.0.0
    vals = E.get_profile("bayes_cohort", "zhaysan")["values"]
    vals["species_profiles"]["lesh"]["draws"] = 1234
    E.save_profile("bayes_cohort", "zhaysan", vals, "u1", "правка математика")
    n = len(E.profiles.list_versions(pid))
    E.seed_builtin()
    assert [v["version"] for v in E.versions("bayes_cohort")] == ["2.0.2", "2.0.0"]
    assert E.latest_enabled("bayes_cohort")["version"] == "2.0.2"
    assert len(E.profiles.list_versions(pid)) == n
    assert E.get_profile("bayes_cohort", "zhaysan")["values"]["species_profiles"]["lesh"]["draws"] == 1234
    # профиль, созданный пользователем на версии 2.x, переносом не затрагивается
    E.save_profile("bayes_cohort", "kapshagay", vals, "u1", "новый")
    assert E.profiles.get(E.profile_id("bayes_cohort", "kapshagay"))["migrated_to"] == "defaults 2.0.2"


def test_profile_species_add_remove(calc_stack):
    """«Добавить вид» / «Убрать вид»: значения по умолчанию для вида, виды в данных водоёма, предупреждение
    в запуске о видах данных, которых нет в профиле."""
    dm, da, aa, mod = calc_stack
    p = aa.get("/profiles/bayes_cohort/zhaysan", headers=H("viewer")).json()
    assert {"lesh", "sudak", "yaz"} <= set(p["water_body_species"])
    ref = aa.get("/profiles/bayes_cohort/species-defaults/lesh", headers=H("viewer")).json()
    assert ref["source"] == "reference" and ref["name"] == "лещ"
    assert ref["values"] == p["profile"]["values"]["species_profiles"]["lesh"]
    gen = aa.get("/profiles/bayes_cohort/species-defaults/zherekh", headers=H("viewer")).json()
    assert gen["source"] == "general" and set(gen["values"]) == {r["key"] for r in p["schema"]}
    assert aa.get("/profiles/bayes_cohort/species-defaults/nope", headers=H()).status_code == 404
    assert aa.get("/profiles/seine_catchability/species-defaults/lesh", headers=H()).status_code == 400
    # профиль Балхаша с нуля: жерех и сом (общие значения), без видов Жайсана, которых в Балхаше нет
    body = {"values": {"species_profiles": {"zherekh": gen["values"], "lesh": ref["values"]}}, "comment": "проба"}
    assert aa.put("/profiles/bayes_cohort/balkhash", headers=H("ichthyologist"), json=body).status_code == 200
    assert aa.put("/profiles/bayes_cohort/balkhash", headers=H("viewer"), json=body).status_code == 403
    got = aa.get("/profiles/bayes_cohort/balkhash", headers=H()).json()["profile"]["values"]["species_profiles"]
    assert set(got) == {"zherekh", "lesh"}
    # Жайсан без язя: расчёт возможен, но с предупреждением, что язь не будет рассчитан
    zh = p["profile"]["values"]
    del zh["species_profiles"]["yaz"]
    assert aa.put("/profiles/bayes_cohort/zhaysan", headers=H("mathematician"), json={"values": zh}).status_code == 200
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan"}).json()
    chk = aa.post(f"/calculations/{c['id']}/check", headers=H()).json()
    assert chk["ok"], chk["errors"]
    assert any("язь" in w and "Добавить вид" in w for w in chk["warnings"]), chk["warnings"]


def test_from_step_takes_base_versions(calc_stack):
    """Запуск «с шага»: пропущенные шаги без закреплённой версии берут версию базового запуска,
    даже если в каталоге появилась более новая (исправление алгоритма после базового запуска)."""
    import json
    dm, da, aa, mod = calc_stack
    E = mod.E
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    r = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={}).json()
    assert mod_process(mod)
    files = E.package_files("seine_catchability", "2.0.0")
    man = json.loads(files["manifest.json"]); man["version"] = "2.0.9"
    E.publish(man, dict(files, **{"manifest.json": json.dumps(man).encode()}), actor="system", source="builtin")
    r2 = aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"),
                 json={"from_step": "pdu_by_age", "base_run": r["id"]})
    assert r2.status_code == 201, r2.json()
    r2 = r2.json()
    assert r2["steps"][0]["version"] == "2.0.0" and any("из базового запуска" in w for w in r2["warnings"])
    assert mod_process(mod)
    assert [s["status"] for s in aa.get(f"/runs/{r2['id']}", headers=H()).json()["steps"]] == ["reused", "reused", "done"]
