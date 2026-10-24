"""Вкладка «Запасы»: «Сходятся ли оценки запаса», доли убыли, поколения, структура, запас в тоннах.

Контрольный пример — docs/specs/stock_insights.md (Жайсан, 2024). Модель — сохранённые результаты нового эталона
(legacy/fish_stock_forecast/results/zhaysan_bayes_<вид>.npz), превращённые в нагрузку шага тем же кодом приложения
(fishcore.views.bayes_payload): числа детерминированы, в отличие от живого расчёта (±5 %).
"""
import copy
import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import H, load_service


def mod_process(mod):
    from importlib import import_module
    return import_module("app.worker").process_one(mod.E, mod.CLIENTS, log=lambda *a: None)

REPO = Path(__file__).resolve().parents[3]
ETALON = REPO / "legacy" / "fish_stock_forecast" / "results"
CODES = {"lesh": "лещ", "plotva": "плотва", "sazan": "сазан", "karas": "карась", "yaz": "язь", "sudak": "судак",
         "okun": "окунь", "shuka": "щука"}


def etalon_bayes_payload():
    sys.path.insert(0, str(REPO / "algorithms"))
    try:
        from fishcore.bayes.run import load_npz
        from fishcore import views
    finally:
        sys.path.remove(str(REPO / "algorithms"))
    out = {}
    for code, ru in CODES.items():
        a, meta = load_npz(ETALON / f"zhaysan_bayes_{code}.npz")
        out[ru] = views.bayes_payload(ru, a, meta, "etalon")
    return {"mode": "new", "species": out}


