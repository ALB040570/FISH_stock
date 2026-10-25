"""Сервис расчётов (решение № 70): каталог a–k, параметры алгоритмов с версиями, расчёты с одним результатом,
основной / альтернативный, устаревание, журнал, перенос данных прежних версий."""
import io
import json
import zipfile

from conftest import H

CHAIN = ["net_catchability", "seine_catchability", "seine_likelihood", "net_likelihood", "seine_stock", "net_stock",
         "combined_stock", "pdu_by_age"]


def work(mod, limit=50):
    """Выполнить очередь (как воркер), пока есть что выполнять."""
    from importlib import import_module
    w = import_module("app.worker")
    n = 0
    while n < limit and w.process_one(mod.E, mod.CLIENTS, log=lambda *a: None):
        n += 1
    return n


def make(aa, code, role="ichthyologist", run=True, **kw):
    r = aa.post("/calcs", headers=H(role), json={"algorithm": code, "water_body": kw.pop("water_body", "zhaysan"),
                                                 "run": run, **kw})
    assert r.status_code == 201, r.json()
    return r.json()


def chain(aa, mod):
    ids = {code: make(aa, code)["id"] for code in CHAIN[:2]}
    work(mod)
    for code in CHAIN[2:]:
        ids[code] = make(aa, code)["id"]
        work(mod)
    return ids


def test_catalog_and_default_sets(calc_stack):
    dm, da, aa, mod = calc_stack
    cat = aa.get("/catalog", headers=H("viewer")).json()
    assert [a["letter"] for a in cat] == list("abcdefghijk")
    by = {a["code"]: a for a in cat}
    assert by["removal_pdu"]["planned"] and by["removal_pdu"]["versions"] == []
    assert all(by[c]["latest"] == "3.0.0" for c in CHAIN + ["forecast_pdu"]) and by["bayes_cohort"]["latest"] == "3.0.2"
    assert "stock_by_catch" not in by and "bayes_checks" not in by
    assert by["seine_likelihood"]["manifest"]["requires"]["steps"] == ["seine_catchability"]
    assert by["bayes_cohort"]["manifest"]["requires"]["steps"] == ["seine_likelihood", "net_likelihood", "combined_stock", "pdu_by_age"]
    # наборы «По умолчанию» — у каждого реализованного алгоритма
    sets = aa.get("/param-sets", headers=H("viewer")).json()
    defaults = {s["algorithm"]: s for s in sets if s["is_default"]}
    assert set(defaults) == set(CHAIN + ["bayes_cohort", "forecast_pdu"])
    b = aa.get(f"/param-sets/{defaults['bayes_cohort']['id']}", headers=H("ichthyologist")).json()
    assert set(b["values"]["species_profiles"]) == {"lesh", "sudak", "okun", "plotva", "shuka", "sazan", "karas", "yaz"}
    kinds = {r["key"]: r.get("value_kind") for r in b["schema"]}
    assert kinds["beta_mu"] == "mu" and kinds["beta_lower"] == "lower"
    sb = aa.get(f"/param-sets/{defaults['seine_catchability']['id']}", headers=H("ichthyologist")).json()
    assert sb["values"]["SEINE_C_UPPER"] == 0.8 and sb["values"]["SEINE_C_LOWER_FIRST"] == 0.01
    assert aa.get(f"/param-sets/{defaults['net_stock']['id']}", headers=H()).json()["values"] == {"STOCK_METHOD": "on_stock"}
    # «Презентация» (№ 62): каталог — названия и описания; без кода и значений параметров
    assert len(aa.get("/catalog", headers=H("presenter")).json()) == 11
    for url in ("/catalog/bayes_cohort/versions/3.0.0/files", "/catalog/bayes_cohort/versions/3.0.0/package.zip",
                f"/param-sets/{defaults['bayes_cohort']['id']}"):
        assert aa.get(url, headers=H("presenter")).status_code == 403, url
    # отключение версии — только математик и администратор
    assert aa.post("/catalog/forecast_pdu/versions/3.0.0/disable", headers=H("ichthyologist")).status_code == 403
    assert aa.post("/catalog/forecast_pdu/versions/3.0.0/disable", headers=H("mathematician")).status_code == 200
    c = make(aa, "forecast_pdu", run=False)
    assert any("нет включённых версий" in e for e in c["check"]["errors"])
    assert aa.post("/catalog/forecast_pdu/versions/3.0.0/enable", headers=H("admin")).status_code == 200
    # планируемый алгоритм не запускается
    r = aa.post("/calcs", headers=H("ichthyologist"), json={"algorithm": "removal_pdu", "water_body": "zhaysan"})
    assert r.status_code == 400 and "планируется" in str(r.json())


