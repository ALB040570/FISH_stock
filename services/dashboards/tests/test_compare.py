"""Страница «Сравнение расчётов» (кабинет «Мониторинг», решение № 77): API сервиса дашбордов.

Результаты расчётов — синтетические, в формате алгоритмов forecast_pdu 3.2.0 / 3.1.0, bayes_cohort и combined_stock
(поля проверяют тесты алгоритмов); здесь — что отдаёт сравнение и кому.
"""
import pytest
from fastapi.testclient import TestClient

from conftest import H, load_service

YH, YF = list(range(2015, 2025)), list(range(2025, 2030))
QF = (0.6, 0.8, 1.0, 1.2, 1.5)
HQ = [[1e5 * (j + 1) * f for j in range(10)] for f in QF]
KS = [0.0, 0.5, 1.0, 2.0]


def _traj(k):
    return [[1e6 * (1 - 0.1 * k * h) * f for h in range(5)] for f in QF]


def _fc_species(code, full=True, k_base=1.0):
    none_q, bar_q = _traj(0.0), _traj(k_base)
    R = {"species": code, "code": code, "available": True, "years_hist": YH, "years_fc": YF, "n_draws": 500,
         "hist": {"total_q": HQ, "fishable_q": [[v / 1e3 for v in r] for r in HQ], "total_last_draws_q": [r[-1] * 1.01 for r in HQ]},
         "scenarios": {"none": {"total_q": none_q, "fishable_q": [[v / 1e3 for v in r] for r in none_q], "p_decline": 0.02},
                       "baranov": {"total_q": bar_q, "fishable_q": [[v / 1e3 for v in r] for r in bar_q],
                                   "pdu_t_q": [[30 * f] * 5 for f in QF], "p_decline": 0.4}},
         "F_q": [[0.2 * f] * 5 for f in QF], "settings": {"k": k_base}}
    K = {"k": KS, "base_k": 1.0, "pdu_t_q": [[30 * k * f for f in QF] for k in KS], "pdu_t_median_years": [[30 * k] * 5 for k in KS],
         "F": [0.2 * k for k in KS], "total_end_q": [[q[-1] for q in _traj(k)] for k in KS],
         "p_decline": [0.02, 0.2, 0.4, 0.9], "p_decline_none": 0.02}
    if full:
        K["total_q_years"] = [_traj(k) for k in KS]
        K["fishable_q_years"] = [[[v / 1e3 for v in r] for r in _traj(k)] for k in KS]
    else:
        K = {**K, "k": [0.5, 1.0, 1.5], "pdu_t_q": K["pdu_t_q"][1:], "F": K["F"][1:], "total_end_q": K["total_end_q"][1:],
             "p_decline": K["p_decline"][1:], "pdu_t_median_years": K["pdu_t_median_years"][1:]}
    R["k_scen"] = K
    return R


RESULTS = {
    "fc1": {"calc": {"id": "fc1", "title": "Прогноз — основной", "is_main": True, "water_body": "zhaysan"},
            "payload": {"k": 1.0, "k_grid": KS, "species": {"сазан": _fc_species("sazan"), "лещ": _fc_species("lesh")}}},
    "fc_old": {"calc": {"id": "fc_old", "title": "Прогноз 3.1.0", "is_main": False, "water_body": "zhaysan"},
               "payload": {"k": 1.0, "species": {"сазан": _fc_species("sazan", full=False)}}},
    "fc2": {"calc": {"id": "fc2", "title": "Прогноз Капчагай", "is_main": True, "water_body": "kapshagay"},
            "payload": {"k": 1.0, "k_grid": KS, "species": {"лещ": _fc_species("lesh")}}},
    "bm1": {"calc": {"id": "bm1", "title": "Модель", "is_main": True, "water_body": "zhaysan"},
            "payload": {"species": {"лещ": {"available": True, "years": YH, "total_obs_q": HQ}}}},
    "cs1": {"calc": {"id": "cs1", "title": "Запас по уловам", "is_main": True, "water_body": "zhaysan"}, "payload": {},
            "tables": {"tonnes": {"rows": [{"year": y, "species": "лещ", "gear": g, "stock": 1e5 * i + (1 if g == "невод" else 0),
                                            "tonnes_all": 50.0 * i, "tonnes_fishable": 20.0 * i}
                                           for i, y in enumerate(YH) for g in ("сеть", "невод", "сеть+невод")]}}},
}
CALCS = [
    {"id": "fc1", "algorithm": "forecast_pdu", "water_body": "zhaysan", "title": "Прогноз — основной", "is_main": True, "has_result": True,
     "result": {"finished_at": "2026-10-27T01:00:00", "version": "3.2.0"}},
    {"id": "fc_old", "algorithm": "forecast_pdu", "water_body": "zhaysan", "title": "Прогноз 3.1.0", "is_main": False, "has_result": True,
     "result": {"version": "3.1.0"}},
    {"id": "fc_new", "algorithm": "forecast_pdu", "water_body": "zhaysan", "title": "Не запускался", "has_result": False},
    {"id": "fc2", "algorithm": "forecast_pdu", "water_body": "kapshagay", "title": "Прогноз Капчагай", "is_main": True, "has_result": True,
     "result": {"version": "3.2.0"}},
    {"id": "bm1", "algorithm": "bayes_cohort", "water_body": "zhaysan", "title": "Модель", "is_main": True, "has_result": True, "result": {}},
    {"id": "bm_egg", "algorithm": "bayes_cohort", "water_body": "zhaysan", "title": "Подбор egg_scale", "has_result": True,
     "result": {"not_main": True}},
    {"id": "cs1", "algorithm": "combined_stock", "water_body": "zhaysan", "title": "Запас по уловам", "is_main": True, "has_result": True, "result": {}},
]
WBS = [{"values": {"code": "zhaysan", "name_ru": "Жайсан", "name_kk": "Зайсан"}}, {"values": {"code": "kapshagay", "name_ru": "Капчагай"}},
       {"values": {"code": "balkhash", "name_ru": "Балхаш"}}]
