"""Сценарный анализ k (алгоритм j 3.1.0): слайды «Сценарии k по видам», «Сценарии k: ПДУ», «риск снижения запаса».

Нагрузка — в формате результата алгоритма forecast_pdu 3.1.0 (поля проверяет algorithms/tests/test_pipeline.py::
test_forecast_k_scenarios); здесь — что показывают представления.
"""
import importlib

import pytest

from conftest import load_service

KS = [0.5, 0.75, 1.0, 1.25, 1.5]


def _sp(code, pdu1, p_dec, npc, k_npc, side):
    return {"species": code, "code": code, "years_hist": list(range(2015, 2025)), "years_fc": list(range(2025, 2030)), "n_draws": 500,
            "k_scen": {"k": KS, "base_k": 1.0, "pdu_t_q": [[pdu1 * k * 0.6, pdu1 * k * 0.8, pdu1 * k, pdu1 * k * 1.2, pdu1 * k * 1.5] for k in KS],
                       "pdu_t_median_years": [[pdu1 * k] * 5 for k in KS], "F": [0.1 * k for k in KS],
                       "total_end_q": [[1e5, 2e5, 3e5 - 1e4 * i, 4e5, 5e5] for i in range(5)],
                       "p_decline": p_dec, "p_decline_none": 0.02, "k_npc": k_npc, "k_npc_side": side, "npc_last": npc}}


class D:
    lang = "ru"
    species = {"sazan": {"name_ru": "сазан"}, "lesh": {"name_ru": "лещ"}}

    def __init__(self, pl):
        self.pl = pl

    def sp_name(self, code):
        return self.species.get(code, {}).get("name_ru", code)

    def run_payload(self, algorithm):
        return (self.pl, {"calc_id": "c1"}) if algorithm == "forecast_pdu" else (None, None)


@pytest.fixture()
def cv(tmp_path, monkeypatch):
    mod = load_service("dashboards", tmp_path, monkeypatch)
    return importlib.import_module(mod.__package__ + ".calc_views")


def test_k_views(cv):
    pl = {"k": 1.0, "k_grid": KS, "species": {
        "сазан": _sp("sazan", 34.5, [0.0, 0.14, 0.56, 0.88, 0.97], 50.6, 1.47, None),
        "лещ": _sp("lesh", 36.4, [0.07, 0.09, 0.14, 0.19, 0.26], 804.0, 1.5, ">")}}
    d = D(pl)
    t = cv.VIEWS["fc_k_species"](d, {})
    assert [r["species"] for r in t["rows"]] == ["лещ", "сазан"]                       # по ПДУ при k = 1
    s = t["rows"][1]
    assert s["p0"] == pytest.approx(17.25) and s["p2"] == 34.5
    assert [round(s[k]) for k in ("d_lo", "d_base", "d_hi")] == [0, 56, 97]
    assert s["k_npc"] == "≈ 1,47" and t["rows"][0]["k_npc"] == "больше 1,5" and round(s["d_none"]) == 2
    titles = [c["title"] for c in t["columns"]]
    assert "ПДУ 2025, k = 0,5, т" in titles and "Снижение к 2029, k = 0,5, %" in titles and t["row_action"] == "species"
    g = cv.VIEWS["fc_k"](d, {"species": "sazan"})
    assert g["chart"]["x"] == ["0,5", "0,75", "1", "1,25", "1,5"] and g["chart"]["vrefs"][0]["x"] == "1"
    assert g["chart"]["lines"][0]["values"][2] == 34.5 and g["chart"]["lines"][1]["values"] == [50.6] * 5
    assert [round(r["pct"]) for r in g["rows"]] == [50, 75, 100, 125, 150] and g["rows"][2]["_current"]
    assert "ПДУ НПЦ соответствует k ≈ 1,47" in g["notes"][0]
    r = cv.VIEWS["fc_k_risk"](d, {"species": "sazan"})
    assert [round(v) for v in r["chart"]["series"][0]["values"]] == [0, 14, 56, 88, 97]
    assert [round(v) for v in r["chart"]["series"][1]["values"]] == [2] * 5
    # прогноз версии 3.0.0 — без сценариев k: понятное сообщение
    old = D({"k": 1.0, "species": {"сазан": {k: v for k, v in pl["species"]["сазан"].items() if k != "k_scen"}}})
    for v, o in (("fc_k_species", {}), ("fc_k", {"species": "sazan"}), ("fc_k_risk", {"species": "sazan"})):
        with pytest.raises(cv.NoData) as e:
            cv.VIEWS[v](old, o)
        assert "3.1.0" in e.value.message