def test_param_sets(calc_stack):
    dm, da, aa, mod = calc_stack
    d = {s["algorithm"]: s for s in aa.get("/param-sets", headers=H()).json() if s["is_default"]}
    # «По умолчанию» не меняется
    r = aa.put(f"/param-sets/{d['seine_catchability']['id']}", headers=H("mathematician"),
               json={"name": "x", "values": {"SEINE_C_UPPER": 0.7}})
    assert r.status_code == 400
    # набор на основе — правка «неизменяемого» прежде коэффициента новой версией набора
    s = aa.post("/param-sets", headers=H("mathematician"), json={"name": "Верхняя граница 0,7", "base": d["seine_catchability"]["id"]}).json()
    assert s["version"] == 1 and s["values"]["SEINE_C_UPPER"] == 0.8
    s = aa.put(f"/param-sets/{s['id']}", headers=H("mathematician"),
               json={"name": s["name"], "values": {**s["values"], "SEINE_C_UPPER": 0.7}, "comment": "несходимость"}).json()
    assert s["version"] == 2 and s["values"]["SEINE_C_UPPER"] == 0.7 and len(s["versions"]) == 2
    assert aa.get(f"/param-sets/{s['id']}?version=1", headers=H()).json()["values"]["SEINE_C_UPPER"] == 0.8
    # проверка значений
    r = aa.put(f"/param-sets/{s['id']}", headers=H("mathematician"), json={"name": s["name"], "values": {"SEINE_C_UPPER": 5}})
    assert r.status_code == 422
    b = aa.post("/param-sets", headers=H("ichthyologist"), json={"name": "Балхаш", "base": d["bayes_cohort"]["id"]}).json()
    vals = b["values"]
    vals["species_profiles"]["lesh"]["beta_lower"] = 5
    r = aa.put(f"/param-sets/{b['id']}", headers=H("mathematician"), json={"name": "Балхаш", "values": vals})
    assert r.status_code == 422 and "β" in str(r.json())
    # одинаковые названия у алгоритма — нельзя; наблюдатель не правит
    assert aa.post("/param-sets", headers=H("mathematician"), json={"name": "Балхаш", "base": d["bayes_cohort"]["id"]}).status_code == 409
    assert aa.post("/param-sets", headers=H("viewer"), json={"name": "z", "base": d["bayes_cohort"]["id"]}).status_code == 403
    # «Добавить вид»: значения для вида вне эталона — общие значения модели
    sd = aa.get("/param-sets/species-defaults/zherekh", headers=H("presenter"))
    assert sd.status_code == 403
    sd = aa.get("/param-sets/species-defaults/zherekh", headers=H("ichthyologist")).json()
    assert sd["source"] == "general" and "beta_mu" in sd["values"]
    # набор, используемый в расчёте, не удаляется
    c = make(aa, "seine_catchability", run=False, param_set=s["id"])
    assert c["param_version"] == 2 and c["param_set_name"] == "Верхняя граница 0,7"
    assert aa.delete(f"/param-sets/{s['id']}", headers=H("mathematician")).status_code == 409