SPECIES = [{"values": {"code": "sazan", "name_ru": "сазан", "name_kk": "сазан"}}, {"values": {"code": "lesh", "name_ru": "лещ", "name_kk": "табан"}}]


class Fake:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def get(self, path, **params):
        self.calls.append(path)
        if self.name == "data_model":
            return {"/entities/water_bodies/records": WBS, "/entities/species/records": SPECIES}.get(path)
        if path == "/calcs":
            return [c for c in CALCS if c["algorithm"] == params.get("algorithm")
                    and (not params.get("water_body") or c["water_body"] == params["water_body"])]
        if path.startswith("/calcs/") and path.endswith("/result"):
            return RESULTS.get(path.split("/")[2])
        return None


@pytest.fixture()
def db(tmp_path, monkeypatch):
    mod = load_service("dashboards", tmp_path, monkeypatch)
    fakes = {k: Fake(k) for k in ("algo_admin", "data_admin", "data_model")}
    monkeypatch.setattr(mod, "SVC", fakes)
    return TestClient(mod.app), fakes


def _series(db, items, measure="total", role="ichthyologist", lang="ru"):
    r = db.post("/compare/series", headers=H(role), json={"series": items, "measure": measure, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()["series"]


def test_options_and_meta(db):
    c, _ = db
    o = c.get("/compare/options", headers=H("mathematician")).json()
    assert [w["code"] for w in o["water_bodies"]] == ["zhaysan", "kapshagay"]           # Балхаш — без расчётов
    assert [x["id"] for x in o["calcs"]["forecast"]] == ["fc2", "fc1", "fc_old"]       # по водоёму, основной первым
    assert [x["id"] for x in o["calcs"]["model"]] == ["bm1"]                            # служебный подбор egg_scale скрыт
    assert o["calcs"]["forecast"][1]["water_body_name"] == "Жайсан" and o["calcs"]["forecast"][1]["version"] == "3.2.0"
    m = c.get("/compare/meta", params={"ids": "fc1,fc_old", "source": "forecast"}, headers=H("admin")).json()
    assert m["fc1"]["k"] == KS and m["fc1"]["k_full"] and m["fc1"]["base_k"] == 1.0
    assert [s["code"] for s in m["fc1"]["species"]] == ["sazan", "lesh"] and m["fc1"]["species"][1]["name"] == "лещ"
    assert m["fc_old"]["k"] == [0.0, 1.0] and not m["fc_old"]["k_full"]                # 3.1.0: траектории — только k = 0 и k расчёта
    m = c.get("/compare/meta", params={"ids": "cs1", "source": "catch", "lang": "kk"}, headers=H("admin")).json()
    assert m["cs1"]["species"] == [{"code": "lesh", "name": "табан"}] and m["cs1"]["gears"] == ["сеть", "невод", "сеть+невод"]
    assert c.get("/compare/meta", params={"ids": "x", "source": "zzz"}, headers=H("admin")).status_code == 400


def test_forecast_series(db):
    c, fakes = db
    s = _series(c, [{"source": "forecast", "calc": "fc1", "species": "lesh", "k": 2},
                    {"source": "forecast", "calc": "fc1", "species": "lesh", "k": 0},
                    {"source": "forecast", "calc": "fc1", "species": "sazan", "k": 0.5}])
    a, z, b = s
    assert a["water_body_name"] == "Жайсан" and a["species_name"] == "лещ" and a["is_main"] and a["calc_title"] == "Прогноз — основной"
    assert a["years_hist"] == YH and a["years_fc"] == YF and a["hist_q"] == HQ
    assert a["fc_q"] == _traj(2.0) and a["join_q"] == [r[-1] * 1.01 for r in HQ]      # прогноз продолжает последний год истории
    assert a["pdu_years"] == [60.0] * 5 and a["pdu1_q"] == [60 * f for f in QF] and a["risk"] == 0.9 and a["F"] == 0.4
    assert a["end_q"] == [q[-1] for q in _traj(2.0)]
    assert z["fc_q"] == _traj(0.0) and z["pdu_years"] == [0.0] * 5 and z["F"] == 0.0
    assert b["fc_q"] == _traj(0.5) and b["species_name"] == "сазан"
    assert sum(p.endswith("/result") for p in fakes["algo_admin"].calls) == 1           # результат читается один раз
    f = _series(c, [{"source": "forecast", "calc": "fc1", "species": "lesh", "k": 2}], measure="fishable")[0]
    assert f["fc_q"] == [[v / 1e3 for v in r] for r in _traj(2.0)] and f["join_q"] == [r[-1] / 1e3 for r in HQ]


def test_forecast_old_version(db):
    c, _ = db
    z, base, mid = _series(c, [{"source": "forecast", "calc": "fc_old", "species": "sazan", "k": 0},
                               {"source": "forecast", "calc": "fc_old", "species": "sazan", "k": 1},
                               {"source": "forecast", "calc": "fc_old", "species": "sazan", "k": 0.5}])
    assert z["fc_q"] == _traj(0.0) and z["risk"] == 0.02                                 # k = 0 — сценарий «без промысла»
    assert base["fc_q"] == _traj(1.0) and base["pdu1_q"] == [30 * f for f in QF] and base["F"] == pytest.approx(0.2)
    assert "3.2.0" in mid["error"]                                                        # траекторий других k нет


def test_model_catch_and_errors(db):
    c, _ = db
    m, g, n, bad_sp, bad_calc, fm = _series(c, [
        {"source": "model", "calc": "bm1", "species": "lesh"},
        {"source": "catch", "calc": "cs1", "species": "lesh", "gear": "невод"},
        {"source": "catch", "calc": "cs1", "species": "lesh", "gear": "что-то"},
        {"source": "forecast", "calc": "fc2", "species": "sazan", "k": 1},
        {"source": "forecast", "calc": "nope", "species": "lesh"},
        {"source": "model", "calc": "bm1", "species": "lesh"}])
    assert m["hist_q"] == HQ and m["years_fc"] == [] and m["fc_q"] is None and "error" not in m
    assert g["gear"] == "невод" and g["hist_q"] == [[1e5 * i + 1 for i in range(10)]]
    assert n["gear"] == "сеть+невод" and n["hist_q"] == [[1e5 * i for i in range(10)]]     # неизвестное орудие → оба орудия
    assert "нет такого вида" in bad_sp["error"] and "не найден" in bad_calc["error"]
    t = _series(c, [{"source": "catch", "calc": "cs1", "species": "lesh", "gear": "сеть"},
                    {"source": "model", "calc": "bm1", "species": "lesh"}], measure="fishable")
    assert t[0]["hist_q"] == [[20.0 * i for i in range(10)]] and "численность" in t[1]["error"]
    kk = _series(c, [{"source": "model", "calc": "bm1", "species": "lesh"}], lang="kk")[0]
    assert kk["species_name"] == "табан"
    r = c.post("/compare/series", headers=H("admin"), json={"series": [{"source": "model", "calc": "bm1", "species": "lesh"}] * 13})
    assert r.status_code == 400


@pytest.mark.parametrize("role,code", [("admin", 200), ("mathematician", 200), ("ichthyologist", 200),
                                       ("viewer", 403), ("operator", 403), ("presenter", 403)])
def test_access(db, role, code):
    c, _ = db
    assert c.get("/compare/options", headers=H(role)).status_code == code
    assert c.get("/compare/meta", params={"ids": "fc1"}, headers=H(role)).status_code == code
    assert c.post("/compare/series", headers=H(role), json={"series": []}).status_code == code