@pytest.fixture(scope="module")
def bayes_pl():
    if not (ETALON / "zhaysan_bayes_lesh.npz").exists():
        pytest.skip("нет результатов эталона")
    import json
    # через JSON — как нагрузка шага после записи в result.json
    return json.loads(json.dumps(etalon_bayes_payload(), default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def test_stock_insights(calc_stack, tmp_path, monkeypatch, bayes_pl):
    dm, da, aa, aa_mod = calc_stack
    c = aa.post("/calculations/from-template", headers=H("ichthyologist"), json={"water_body": "zhaysan", "template": "stock"}).json()
    aa.post(f"/calculations/{c['id']}/run", headers=H("ichthyologist"), json={})
    assert mod_process(aa_mod)
    mod = load_service("dashboards", tmp_path, monkeypatch)
    for k, cl in (("algo_admin", aa), ("data_admin", da), ("data_model", dm)):
        mod.SVC[k] = mod.Svc(k, http=cl)
    db = TestClient(mod.app)
    ins = importlib.import_module(mod.__package__ + ".insights")

    def view(name, sp=None, **flt):
        r = db.post("/widgets/data", headers=H("ichthyologist"), json={"source": {"kind": "insight", "view": name},
                                                                 "filters": {"water_body": "zhaysan", "species": sp, **flt}, "options": {}})
        assert r.status_code == 200, r.text
        return r.json()

    # только этапы 1–3: понятное сообщение, не ошибка; «запас в тоннах» по уловам работает и без модели
    assert "полный расчёт" in view("st_trust")["message"]
    bm = view("st_biomass", "lesh")
    assert [round(r["bio"]) for r in bm["rows"]][::9] == [9113, 16217] and bm["rows"][-1]["share"] == 27.7
    assert bm["rows"][-1]["quota"] == 4488 and "model" not in [c["code"] for c in bm["columns"]]

    real = ins.Data.run_payload
    state = {"pl": bayes_pl}

    def run_payload(self, algorithm):
        if algorithm == "bayes_cohort":
            _, meta = real(self, "stock_by_catch")
            return state["pl"], meta
        return real(self, algorithm)
    monkeypatch.setattr(ins.Data, "run_payload", run_payload)

    # ---- А. сводка: контрольный пример
    tr = view("st_trust")
    T = {r["species"]: r for r in tr["stock_trust"]["rows"]}
    assert tr["year"] == 2024 and tr["default_view"] == "stock_trust"
    assert [r["species"] for r in tr["stock_trust"]["rows"]] == ["лещ", "судак", "окунь", "плотва", "щука", "сазан", "карась", "язь"]
    assert tr["stock_trust"]["head"] == "Модели можно опираться у 2 из 8 видов"
    ctl = {  # вид: (модель ÷ уловы, модель ÷ НПЦ, изменение модели, по уловам, сходимость, вывод)
        "лещ": (2.70, 1.26, 2.54, 1.49, True, "Расходится с уловами"),
        "судак": (1.70, 1.22, 2.12, 1.06, False, "Модель не сошлась"),
        "окунь": (1.84, 1.14, 3.72, 2.10, True, "Можно опираться"),
        "плотва": (0.50, 0.28, 0.08, 0.08, True, "Расходится с НПЦ"),
        "щука": (0.52, 0.17, 0.34, 0.40, True, "Расходится с НПЦ"),
        "сазан": (0.20, 45.19, 1.12, 4.53, True, "Уловы, НПЦ, динамика"),
        "карась": (0.77, 1.73, 0.15, 0.16, True, "Можно опираться"),
        "язь": (0.24, 0.09, 0.27, 1.02, False, "Модель не сошлась")}
    for sp, (rc, rn, cm, cc, ok, lab) in ctl.items():
        r = T[sp]
        assert round(r["ratio"]["catch"], 2) == rc and round(r["ratio"]["npc"], 2) == rn, sp
        assert round(r["trend"]["model"], 2) == cm and round(r["trend"]["catch"], 2) == cc, sp
        assert r["conv"]["ok"] is ok and r["verdict"]["label"] == lab, sp
    assert T["язь"]["conv"]["text"] == "не сошлась" and T["язь"]["conv"]["detail"] == "R̂ 1,025 · ESS 192 / 456" and T["язь"]["conv"]["all"] == ["R̂ 1,025", "ESS 192 / 456"]
    assert T["судак"]["conv"]["all"] == ["R̂ 1,013", "ESS 362 / 107"]
    assert "не доверять" in T["язь"]["verdict"]["phrase"] and "НПЦ" not in T["язь"]["verdict"]["phrase"].split("убыли")[0]
    assert round(T["щука"]["fishing"]["pct"]) == 65 and round(T["лещ"]["fishing"]["pct"]) == 7
    assert "в 2,7 раза выше оценки по уловам" in T["лещ"]["verdict"]["phrase"] and "вылов — 7 % убыли" in T["лещ"]["verdict"]["phrase"]
    assert T["плотва"]["ratio"]["hit_c"] is False                       # 0,5022 — на границе, правило не сработало
    assert tr["explain"]["how"] and tr["explain"]["now"][0] == tr["stock_trust"]["head"]
    # первый год ряда: изменения нет
    t0 = {r["species"]: r for r in view("st_trust", year=2015)["stock_trust"]["rows"]}
    assert t0["лещ"]["trend"]["model"] is None and t0["лещ"]["trend"]["hit"] is False
    # порог из «Правил замечаний»: при 3× у леща расхождение с уловами (2,7×) уже не вопрос
    rules = db.get("/signal-rules", headers=H("ichthyologist")).json()["rules"]
    assert {r["code"] for r in rules} >= {"model_vs_catch", "model_vs_npc", "trend_vs_catch"}
    put = [{"code": r["code"], "enabled": r["enabled"], "values": {**r["values"], **({"ratio": 3} if r["code"] == "model_vs_catch" else {})}}
           for r in rules]
    assert db.put("/signal-rules", headers=H("ichthyologist"), json={"rules": put}).status_code == 200
    T3 = {r["species"]: r for r in view("st_trust")["stock_trust"]["rows"]}
    assert T3["лещ"]["verdict"]["label"] == "Можно опираться" and "3×" in view("st_trust")["stock_trust"]["thresholds"]
    # вид без модели — строка без цвета
    pl2 = copy.deepcopy(bayes_pl)
    pl2["species"]["карась"]["available"] = False
    state["pl"] = pl2
    T4 = {r["species"]: r for r in view("st_trust")["stock_trust"]["rows"]}
    assert T4["карась"].get("skipped") and T4["карась"]["verdict"]["level"] is None
    assert view("st_trust")["stock_trust"]["head"].endswith("из 7 видов")
    state["pl"] = bayes_pl

    # ---- Б. доли убыли
    d1 = view("by_deaths", "lesh")
    assert d1["chart"]["kind"] == "fit" and [t["value"] for t in d1["toggles"]] == ["pcs"]
    d2 = view("by_deaths", "lesh", dshare="share")
    assert d2["chart"]["kind"] == "series" and d2["chart"]["default"] == "stack100"
    last = d2["rows"][-1]
    assert abs(sum(last[k] for k in ("natural", "predators", "catch", "poaching") if last[k]) - 100) < 0.5
    assert round(last["fishing"]) == 7 and "медианам" in " ".join(d2["notes"])

    # ---- В. поколения: лещ — сильнейшее поколение 2022 г., ×7,0 медианы, в промысел (m0 = 4) — 2025
    co = view("by_cohorts", "lesh", year=2022)
    best = max(co["rows"], key=lambda r: r["x_med"] or 0)
    assert best["year"] == 2022 and best["x_med"] == 7.0 and best["entry"] == 2025
    assert co["chart"]["kind"] == "heatmap" and co["chart"]["fmt"] == "ratio"
    assert sum(1 for c in co["chart"]["cells"] if c[5]) == 3       # 2022, 2023, 2024 — три года поколения в ряду

    # ---- Г. структура: лещ — доля половозрелых по модели 53 → 32 %, по уловам 55 → 63 %; средний возраст 5,8 → 4,7
    sr = view("by_structure", "lesh")
    r0, r1 = sr["rows"][0], sr["rows"][-1]
    assert (round(r0["share_m"]), round(r1["share_m"])) == (53, 32) and (round(r0["share_c"]), round(r1["share_c"])) == (55, 63)
    assert round(r0["age_m"], 1) == 5.8 and abs(r1["age_m"] - 4.75) < 0.01
    tl = {t["label"]: t for t in sr["tiles"]}
    assert tl["Средний возраст половозрелых, модель"]["value"] == "4,7 года"
    sp_ = view("by_structure", "plotva")                            # m0 — первый возраст: только средний возраст
    assert "только средний возраст" in sp_["notes"][0]

    # ---- уловистость, идея 8: c по методике рядом с q модели — те же числа, без пересчёта
    cq = view("ca_q", "lesh")
    seine = db.post("/widgets/data", headers=H("ichthyologist"), json={"source": {"kind": "payload", "algorithm": "seine_catchability"},
                                                                "filters": {"water_body": "zhaysan"}, "options": {}}).json()["payload"]
    f = seine["fits"]["лещ"]["2024"]
    byage = {r["age"]: r for r in cq["rows"]}
    assert byage["1–2"]["c_s"] == f["c"][0] and byage["4–5"]["c_s"] == f["c"][f["ages"].index(5)]
    qq = bayes_pl["species"]["лещ"]["q_bias_q"]
    assert [r["q"] for r in cq["rows"]] == qq[2][:len(cq["rows"])]
    assert "решает математик" in cq["notes"][0] and cq["chart"]["kind"] == "band"