def test_chain_main_rerun_stale(calc_stack):
    dm, da, aa, mod = calc_stack
    ids = chain(aa, mod)
    for code, cid in ids.items():
        c = aa.get(f"/calcs/{cid}", headers=H("viewer")).json()
        assert c["state"] == "done", (code, c.get("message"))
        assert c["is_main"] and c["stale"] == []          # первый результат — основной
    # результаты: ПДУ НПЦ распределён полностью; файлы; выгрузка
    res = aa.get(f"/calcs/{ids['pdu_by_age']}/result", headers=H("ichthyologist")).json()
    lesh24 = sum(r["pdu_t"] or 0 for r in res["tables"]["pdu_by_age"]["rows"] if r["species"] == "лещ" and r["year"] == 2024)
    assert abs(lesh24 - 4488) < 1
    g = aa.get(f"/calcs/{ids['combined_stock']}/result", headers=H("ichthyologist")).json()
    assert {"yearly_stock", "stock_by_age", "tonnes"} <= set(g["tables"])
    assert aa.get(f"/calcs/{ids['pdu_by_age']}/files/pdu_by_age.xlsx", headers=H("ichthyologist")).status_code == 200
    assert aa.get(f"/calcs/{ids['pdu_by_age']}/files/state.pkl", headers=H("ichthyologist")).status_code == 404
    z = zipfile.ZipFile(io.BytesIO(aa.get(f"/calcs/{ids['pdu_by_age']}/export.zip", headers=H()).content))
    assert any(n.endswith("h_pdu_by_age/zhaysan_pdu_pieces_3d.nc") for n in z.namelist()) and "journal.json" in z.namelist()
    # права на результаты (№ 62): список и статусы — всем, результаты, файлы, журнал выполнения, отчёт — нет
    for role in ("viewer", "operator", "presenter"):
        assert aa.get(f"/calcs/{ids['pdu_by_age']}", headers=H(role)).status_code == 200
        for url in (f"/calcs/{ids['pdu_by_age']}/result", f"/calcs/{ids['pdu_by_age']}/log",
                    f"/calcs/{ids['pdu_by_age']}/files/pdu_by_age.xlsx", f"/calcs/{ids['pdu_by_age']}/export.zip",
                    "/water-bodies/zhaysan/report.pdf"):
            assert aa.get(url, headers=H(role)).status_code == 403, (role, url)
        assert aa.post(f"/calcs/{ids['pdu_by_age']}/run", headers=H(role)).status_code == 403
    # сводка для карты и «Потока»; результат основного расчёта для мониторинга
    st = aa.get("/water-bodies/status", headers=H("ichthyologist")).json()["zhaysan"]
    assert set(st["main"]) == set(CHAIN) and st["stale"] == [] and st["pdu_npc"]["rows"]
    mr = aa.get("/water-bodies/zhaysan/main-result?algorithm=pdu_by_age", headers=H("viewer")).json()
    assert mr["calc"]["id"] == ids["pdu_by_age"] and mr["result"] is None            # наблюдателю — без результата
    mr = aa.get("/water-bodies/zhaysan/main-result?algorithm=pdu_by_age", headers=H("ichthyologist")).json()
    assert mr["result"]["payload"]["species"]
    for fmt in ("docx", "pdf"):
        r = aa.get(f"/water-bodies/zhaysan/report.{fmt}", headers=H("ichthyologist"))
        assert r.status_code == 200 and len(r.content) > 1000
    # повторный запуск затирает результат; в журнале — оба выполнения
    b = aa.get(f"/calcs/{ids['seine_catchability']}", headers=H()).json()
    rid = b["result"]["result_id"]
    aa.post(f"/calcs/{ids['seine_catchability']}/run", headers=H("ichthyologist"))
    work(mod)
    b = aa.get(f"/calcs/{ids['seine_catchability']}", headers=H()).json()
    assert b["result"]["result_id"] != rid
    runs = [j for j in aa.get(f"/calcs/{ids['seine_catchability']}/journal", headers=H("viewer")).json() if j["action"] == "run"]
    assert len(runs) == 2 and all(j["status"] == "done" and j["param_set_name"] for j in runs)
    # зависимые расчёты устарели: c — вход пересчитан, e, g, h — вход устарел
    cs = {c["algorithm"]: c for c in aa.get("/calcs?water_body=zhaysan", headers=H()).json()}
    assert cs["seine_likelihood"]["stale"] == ["расчёт-вход b пересчитан"]
    assert cs["seine_stock"]["stale"] == ["расчёт-вход c устарел"]
    assert cs["pdu_by_age"]["stale"] and not cs["net_likelihood"]["stale"] and not cs["seine_catchability"]["stale"]
    assert aa.get("/water-bodies/status", headers=H()).json()["zhaysan"]["stale"]
    r = aa.post("/calcs/recalc-stale", headers=H("ichthyologist"), json={"water_body": "zhaysan"}).json()
    assert [x["id"] for x in r["queued"]] == [ids[c] for c in ("seine_likelihood", "seine_stock", "combined_stock", "pdu_by_age")]
    work(mod)
    cs = {c["algorithm"]: c for c in aa.get("/calcs?water_body=zhaysan", headers=H()).json()}
    assert all(not c["stale"] and c["state"] == "done" for c in cs.values()), {k: (c["stale"], c["message"]) for k, c in cs.items()}


