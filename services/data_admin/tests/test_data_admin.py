import io
from pathlib import Path

from openpyxl import load_workbook

from conftest import H, REPO

SAMPLES = REPO / "samples" / "zhaysan"
TYPES = ["catches", "age_samples", "mean_weights", "species_props", "yearly_conditions", "npc_stock", "npc_pdu"]


def up(da, dtype, content, role="ichthyologist", **form):
    data = {"water_body": "zhaysan", "dataset_type": dtype, "mode": "merge", **form}
    return da.post("/upload", headers=H(role), data=data, files={"file": (f"{dtype}.xlsx", content)})


def test_upload_all_samples(data_stack):
    dm, da, _ = data_stack
    for t in TYPES:
        r = up(da, t, (SAMPLES / f"{t}.xlsx").read_bytes())
        assert r.status_code == 200, r.text
        j = r.json(); assert j["ok"], (t, j["errors"][:3])
        assert j["version"] == 1
    st = da.get("/water-bodies/status", headers=H("viewer")).json()["zhaysan"]
    assert set(st["datasets"]) == set(TYPES) and st["years"][0] == 2015 and st["years"][-1] == 2024
    ds = st["datasets"]["catches"]["id"]
    tab = da.get(f"/datasets/{ds}/data", headers=H("viewer")).json()["table"]
    assert len(tab["rows"]) == 690
    r0 = tab["rows"][0]
    assert r0["gear"] in ("seine", "net") and r0["date"].count("-") == 2
    # пропуск остаётся пропуском
    assert any(r["sazan"] is None for r in tab["rows"]) and any(r["sazan"] == 0 for r in tab["rows"])
    # наблюдатель не загружает
    assert up(da, "npc_pdu", (SAMPLES / "npc_pdu.xlsx").read_bytes(), role="viewer").status_code == 403


def _broken_catches():
    wb = load_workbook(SAMPLES / "catches.xlsx")
    ws = wb["Данные"]
    ws["A2"] = "две тысячи"        # год не число
    ws["D3"] = "трал"              # нет в справочнике орудий
    ws["I4"] = -5                  # отрицательный улов (первый столбец вида)
    ws["B5"] = "31.02.2015"        # несуществующая дата
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_errors_are_explained(data_stack):
    dm, da, _ = data_stack
    r = up(da, "catches", _broken_catches()).json()
    assert not r["ok"] and r["errors_total"] >= 4
    msgs = " | ".join(e["message"] for e in r["errors"])
    assert "нужно целое число" in msgs and "нет в справочнике" in msgs and "меньше допустимого" in msgs and "ДД.ММ.ГГГГ" in msgs
    rows = {e["row"] for e in r["errors"]}
    assert {2, 3, 4, 5} <= rows
    # не тот файл / не Excel
    r = up(da, "catches", b"not excel").json()
    assert not r["ok"] and "Excel" in r["errors"][0]["message"]
    # чужой столбец и нет обязательного
    r = up(da, "npc_pdu", (SAMPLES / "species_props.xlsx").read_bytes()).json()
    assert not r["ok"] and any("Нет обязательного столбца" in e["message"] for e in r["errors"])
    # повтор ключа и правило m0 <= m1
    wb = load_workbook(SAMPLES / "species_props.xlsx"); ws = wb["Данные"]
    ws["B3"] = 30; ws["A4"] = ws["A2"].value
    buf = io.BytesIO(); wb.save(buf)
    r = up(da, "species_props", buf.getvalue()).json()
    msgs = " | ".join(e["message"] for e in r["errors"])
    assert "m0 не может быть больше m1" in msgs and "Повтор строки" in msgs


def test_edit_versions_diff(data_stack):
    dm, da, _ = data_stack
    j = up(da, "npc_pdu", (SAMPLES / "npc_pdu.xlsx").read_bytes()).json()
    ds = j["dataset"]["id"]
    tab = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]
    rows = tab["rows"]; rows[0]["lesh"] = 3600; rows.append({"year": 2025, "lesh": 4000})
    r = da.put(f"/datasets/{ds}/data", headers=H("ichthyologist"), json={"rows": rows, "comment": "правка", "base_version": 1}).json()
    assert r["ok"] and r["version"] == 2
    # конфликт версий
    assert da.put(f"/datasets/{ds}/data", headers=H("ichthyologist"), json={"rows": rows, "base_version": 1}).status_code == 409
    d = da.get(f"/datasets/{ds}/diff?a=1&b=2", headers=H()).json()
    assert len(d["added"]) == 1 and d["changed"][0]["key"] == {"year": 2015}
    assert d["changed"][0]["cells"] == [{"field": "lesh", "old": 3597, "new": 3600}]
    # ошибка правки не создаёт версию
    rows[1]["lesh"] = "много"
    r = da.put(f"/datasets/{ds}/data", headers=H("ichthyologist"), json={"rows": rows}).json()
    assert not r["ok"] and da.get(f"/datasets/{ds}", headers=H()).json()["current_version"] == 2
    # восстановление и история
    da.post(f"/datasets/{ds}/restore/1", headers=H("ichthyologist"))
    vs = da.get(f"/datasets/{ds}/versions", headers=H()).json()
    assert [v["n"] for v in vs] == [3, 2, 1] and vs[0]["origin"] == "restore:1"
    # merge: файл с одним годом заменяет только этот год
    x = da.get(f"/datasets/{ds}/export.xlsx?version=2", headers=H()).content
    wb = load_workbook(io.BytesIO(x)); ws = wb["Данные"]
    for _ in range(ws.max_row - 2):
        ws.delete_rows(3)
    ws["B2"] = 9999
    buf = io.BytesIO(); wb.save(buf)
    r = da.post(f"/datasets/{ds}/upload", headers=H("ichthyologist"), data={"mode": "merge"}, files={"file": ("x.xlsx", buf.getvalue())}).json()
    assert r["ok"] and r["summary"]["rows"] == 10
    tab = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]
    assert [x["lesh"] for x in tab["rows"] if x["year"] == 2015] == [9999]


