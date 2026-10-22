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
        elif str(w["source"].get("view", "")).startswith(("by_", "fc_")):   # модель и прогноз: в расчёте «stock» шагов нет
            assert j.get("empty") and "полный расчёт" in j["message"], w["id"]
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


def test_catchability_views(calc_stack, tmp_path, monkeypatch):
    """Уловистость в мониторинге: блоки-слайды повторяют числа результата этапов 1–2 (как страницы прежнего приложения)."""
    dm, da, aa, aa_mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={})
    assert mod_process(aa_mod)
    mod = load_service("dashboards", tmp_path, monkeypatch)
    for k, cl in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        mod.SVC[k] = mod.Svc(k, http=cl)
    db = TestClient(mod.app)

    def view(name, sp=None, **flt):
        r = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "insight", "view": name},
                                                                 "filters": {"water_body": "zhaysan", "species": sp, **flt}, "options": {}})
        assert r.status_code == 200, r.text
        return r.json()

    seine = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "payload", "algorithm": "seine_catchability"},
                                                                "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]
    net = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "payload", "algorithm": "stock_by_catch"},
                                                              "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]["net"]
    f = seine["fits"]["лещ"]["2024"]
    # контрольные числа прежнего приложения (лещ, 2024): j50 ≈ 3,1; a = 3,97; c = 0,01…0,67; Z = 0,43; R² = 0,79; 574 рыбы
    assert round(f["j50"], 1) == 3.1 and round(f["a"], 2) == 3.97 and round(f["Z"], 2) == 0.43 and f["n_sample"] == 574
    t = view("ca_seine_tiles", "lesh")
    vals = {x["label"]: x["value"] for x in t["tiles"]}
    assert vals["Точка перегиба j50"] == "3,1" and vals["Крутизна a"] == "3,97" and vals["Уловистость по возрастам"] == "0,01 … 0,67"
    assert vals["Общая смертность Z"] == "0,43" and vals["Качество подгонки R²"] == "0,79" and vals["Данные года"] == "574 рыб"
    assert t["year"] == 2024 and t["calc_year"] and t["warnings"] and "двухлеток" in t["warnings"][0]["text"]
    # улов и кривая — те же ряды, что в результате
    ch = view("ca_seine_catch", "lesh")["chart"]
    assert ch["series"][0]["values"] == f["observed"] and ch["series"][1]["values"] == f["fitted"] and ch["x"][0] == "1–2"
    cu = view("ca_seine_curve", "lesh")["chart"]
    assert cu["series"][0]["values"] == f["c"] and cu["vrefs"][0]["x"] == f["j50"] and cu["hrefs"][1]["y"] == seine["c_upper"]
    # тепловая карта и параметры: все годы, выбранный год выделен; год переключается фильтром
    h = view("ca_seine_heat", "lesh", year=2019)
    assert h["year"] == 2019 and len(h["rows"]) == len(seine["years"]) and h["chart"]["pick_year"]
    assert next(r for r in h["rows"] if r["year"] == 2019)["_current"]
    p = view("ca_seine_params", "sudak", year=2023)
    r23 = next(r for r in p["rows"] if r["year"] == 2023)
    assert r23["a"] == seine["fits"]["судак"]["2023"]["a"] and p["row_action"] == "year"
    # все виды за год: строка — вид (щелчок — все данные по виду)
    s = view("ca_seine_species")
    assert len(s["rows"]) == len(seine["species"]) and s["row_action"] == "species" and {r["_code"] for r in s["rows"]} >= {"lesh", "sudak"}
    # сеть: вершина параболы, ветви, σ
    fn = net["fits"]["лещ"]["2024"]
    nt = {x["label"]: x["value"] for x in view("ca_net_tiles", "lesh")["tiles"]}
    assert nt["Вершина параболы c¹"] == "возраст " + f"{int(fn['peak']) - 1}–{int(fn['peak'])}"
    ag = view("ca_net_ages", "lesh")
    assert [r["sigma"] for r in ag["rows"]] == fn["sigma"]
    # казахский язык и вид вне расчёта
    k = view("ca_seine_tiles", "lesh", lang="kk")
    assert k["tiles"][0]["label"] == "Иілу нүктесі j50" and "жылы" not in k["explain"]["how"][0]
    assert view("ca_seine_tiles", "nalim").get("empty")
    # ---- запас по уловам: те же числа, что в результате; виды не складываются; возрасты по порядку
    st = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "payload", "algorithm": "stock_by_catch"},
                                                             "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]["stock"]
    tot = st["species"]["лещ"]["variants"]["with_ages"]["on_stock"]["totals"]
    yt = view("st_table", "lesh")
    assert [r["mean"] for r in yt["rows"]] == tot["сеть+невод"] and [r["net"] for r in yt["rows"]] == tot["сеть"]
    t2 = view("st_tiles", "lesh", variant="out_ages", method="on_catch")
    oc = st["species"]["лещ"]["variants"]["out_ages"]["on_catch"]["totals"]["сеть+невод"][-1]
    assert t2["values"]["mean"] == oc and [g["value"] for g in t2["toggles"]] == ["out_ages", "on_catch"]
    sp_rows = view("st_species")["rows"]
    assert len(sp_rows) == len(st["species"]) and next(r for r in sp_rows if r["_code"] == "lesh")["mean"] == tot["сеть+невод"][-1]
    ages = [r["age"] for r in view("st_ages", "lesh")["rows"]]
    assert ages[:3] == ["1–2", "2–3", "3–4"] and ages.index("10–11") > ages.index("9–10")
    hl = view("st_hauls", "lesh")
    assert hl["chart"]["kind"] == "dots" and sum(len(d["points"]) for d in hl["chart"]["dots"]) == len(hl["rows"])
    # ---- ПДУ НПЦ (официальный): числа результата этапа 3; лещ 2024 — 11 302 439 шт
    pdu = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "payload", "algorithm": "pdu_by_age"},
                                                              "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]
    pl = pdu["species"]["лещ"]
    pt = view("pn_tiles", "lesh")
    assert pt["values"]["pcs"] == pl["pieces_total"][-1] == 11302439 and pt["values"]["pdu_t"] == pl["pdu_t"][-1]
    pa = view("pn_ages", "lesh", year=2020)
    assert [r["pcs"] for r in pa["rows"]] == pl["by_year"][pdu["years"].index(2020)]["pieces"]
    assert all(r["expl"] is None for r, a in zip(pa["rows"], pl["ages"]) if a < pl["m0"])
    ps = view("pn_species")
    assert {r["_code"] for r in ps["rows"]} >= {"lesh", "sudak"} and "F = k·M" not in str(ps["columns"])
    # байесовская модель и ПДУ приложения: в расчёте «stock» их нет — понятное сообщение, а не ошибка
    assert "полный расчёт" in view("by_total", "lesh")["message"] and "полный расчёт" in view("fc_tiles", "lesh")["message"]
    # ---- «Можно ли верить запасу» (спецификация catchability_trust, контрольный пример Жайсан 2024)
    tr = view("ca_trust")
    T = {r["species"]: r for r in tr["trust"]["rows"]}
    assert tr["year"] == 2024 and tr["default_view"] == "trust" and len(T) == 8
    assert tr["trust"]["head"].startswith("Проверки пройдены у 2 из 8 видов")
    ctl = {  # вид: (запас на границах %, невод/сеть, k, n, наибольший рост, рыб, R², уровень)
        "лещ": (4.3, 1.99, 5, 14, 43.6, 574, 0.79, "warning"), "плотва": (34.0, 1.33, 1, 8, 8.3, 352, 0.84, "warning"),
        "сазан": (35.0, 6.19, 5, 8, 37.6, 30, 0.82, "warning"), "карась": (0, 0.43, 3, 13, 2.8, 36, 0.84, "warning"),
        "язь": (7.2, 1.46, 7, 11, 7.5, 11, 0.72, "warning"), "судак": (0, 1.26, 2, 9, 4.4, 363, 0.74, "ok"),
        "окунь": (29.0, 2.65, 2, 11, 14.6, 297, 0.84, "warning"), "щука": (2.2, 0.90, 2, 8, 16.8, 71, 0.74, "ok")}
    for s, (b, rt, k, n, x, ns, r2, lv) in ctl.items():
        r = T[s]
        assert round(r["bounds"]["pct"], 1) == b and round(r["gears"]["ratio"], 2) == rt, s
        assert (r["cohorts"]["k"], r["cohorts"]["n"]) == (k, n) and round(r["cohorts"]["best"]["x"], 1) == x, s
        assert r["sample"]["n"] == ns and round(r["sample"]["r2"], 2) == r2 and r["verdict"]["level"] == lv, s
    assert T["язь"]["sample"]["pooled"] and not T["язь"]["sample"]["small"] and T["сазан"]["sample"]["small"]
    assert T["щука"]["cohorts"]["k"] / T["щука"]["cohorts"]["n"] == 0.25 and not T["щука"]["cohorts"]["hit"]   # граница: только «больше»
    assert T["лещ"]["verdict"]["phrase"] == ("Есть вопросы: 5 из 14 поколений выросли за год больше чем вдвое "
                                            "(наибольший рост ×43,6).")
    assert T["сазан"]["verdict"]["label"] == "4 вопроса" and T["язь"]["verdict"]["label"] == "Проба за все годы, поколения"
    assert "(24)" not in str(tr) and "стар" not in str(tr).lower()
    # первый год ряда — проверять поколения не с чем
    first = view("ca_trust", year=min(seine["years"]))
    assert all(r["cohorts"]["n"] == 0 and not r["cohorts"]["hit"] for r in first["trust"]["rows"])
    # отключённое правило не проверяется; изменённый порог меняет вывод
    rules = db.get("/signal-rules", headers=H("viewer")).json()["rules"]
    put = [{"code": r["code"], "enabled": r["enabled"], "values": r["values"]} for r in rules]
    for r in put:
        if r["code"] == "cohort_growth":
            r["enabled"] = False
        if r["code"] == "gears_disagree":
            r["values"] = {"ratio": 7}
    assert db.put("/signal-rules", headers=H("ichthyologist"), json={"rules": put}).status_code == 200
    T2 = {r["species"]: r for r in view("ca_trust")["trust"]["rows"]}
    assert T2["лещ"]["verdict"]["level"] == "ok" and "отключено" in T2["лещ"]["verdict"]["phrase"]
    assert not T2["сазан"]["gears"]["hit"] and not T2["окунь"]["gears"]["hit"] and T2["карась"]["verdict"]["level"] == "ok"
    # одно орудие и вид без подгонки сети — без цвета и без ошибки
    import copy, importlib
    cv = importlib.import_module(mod.__package__ + ".calc_views")
    real_stock, real_payload = cv._stock, cv._payload

    def one_gear(D, *a, **k):
        st, m = real_stock(D, *a, **k)
        st = copy.deepcopy(st)
        for sp in st["species"].values():
            tot = sp["variants"]["with_ages"]["on_stock"]["totals"][st["gears"]["seine"]]
            tot[:] = [0] * len(tot)
        return st, m

    def no_net(D, gear, *a, **k):
        p, m = real_payload(D, gear, *a, **k)
        if gear == "net":
            p = {**p, "fits": {s: v for s, v in p["fits"].items() if s != "лещ"}}
        return p, m
    monkeypatch.setattr(cv, "_stock", one_gear)
    monkeypatch.setattr(cv, "_payload", no_net)
    T3 = {r["species"]: r for r in view("ca_trust")["trust"]["rows"]}
    assert all(r["gears"]["one"] and r["gears"]["ratio"] is None and not r["gears"]["hit"] for r in T3.values())
    assert T3["лещ"]["bounds"]["pct"] is not None and T3["лещ"]["bounds"]["gear"] in ("", "невод")