def test_alternative_input_and_main(calc_stack):
    dm, da, aa, mod = calc_stack
    ids = chain(aa, mod)
    d = {s["algorithm"]: s for s in aa.get("/param-sets", headers=H()).json() if s["is_default"]}
    s = aa.post("/param-sets", headers=H("mathematician"), json={"name": "c ≤ 0,7", "base": d["seine_catchability"]["id"]}).json()
    aa.put(f"/param-sets/{s['id']}", headers=H("mathematician"), json={"name": s["name"], "values": {**s["values"], "SEINE_C_UPPER": 0.7}})
    b2 = make(aa, "seine_catchability", param_set=s["id"], period={"from": 2015, "to": 2024})
    work(mod)
    b2 = aa.get(f"/calcs/{b2['id']}", headers=H()).json()
    assert b2["state"] == "done" and not b2["is_main"] and "c ≤ 0,7" in b2["title"]
    # вход по умолчанию — основной; можно указать альтернативный
    c2 = make(aa, "seine_likelihood", inputs={"seine_catchability": b2["id"]})
    work(mod)
    c2 = aa.get(f"/calcs/{c2['id']}", headers=H()).json()
    assert c2["state"] == "done" and c2["result"]["inputs"]["seine_catchability"]["calc_id"] == b2["id"]
    r1 = aa.get(f"/calcs/{ids['seine_likelihood']}/result", headers=H("ichthyologist")).json()["tables"]["per_haul"]["rows"]
    r2 = aa.get(f"/calcs/{c2['id']}/result", headers=H("ichthyologist")).json()["tables"]["per_haul"]["rows"]
    assert [x["stock"] for x in r1] != [x["stock"] for x in r2]
    # смена основного: c (вход «основной») устаревает, c2 (вход указан) — нет
    assert aa.post(f"/calcs/{b2['id']}/main", headers=H("viewer")).status_code == 403
    aa.post(f"/calcs/{b2['id']}/main", headers=H("ichthyologist"))
    cs = {c["id"]: c for c in aa.get("/calcs?water_body=zhaysan", headers=H()).json()}
    assert cs[b2["id"]]["is_main"] and not cs[ids["seine_catchability"]]["is_main"]
    assert cs[ids["seine_likelihood"]]["stale"] == ["сменился основной расчёт-вход b"]
    assert cs[c2["id"]]["stale"] == []
    j = aa.get(f"/calcs/{ids['seine_catchability']}/journal", headers=H()).json()
    assert any("стал альтернативным" in (x.get("message") or "") for x in j)
    # расчёт, указанный входом, не удаляется
    assert aa.delete(f"/calcs/{b2['id']}", headers=H("ichthyologist")).status_code == 409
    # новая версия набора данных — устаревают расчёты, которые его используют
    from conftest import REPO
    f = REPO / "samples" / "zhaysan" / "mean_weights.xlsx"
    r = da.post("/upload", headers=H("ichthyologist"), data={"water_body": "zhaysan", "dataset_type": "mean_weights",
                                                            "mode": "replace"}, files={"file": (f.name, f.read_bytes())})
    assert r.json()["ok"]
    cs = {c["algorithm"] + c["id"]: c for c in aa.get("/calcs?water_body=zhaysan", headers=H()).json()}
    stale = {c["algorithm"] for c in cs.values() if any("mean_weights" in x for x in c["stale"])}
    assert {"seine_catchability", "net_catchability", "seine_stock", "combined_stock", "pdu_by_age"} <= stale