def test_template(data_stack):
    dm, da, _ = data_stack
    r = da.get("/templates/catches.xlsx?species=lesh,sudak", headers=H("viewer"))
    wb = load_workbook(io.BytesIO(r.content))
    head = [c.value for c in wb["Данные"][1]]
    assert head[0] == "Год *" and head[-2:] == ["лещ", "судак"] and "Описание" in wb.sheetnames
    r = up(da, "catches", r.content).json()
    assert not r["ok"] and "нет строк" in r["errors"][0]["message"]


def test_catch_types_and_places(data_stack):
    """Тип лова — коды справочника «Типы вылова»; место лова сверяется со справочником мест водоёма."""
    dm, da, mod = data_stack
    content = (SAMPLES / "catches.xlsx").read_bytes()
    j = up(da, "catches", content).json()
    assert j["ok"]
    assert any("ещё нет мест" in w["message"] for w in j["warnings"])
    ds = j["dataset"]["id"]
    rows = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]["rows"]
    assert {r["catch_type"] for r in rows} <= {"scientific", "commercial"}
    # ихтиолог не правит справочник
    assert da.post("/fishing-places/collect", headers=H("viewer")).status_code == 403
    r = da.post("/fishing-places/collect", headers=H("mathematician")).json()
    places = {p["name_ru"]: p for p in r["places"]}
    assert places["м. Волчий"]["aliases"] == ["м.Волчий"]           # отличие только пробелом — одно место
    assert "Тополев мыс" in places and "м. Тополев" in places      # разные написания — до подтверждения раздельно
    assert all(p["water_body"] == "zhaysan" for p in r["places"])
    assert da.post("/fishing-places/collect", headers=H("mathematician")).json()["created"] == 0
    # подтверждённое другое написание: «Тополев мыс» → «м. Тополев»
    recs = dm.get("/entities/fishing_places/records", headers=H()).json()
    top = next(x for x in recs if x["values"]["name_ru"] == "м. Тополев")
    dup = next(x for x in recs if x["values"]["name_ru"] == "Тополев мыс")
    dm.delete(f"/entities/fishing_places/records/{dup['id']}", headers=H())
    v = dict(top["values"], aliases=(top["values"]["aliases"] or "") + "\nТополев мыс")
    assert dm.put(f"/entities/fishing_places/records/{top['id']}", headers=H(), json={"values": v}).status_code == 200
    j = up(da, "catches", content, mode="replace").json()
    assert j["ok"] and not [w for w in j["warnings"] if w["field"] == "place"]
    rows = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]["rows"]
    names = {r["place"] for r in rows}
    assert "Тополев мыс" not in names and "м.Волчий" not in names and "м. Тополев" in names
    # неизвестное место — предупреждение, не ошибка
    wb = load_workbook(SAMPLES / "catches.xlsx"); ws = wb["Данные"]
    ws["C2"] = "Новое место"; ws["C3"] = "Новое место"
    buf = io.BytesIO(); wb.save(buf)
    j = up(da, "catches", buf.getvalue(), dry_run="true").json()
    assert j["ok"]
    w = [x for x in j["warnings"] if x["field"] == "place"]
    assert len(w) == 1 and "Новое место" in w[0]["message"] and "строк: 2" in w[0]["message"]
    # тип лова — по справочнику
    ws["H2"] = "трал"
    buf = io.BytesIO(); wb.save(buf)
    j = up(da, "catches", buf.getvalue(), dry_run="true").json()
    assert not j["ok"] and any(e["field"] == "catch_type" for e in j["errors"])


def test_catch_types_migration(data_stack):
    """Наборы уловов до 21.10: «научный»/«промысловый» → коды справочника, новой версией."""
    import json as _json
    from fishcommon.storage import dumps
    dm, da, mod = data_stack
    j = up(da, "catches", (SAMPLES / "catches.xlsx").read_bytes()).json()
    ds = j["dataset"]["id"]
    tab = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]
    for r in tab["rows"]:
        r["catch_type"] = {"scientific": "научный", "commercial": "промысловый"}[r["catch_type"]]
    mod.datasets.add_version(ds, {"data.json": dumps(tab).encode()}, {"comment": "старая версия"}, "test")
    before = mod.datasets.get(ds)["updated_at"]
    mod._migrate_catch_types()
    d = mod.datasets.get(ds)
    assert d["current_version"] == 3 and d["updated_at"] == before      # данные не «изменились после расчёта»
    new = _json.loads(mod.datasets.read_version_file(ds, 3, "data.json"))
    assert {r["catch_type"] for r in new["rows"]} == {"scientific", "commercial"}
    assert [r["place"] for r in new["rows"]] == [r["place"] for r in tab["rows"]]
    mod._migrate_catch_types()
    assert mod.datasets.get(ds)["current_version"] == 3
    # восстановление старой версии приводит значения к кодам
    da.post(f"/datasets/{ds}/restore/2", headers=H())
    rows = da.get(f"/datasets/{ds}/data", headers=H()).json()["table"]["rows"]
    assert {r["catch_type"] for r in rows} == {"scientific", "commercial"}
