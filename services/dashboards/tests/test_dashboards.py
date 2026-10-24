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
        elif str(w["source"].get("view", "")).startswith("bc_"):            # проверки модели — отдельный шаг
            assert j.get("empty") and "Проверки байесовской модели" in j["message"], w["id"]
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
    """Улов по ловам и возрастам: Y_ijd = Y_id · q_ij(t_d), q — доли сглаженной пробы года (эталон 22.10.2026:
    в сумме одна условная рыба на группы j ≤ m1; пробы меньше 30 рыб — вместе с соседними годами ± 1)."""
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
    def year_sample(y):
        return {r["age"]: (r.get("sudak") or 0) for r in ages if r["year"] == y}
    n = year_sample(2019)
    if sum(n.values()) < 30:
        for y in (2018, 2020):
            for a, v in year_sample(y).items():
                n[a] = n.get(a, 0) + v
    J = sum(1 for a in n if a <= m1)
    sm = {a: v + (1 / J if a <= m1 else 0) for a, v in n.items()}
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
    # контрольные числа эталона 22.10.2026 (лещ, 2024): j50 ≈ 3,1; a = 3,91; c = 0,01…0,67; Z = 0,45; R² = 0,78; 574 рыбы
    assert round(f["j50"], 1) == 3.1 and round(f["a"], 2) == 3.91 and round(f["Z"], 2) == 0.45 and f["n_sample"] == 574
    t = view("ca_seine_tiles", "lesh")
    vals = {x["label"]: x["value"] for x in t["tiles"]}
    assert vals["Точка перегиба j50"] == "3,1" and vals["Крутизна a"] == "3,91" and vals["Уловистость по возрастам"] == "0,01 … 0,67"
    assert vals["Общая смертность Z"] == "0,45" and vals["Качество подгонки R²"] == "0,78" and vals["Данные года"] == "574 рыб"
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
    # ---- ПДУ НПЦ (официальный): числа результата этапа 3; лещ 2024 — 11 968 214 шт (эталон 22.10.2026)
    pdu = db.post("/widgets/data", headers=H("viewer"), json={"source": {"kind": "payload", "algorithm": "pdu_by_age"},
                                                              "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]
    pl = pdu["species"]["лещ"]
    pt = view("pn_tiles", "lesh")
    assert pt["values"]["pcs"] == pl["pieces_total"][-1] == 11968214 and pt["values"]["pdu_t"] == pl["pdu_t"][-1]
    pa = view("pn_ages", "lesh", year=2020)
    assert [r["pcs"] for r in pa["rows"]] == pl["by_year"][pdu["years"].index(2020)]["pieces"]
    assert all(r["expl"] is None for r, a in zip(pa["rows"], pl["ages"]) if a < pl["m0"])
    ps = view("pn_species")
    assert {r["_code"] for r in ps["rows"]} >= {"lesh", "sudak"} and "F = k·M" not in str(ps["columns"])
    # байесовская модель и ПДУ приложения: в расчёте «stock» их нет — понятное сообщение, а не ошибка
    assert "полный расчёт" in view("by_total", "lesh")["message"] and "полный расчёт" in view("fc_tiles", "lesh")["message"]
    # ---- «Можно ли верить запасу»: контрольный пример Жайсан 2024 по эталону 22.10.2026 (независимый пересчёт
    # по файлам legacy/fish_stock_forecast/results — tools/control_trust.py)
    tr = view("ca_trust")
    T = {r["species"]: r for r in tr["trust"]["rows"]}
    assert tr["year"] == 2024 and tr["default_view"] == "trust" and len(T) == 8
    assert [r["species"] for r in tr["trust"]["rows"]] == ["лещ", "судак", "окунь", "плотва", "сазан", "щука", "карась", "язь"]
    assert tr["trust"]["head"].startswith("Проверки пройдены у 0 из 8 видов")
    ctl = {  # вид: (запас на границах %, невод/сеть, k, n, наибольший рост, рыб, R²)
        "лещ": (0.5, 9.84, 3, 14, 476.8, 574, 0.78), "судак": (54.5, 5.65, 1, 9, 3.5, 363, 0.69),
        "окунь": (31.7, 11.73, 1, 11, 173.3, 297, 0.79), "плотва": (43.4, 6.78, 1, 8, 54.3, 352, 0.83),
        "сазан": (7.7, 39.20, 4, 8, 103.8, 30, 0.79), "щука": (2.5, 3.43, 2, 8, 135.4, 71, 0.65),
        "карась": (27.6, 2.81, 4, 13, 32.4, 36, 0.65), "язь": (3.1, 6.07, 1, 11, 71.6, 11, 0.72)}
    for s_, (b, rt, k, n, x, ns, r2) in ctl.items():
        r = T[s_]
        assert round(r["bounds"]["pct"], 1) == b and round(r["gears"]["ratio"], 2) == rt, s_
        assert (r["cohorts"]["k"], r["cohorts"]["n"]) == (k, n) and round(r["cohorts"]["best"]["x"], 1) == x, s_
        assert r["sample"]["n"] == ns and round(r["sample"]["r2"], 2) == r2 and r["verdict"]["level"] == "warning", s_
        assert r["gears"]["hit"], s_                     # невод и сеть расходятся больше чем вдвое у всех видов
    assert T["язь"]["sample"]["pooled"] and not T["язь"]["sample"]["small"] and T["сазан"]["sample"]["small"]
    assert T["щука"]["cohorts"]["k"] / T["щука"]["cohorts"]["n"] == 0.25 and not T["щука"]["cohorts"]["hit"]   # граница: только «больше»
    assert T["сазан"]["cohorts"]["hit"] and not T["лещ"]["cohorts"]["hit"]
    assert [s_ for s_, r in T.items() if r["bounds"]["hit"]] == ["судак", "окунь", "плотва", "карась"]
    assert T["лещ"]["verdict"]["phrase"] == "Есть вопросы: невод даёт в 9,8 раза больше сети."
    assert T["сазан"]["verdict"]["label"] == "Орудия, поколения, мало рыб" and T["язь"]["verdict"]["label"] == "Проба за все годы, орудия"
    assert "(24)" not in str(tr) and "стар" not in str(tr).lower()
    # первый год ряда — проверять поколения не с чем
    first = view("ca_trust", year=min(seine["years"]))
    assert all(r["cohorts"]["n"] == 0 and not r["cohorts"]["hit"] for r in first["trust"]["rows"])
    # ---- часть Б: подробные проверки вида — те же числа, что в сводке
    by = view("ca_bounds_years", "lesh")
    r24 = next(r for r in by["rows"] if r["year"] == 2024)
    assert round(r24["pct"], 1) == 0.5 and by["chart"]["pick_year"] and by["threshold"] == 25
    ba = view("ca_bounds_ages", "plotva")
    assert round(ba["bounds"]["pct"], 1) == 43.4 and [r["age"] for r in ba["rows"] if r["_level"]] == ["1–2", "2–3"]
    co = view("ca_cohorts", "lesh")
    last = [c for c in co["chart"]["cells"] if c[1] == len(co["chart"]["y"]) - 1]
    assert sum(1 for c in last if c[5]) == 3 and len(last) == 14 and co["chart"]["fmt"] == "ratio"
    assert "×476,8" in [c[3] for c in last]
    ga = view("ca_gears_age", "lesh")
    assert ga["chart"]["cells"] and all(len(c) == 6 for c in ga["chart"]["cells"])
    pp = view("ca_passport")
    assert pp["chart"]["y"][:2] == [tr["trust"]["rows"][0]["species"], tr["trust"]["rows"][1]["species"]] and len(pp["chart"]["y_codes"]) == 8
    yaz = next(r for r in pp["rows"] if r["species"] == "язь" and r["year"] == 2024)
    assert "проба за все годы" in yaz["issues"] and yaz["_level"] == "warning"
    z = view("ca_z", "lesh")
    assert len(z["chart"]["series"]) == 2 and next(r for r in z["rows"] if r["year"] == 2024)["Z"] == f["Z"]
    assert len(view("ca_z")["chart"]["series"]) == 8
    bl = view("ca_blind", "lesh")
    assert bl["blind"] and "из 100 рыб попадается 1" in bl["blind"][0] and "умноженный на 100" in bl["blind"][0]
    sg = view("ca_strong", "lesh")
    assert len(sg["rows"]) == len(f["ages"]) or sg["rows"]
    for m in ("dev", "gears", "growth"):
        h = view("ca_seine_heat", "lesh", hmode=m)
        assert h["hmode"] == m and h["chart"]["cells"] and h["toggles"][0]["value"] == m
    assert view("ca_seine_heat", "lesh")["hmode"] == "c"
    # отключённое правило не проверяется; изменённый порог меняет вывод
    rules = db.get("/signal-rules", headers=H("viewer")).json()["rules"]
    put = [{"code": r["code"], "enabled": r["enabled"], "values": r["values"]} for r in rules]
    for r in put:
        if r["code"] == "cohort_growth":
            r["enabled"] = False
        if r["code"] == "gears_disagree":
            r["values"] = {"ratio": 50}
    assert db.put("/signal-rules", headers=H("ichthyologist"), json={"rules": put}).status_code == 200
    T2 = {r["species"]: r for r in view("ca_trust")["trust"]["rows"]}
    assert T2["лещ"]["verdict"]["level"] == "ok" and "отключено" in T2["лещ"]["verdict"]["phrase"]
    assert not T2["сазан"]["gears"]["hit"] and not T2["окунь"]["gears"]["hit"] and T2["щука"]["verdict"]["level"] == "ok"
    assert T2["карась"]["verdict"]["level"] == "warning" and T2["карась"]["bounds"]["hit"]
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
    # невод не дал вида в одном году (Балхаш на сервере, 24.10.2026): сравнивать не с чем — «—», а не ошибка 500
    monkeypatch.setattr(cv, "_payload", real_payload)

    def seine_zero_2020(D, *a, **k):
        st, m = real_stock(D, *a, **k)
        st = copy.deepcopy(st)
        tot = st["species"]["лещ"]["variants"]["with_ages"]["on_stock"]["totals"][st["gears"]["seine"]]
        tot[st["years"].index(2020)] = 0
        return st, m
    monkeypatch.setattr(cv, "_stock", seine_zero_2020)
    T4 = {r["species"]: r for r in view("ca_trust", year=2020)["trust"]["rows"]}
    assert T4["лещ"]["gears"]["ratio"] is None and not T4["лещ"]["gears"]["hit"] and not T4["лещ"]["gears"]["one"]
    assert view("ca_passport")["rows"] and view("ca_z")["rows"]


def test_model_checks_views(tmp_path, monkeypatch):
    """Слайды «Проверки модели» по результату шага bayes_checks (форма — как у пакета; числа — таблица 17 статьи)."""
    mod = load_service("dashboards", tmp_path, monkeypatch)
    import importlib
    cv = importlib.import_module(mod.__package__ + ".calc_views")
    net_rows = [{"species": "лещ", "parameter": "база", "value": None, "rel_change": 0.0, "stock_factor": 1.0}]
    for par, vals in (("V, м/ч", (2.08, 1.35, 0.79, 0.66)), ("k", (1.83, 1.28, 0.83, 0.72)),
                      ("время стоянки, ч", (2.03, 1.34, 0.80, 0.66)), ("p_to_net", (2.09, 1.41, 0.73, 0.53))):
        rels = (-0.4, -0.2, 0.2, 0.4) if par == "p_to_net" else (-0.5, -0.25, 0.25, 0.5)
        net_rows += [{"species": "лещ", "parameter": par, "value": 1, "rel_change": r, "stock_factor": f} for r, f in zip(rels, vals)]
    comp = [{"variant": "σ × 2", "year": y, "median": 1.0, "median_base": 1.0, "median_ratio": r, "width_ratio": 1.0}
            for y, r in zip(range(2015, 2025), (1.0, 1.01, 1.02, 1.03, 1.04, 1.0, 1.0, 1.13, 1.57, 1.59))]
    pl = {"species": ["лещ"], "net": {"year": 2024, "rows": net_rows}, "year_max": 2021, "prior_factor": 2.0,
          "retro": {"лещ": {"forecast_years": [2022, 2023, 2024], "metrics": [
              {"subset": "непустые ловы", "n": 2590, "rmse_log": 3.62, "bias_log": 1.09, "coverage95": 0.72},
              {"subset": "доля пустых ловов", "n": 100, "zero_share_obs": 0.02, "zero_share_pred": 0.08, "zero_share_q025": 0.02, "zero_share_q975": 0.18}]}},
          "prior": {"лещ": comp}, "pad": {}, "recovery": {"лещ": {"truth_source": "медианы", "coverage": [
              {"quantity": "параметры", "n": 50, "coverage95": 0.88}]}},
          "runs": {"retro": {"лещ": {"rhat": 1.005, "ess_bulk": 1020, "ess_tail": 1315, "divergences": 0, "ebfmi": 0.86}}}}

    class D:
        lang = "ru"
        def run_payload(self, alg):
            return (pl, {"run_id": "r1"}) if alg == "bayes_checks" else (None, None)
        def sp_name(self, c):
            return {"lesh": "лещ"}.get(c, c)
    net = cv.v_bc_net(D(), {"species": "lesh"})
    v = {r["parameter"]: [r["f0"], r["f1"], r["f2"], r["f3"]] for r in net["rows"]}
    assert v["Скорость перемещения V"] == [2.08, 1.35, 0.79, 0.66] and v["Доля движущихся к сети"] == [2.09, 1.41, 0.73, 0.53]
    rt = cv.v_bc_retro(D(), {})["rows"][0]
    assert rt["n"] == 2590 and rt["cov"] == 0.72 and rt["z_pred"] == "0,08 (0,02–0,18)"
    pr = cv.v_bc_prior(D(), {})["rows"][0]
    assert pr["early"] == "1,00–1,04" and (pr["y0"], pr["y1"], pr["y2"]) == (1.13, 1.57, 1.59)
    import pytest
    with pytest.raises(cv.NoData):                         # проверка не выполнялась — понятное сообщение
        cv.v_bc_pad(D(), {})
    assert cv.v_bc_recovery(D(), {})["rows"][0]["cov"] == 0.88
    assert cv.v_bc_runs(D(), {})["rows"][0]["_level"] is None