def test_period_and_errors(calc_stack):
    dm, da, aa, mod = calc_stack
    b = make(aa, "seine_catchability", period={"from": 2018, "to": 2022})
    work(mod)
    b = aa.get(f"/calcs/{b['id']}", headers=H()).json()
    assert b["state"] == "done" and b["result"]["years"] == [2018, 2019, 2020, 2021, 2022] and b["period_text"] == "2018–2022"
    # c за все годы по b за 2018–2022 — предупреждение нет (период не задан), расчёт за общие годы с замечанием
    c = make(aa, "seine_likelihood", period={"from": 2015, "to": 2024}, run=False)
    chk = aa.post(f"/calcs/{c['id']}/check", headers=H()).json()
    assert chk["ok"] and any("рассчитан за 2018–2022" in w for w in chk["warnings"])
    aa.post(f"/calcs/{c['id']}/run", headers=H("ichthyologist"))
    work(mod)
    c = aa.get(f"/calcs/{c['id']}", headers=H()).json()
    assert c["state"] == "done" and c["result"]["years"] == [2018, 2019, 2020, 2021, 2022]
    assert any("2018–2022" in n for n in c["result"]["notes"])
    # нет основного входа — понятная ошибка до запуска
    r = aa.post("/calcs", headers=H("ichthyologist"), json={"algorithm": "net_likelihood", "water_body": "zhaysan", "run": True})
    assert r.status_code == 422 and "Нет основного расчёта «a. Уловистость сети" in str(r.json())
    # водоём без данных
    r = aa.post("/calcs", headers=H("ichthyologist"), json={"algorithm": "seine_catchability", "water_body": "balkhash", "run": True})
    assert r.status_code == 422 and "не загружен набор" in str(r.json())
    # период задан неверно
    r = aa.post("/calcs", headers=H("ichthyologist"), json={"algorithm": "seine_catchability", "water_body": "zhaysan",
                                                            "period": {"from": 2024, "to": 2018}})
    assert r.status_code == 422
    # отмена до начала выполнения
    x = make(aa, "net_catchability")
    x = aa.post(f"/calcs/{x['id']}/cancel", headers=H("ichthyologist")).json()
    assert x["state"] == "cancelled" and not work(mod)
    # набор без части значений дополняется значениями по умолчанию
    s = aa.post("/param-sets", headers=H("mathematician"), json={"name": "проба 20", "algorithm": "seine_catchability",
                                                                "values": {"SEINE_MIN_SAMPLE": 20}}).json()
    assert s["values"]["SEINE_C_UPPER"] == 0.8


def test_migration_from_runs(tmp_path, monkeypatch):
    """Переход на каталог a–k: прежние запуски, цепочки и основной запуск удаляются, профили модели водоёмов
    становятся наборами параметров алгоритма i со всеми правками; второй запуск ничего не меняет."""
    from conftest import load_service
    from fishcommon.storage import Collection, atomic_write_json, dumps
    root = tmp_path / "algo_admin"
    for d in ("runs/R1", "calculations/C1", "catalog/stock_by_catch/versions/1", "catalog/bayes_checks"):
        (root / d).mkdir(parents=True)
    atomic_write_json(root / "runs/R1/meta.json", {"id": "R1", "status": "done"})
    atomic_write_json(root / "catalog/stock_by_catch/meta.json", {"id": "stock_by_catch", "code": "stock_by_catch"})
    atomic_write_json(root / "catalog/bayes_checks/meta.json", {"id": "bayes_checks", "code": "bayes_checks"})
    atomic_write_json(root / "main_runs.json", {"zhaysan": {"run_id": "R1"}})
    prof = Collection(root, "profiles")
    prof.create({"algorithm": "bayes_cohort", "water_body": "balkhash"}, actor="u", obj_id="bayes_cohort__balkhash")
    prof.add_version("bayes_cohort__balkhash", {"values.json": dumps({"species_profiles": {"zherekh": {"draws": 3000}}}).encode()},
                     {}, "u")
    mod = load_service("algo_admin", tmp_path, monkeypatch)
    E = mod.E
    assert not (root / "runs").exists() and not (root / "calculations").exists() and not (root / "main_runs.json").exists()
    assert not E.catalog.exists("stock_by_catch") and not E.catalog.exists("bayes_checks")
    sets = [s for s in E.param_sets.list() if s["algorithm"] == "bayes_cohort" and not s["is_default"]]
    assert len(sets) == 1 and E.set_values(sets[0]["id"]) == {"species_profiles": {"zherekh": {"draws": 3000}}}
    assert "balkhash" in sets[0]["name"] and not (root / "profiles").exists()
    E.seed_builtin()
    assert len([s for s in E.param_sets.list() if s["algorithm"] == "bayes_cohort"]) == 2
    assert len(E.param_sets.list_versions("default_bayes_cohort")) == 1


