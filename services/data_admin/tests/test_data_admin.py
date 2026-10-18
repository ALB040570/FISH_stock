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