def test_recover_stale_after_restart(tmp_path, monkeypatch):
    """Расчёт, оборванный перезапуском воркера, помечается прерванным, а не висит «выполняется»."""
    import os
    from conftest import load_service
    load_service("algo_admin", tmp_path, monkeypatch)
    from importlib import import_module
    eng_mod = import_module("app.engine")
    E = eng_mod.Engine(tmp_path / "recover")
    me = eng_mod.worker_name()
    host = me.split(":")[0]
    mk = lambda w, st="running": E.calcs.create({"state": st, "worker": w, "water_body": "zhaysan", "algorithm": "x"})
    old_container = mk("3f2a9c1b7d4e:1:aaaa")
    same_pid_new_boot = mk(f"{host}:{os.getpid()}:bbbb")
    mine = mk(me)
    queued = mk("x:1:c", st="queued")
    assert E.recover_stale(host, sole=False) == 1
    assert E.calcs.get(same_pid_new_boot["id"])["state"] == "failed"
    assert E.calcs.get(old_container["id"])["state"] == "running"
    monkeypatch.setenv("FISH_WORKER_SOLE", "1")
    assert E.recover_stale(host) == 1
    r = E.calcs.get(old_container["id"])
    assert r["state"] == "failed" and "перезапуск" in r["message"]
    assert E.journal(old_container["id"])[-1]["status"] == "failed"
    assert E.calcs.get(mine["id"])["state"] == "running"
    assert E.calcs.get(queued["id"])["state"] == "queued"


def test_classification(calc_stack):
    dm, da, aa, mod = calc_stack
    cl = aa.get("/classifiers", headers=H("viewer")).json()
    assert [m["code"] for m in cl["stock_methods"]] == ["area", "balance", "model"]
    cat = {a["code"]: a["classification"] for a in aa.get("/catalog", headers=H("viewer")).json()}
    assert cat["bayes_cohort"] == {"model_type": "stochastic", "stock_methods": ["model"]}
    assert cat["seine_likelihood"]["stock_methods"] == ["area"] and cat["net_stock"]["stock_methods"] == ["balance"]
    body = {"model_type": "deterministic", "stock_methods": ["balance"]}
    assert aa.put("/catalog/pdu_by_age/classification", headers=H("ichthyologist"), json=body).status_code == 403
    assert aa.put("/catalog/pdu_by_age/classification", headers=H("mathematician"), json=body).status_code == 200
    assert aa.get("/catalog/pdu_by_age", headers=H()).json()["classification"] == body
    assert json.dumps(cat)


def test_queue_chain_before_inputs_exist(calc_stack):
    """Новый водоём: расчёты a–e можно поставить в очередь сразу — зависимые ждут свои входы, первый результат
    каждого становится основным и берётся входом следующего."""
    dm, da, aa, mod = calc_stack
    ids = [make(aa, code)["id"] for code in CHAIN[:5]]
    q = aa.get("/queue", headers=H("viewer")).json()
    assert [c["id"] for c in q["queued"]] == ids
    c = aa.get(f"/calcs/{ids[2]}", headers=H()).json()
    assert any("выполняется — расчёт начнётся после него" in w for w in c["check"]["warnings"])
    assert work(mod) == 5
    for cid in ids:
        c = aa.get(f"/calcs/{cid}", headers=H()).json()
        assert c["state"] == "done" and c["is_main"] and not c["stale"], (c["algorithm"], c.get("message"))


def test_egg_scale_calc_is_not_main(calc_stack):
    """Модель в режиме «подбор масштаба выживаемости икры» (решение № 73): таблица подбора, расчёт служебный —
    не становится основным ни автоматически, ни вручную."""
    dm, da, aa, mod = calc_stack
    chain(aa, mod)
    d = {s["algorithm"]: s for s in aa.get("/param-sets", headers=H()).json() if s["is_default"]}
    s = aa.post("/param-sets", headers=H("mathematician"), json={"name": "подбор egg_scale", "base": d["bayes_cohort"]["id"]}).json()
    aa.put(f"/param-sets/{s['id']}", headers=H("mathematician"), json={"name": s["name"], "values": {**s["values"], "mode": "egg_scale"}})
    c = make(aa, "bayes_cohort", param_set=s["id"], calc_params={"species": ["lesh"]})
    work(mod)
    c = aa.get(f"/calcs/{c['id']}", headers=H()).json()
    assert c["state"] == "done", c.get("message")
    assert c["result"]["not_main"] and not c["is_main"]
    assert aa.post(f"/calcs/{c['id']}/main", headers=H("ichthyologist")).status_code == 400
    rows = aa.get(f"/calcs/{c['id']}/result", headers=H("ichthyologist")).json()["tables"]["egg_scale_fit"]["rows"]
    assert [r["species"] for r in rows] == ["лещ"] and rows[0]["suggested"]
