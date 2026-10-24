from conftest import H


def test_seed_and_records(svc):
    c = svc("data_model")
    ents = {e["code"]: e for e in c.get("/entities", headers=H("viewer")).json()}
    assert {"water_bodies", "species", "gears"} <= set(ents)
    assert ents["species"]["records_count"] == 20
    fc = c.get("/water-bodies.geojson", headers=H("viewer")).json()
    codes = {f["properties"]["code"] for f in fc["features"]}
    assert {"zhaysan", "balkhash", "kapshagay", "alakol"} <= codes
    # наблюдатель не редактирует
    assert c.post("/entities/species/records", headers=H("viewer"), json={"values": {"code": "x", "name_ru": "x"}}).status_code == 403
    # ошибки проверки
    r = c.post("/entities/water_bodies/records", headers=H("ichthyologist"), json={"values": {"code": "test", "name_ru": "Тест", "type": "озеро", "point": "95, 10"}})
    assert r.status_code == 422 and "координаты" in str(r.json())
    r = c.post("/entities/water_bodies/records", headers=H("ichthyologist"), json={"values": {"code": "test", "name_ru": "Тест", "type": "озеро", "point": "48.1, 70.2"}})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]; assert r.json()["values"]["type"] == "lake"
    r = c.post("/entities/water_bodies/records", headers=H("ichthyologist"), json={"values": {"code": "test", "name_ru": "Тест2", "type": "lake", "point": "48, 70"}})
    assert r.status_code == 422  # код уникален
    r = c.put(f"/entities/water_bodies/records/{rid}", headers=H("ichthyologist"), json={"values": {"code": "test", "name_ru": "Тест-1", "type": "lake", "point": [48.1, 70.2], "area_km2": "12,5"}})
    assert r.status_code == 200 and r.json()["values"]["area_km2"] == 12.5
    vs = c.get(f"/entities/water_bodies/records/{rid}/versions", headers=H("viewer")).json()
    assert [v["n"] for v in vs] == [1, 2] and vs[0]["values"]["name_ru"] == "Тест"


def test_entity_constructor(svc):
    c = svc("data_model")
    body = {"code": "stations", "title_ru": "Станции", "fields": [
        {"code": "name", "title_ru": "Название", "type": "string", "required": True},
        {"code": "wb", "title_ru": "Водоём", "type": "ref", "ref_entity": "water_bodies"},
        {"code": "depth", "title_ru": "Глубина", "type": "number", "unit": "м", "min": 0}]}
    r = c.post("/entities", headers=H("ichthyologist"), json=body); assert r.status_code == 201, r.text
    r = c.post("/entities/stations/records", headers=H("ichthyologist"), json={"values": {"name": "С1", "wb": "Балхаш", "depth": -1}})
    assert r.status_code == 422
    r = c.post("/entities/stations/records", headers=H("ichthyologist"), json={"values": {"name": "С1", "wb": "Балхаш", "depth": 3}})
    assert r.status_code == 201 and r.json()["values"]["wb"] == "balkhash"
    # системные поля нельзя удалить
    sp = c.get("/entities/species", headers=H()).json()
    sp["fields"] = [f for f in sp["fields"] if f["code"] != "name_ru"]
    r = c.put("/entities/species", headers=H(), json={k: sp[k] for k in ("code", "title_ru", "title_kk", "description", "fields")})
    assert r.status_code == 422
    assert c.delete("/entities/species", headers=H()).status_code == 400
    bad = {"code": "Bad Code", "title_ru": "", "fields": [{"code": "x", "type": "zzz", "title_ru": "x"}]}
    assert c.post("/entities", headers=H(), json=bad).status_code == 422


def test_dtypes_and_geo(svc):
    c = svc("data_model")
    t = {x["code"] for x in c.get("/dataset-types", headers=H("viewer")).json()}
    assert {"catches", "age_samples", "mean_weights", "species_props", "yearly_conditions", "npc_stock", "npc_pdu"} <= t
    kml = b'<kml><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>70,48 71,48 71,49 70,49 70,48</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>'
    r = c.post("/geo/parse", headers=H("ichthyologist"), files={"file": ("a.kml", kml)})
    assert r.status_code == 200 and r.json()["shape"]["type"] == "Polygon"
    assert c.post("/geo/parse", headers=H("ichthyologist"), files={"file": ("a.json", b"{oops")}).status_code == 422


def test_regions_multi(svc):
    """Водоём в нескольких областях: справочник «Области», поле «Области» (несколько ссылок), фильтр."""
    c = svc("data_model")
    regs = c.get("/entities/regions/records", headers=H("viewer")).json()
    assert len(regs) == 20 and any(r["values"]["code"] == "ulytau" for r in regs)
    wb = next(r for r in c.get("/entities/water_bodies/records", headers=H()).json() if r["values"]["code"] == "balkhash")
    assert wb["values"]["regions"] == ["karaganda", "almaty_region", "zhambyl"]
    v = dict(wb["values"], regions="Карагандинская область; Жетісу облысы")      # названия, разделитель
    r = c.put(f"/entities/water_bodies/records/{wb['id']}", headers=H("ichthyologist"), json={"values": v})
    assert r.status_code == 200 and r.json()["values"]["regions"] == ["karaganda", "zhetysu"]
    v["regions"] = ["karaganda", "Луна"]
    r = c.put(f"/entities/water_bodies/records/{wb['id']}", headers=H("ichthyologist"), json={"values": v})
    assert r.status_code == 422 and "Луна" in str(r.json())
    gj = c.get("/water-bodies.geojson", headers=H()).json()
    f = next(x for x in gj["features"] if x["properties"]["code"] == "balkhash")
    assert f["properties"]["regions"] == ["karaganda", "zhetysu"]


def test_regions_migration(tmp_path, monkeypatch):
    """Установка до 21.10: строковое поле «Область» переводится в «Области»."""
    import json as _json
    from conftest import load_service
    mod = load_service("data_model", tmp_path, monkeypatch)
    # имитация старой схемы: поле region вместо regions, значение — строка
    e = mod.entities.get("water_bodies")
    old_fields = [dict(f, code="region", title_ru="Область", type="string", ref_entity=None) if f["code"] == "regions"
                  else f for f in e["fields"]]
    mod.entities.update("water_bodies", {"fields": old_fields}, actor="test")
    col = mod.records("water_bodies")
    for r in col.list():
        v = dict(r["values"])
        v.pop("regions", None)
        v["region"] = "Алматинская область" if v["code"] == "kapshagay" else "Жамбылская область"
        col.update(r["id"], {"values": v}, actor="test")
    mod._migrate_regions()
    fields = [f["code"] for f in mod.entities.get("water_bodies")["fields"]]
    assert "regions" in fields and "region" not in fields
    vals = {r["values"]["code"]: r["values"] for r in col.list()}
    assert vals["balkhash"]["regions"] == ["karaganda", "almaty_region", "zhambyl"]
    assert vals["kapshagay"]["regions"] == ["almaty_region"] and "region" not in vals["kapshagay"]
    assert _json.loads(col.read_version_file(next(r["id"] for r in col.list() if r["values"]["code"] == "alakol"),
                                             col.get(next(r["id"] for r in col.list()
                                                          if r["values"]["code"] == "alakol"))["current_version"],
                                             "record.json"))["regions"] == ["zhetysu", "abai"]


def test_tofi_classifiers(svc):
    """Справочники классификатора ТОФИ (21.10.2026): значения, коды ТОФИ, другие написания, ссылки."""
    c = svc("data_model")
    recs = lambda e: {r["values"]["code"]: r["values"] for r in c.get(f"/entities/{e}/records", headers=H()).json()}
    wt = recs("water_body_types")
    assert list(wt) == ["sea", "lake", "river", "reservoir", "pond", "dam", "channel"]
    assert wt["lake"]["tofi_code"] == "_FV_1002"
    assert set(recs("water_body_statuses")) == {"international", "republican", "local"}
    assert set(recs("water_body_origins")) == {"natural", "artificial"}
    assert len(recs("fishery_kinds")) == 4 and len(recs("fish_sexes")) == 3 and len(recs("forage_bases")) == 2
    fam = recs("fish_families")
    assert len(fam) == 16 and fam["osmeridae"]["name_ru"] == "Корюшковые"
    assert set(recs("gear_categories")) == {"commercial", "non_commercial"}
    # прежние значения «Типа лова» — другие написания справочника
    lk = c.get("/entities/catch_types/lookup", headers=H()).json()
    assert lk["научный"] == "scientific" and lk["научный лов"] == "scientific" and lk["промысловый"] == "commercial"
    sp = recs("species")
    assert len(sp) == 20 and {"elets", "karp", "rak"} <= set(sp)
    assert sp["sudak"]["family"] == "percidae" and sp["sudak"]["tofi_code"] == "_FV_1026"
    assert sp["rak"]["family"] is None and sp["b_amur"]["tofi_code"] == "_FV_1109"
    wbs = recs("water_bodies")
    assert wbs["zhaysan"]["type"] == "reservoir"
    e = c.get("/entities/water_bodies", headers=H()).json()
    f = {x["code"]: x for x in e["fields"]}
    assert f["type"]["type"] == "ref" and f["type"]["ref_entity"] == "water_body_types"
    assert f["fishery_kinds"]["type"] == "ref_list"
    # водоём с новыми свойствами; неизвестное значение — ошибка
    rid = next(r["id"] for r in c.get("/entities/water_bodies/records", headers=H()).json() if r["values"]["code"] == "zhaysan")
    v = dict(wbs["zhaysan"], origin="искусственный водоём", status="republican", fishery_kinds="промысловое рыболовство; amateur")
    r = c.put(f"/entities/water_bodies/records/{rid}", headers=H("mathematician"), json={"values": v}).json()
    assert r["values"]["origin"] == "artificial" and r["values"]["fishery_kinds"] == ["commercial", "amateur"]
    v["type"] = "болото"
    assert c.put(f"/entities/water_bodies/records/{rid}", headers=H(), json={"values": v}).status_code == 422
    # коды записей системных справочников менять нельзя
    cid = next(r["id"] for r in c.get("/entities/catch_types/records", headers=H()).json() if r["values"]["code"] == "sport")
    assert c.put(f"/entities/catch_types/records/{cid}", headers=H(),
                 json={"values": dict(recs("catch_types")["sport"], code="amateur")}).status_code == 400
    dt = c.get("/dataset-types/catches", headers=H()).json()
    cols = {x["code"]: x for x in dt["columns"]}
    assert cols["catch_type"]["type"] == "ref" and cols["place"]["places_entity"] == "fishing_places"


def test_tofi_upgrade_old_install(tmp_path, monkeypatch):
    """Установка до 21.10: вид водоёма и тип лова — списки значений, новых полей нет → обновление поставки."""
    from conftest import load_service
    mod = load_service("data_model", tmp_path, monkeypatch)
    e = mod.entities.get("water_bodies")
    old = [dict(f, type="enum", ref_entity=None, enum=[{"value": "lake"}, {"value": "reservoir"}])
           if f["code"] == "type" else f for f in e["fields"] if f["code"] not in ("origin", "status", "fishery_kinds")]
    old.append({"code": "my_field", "title_ru": "Моё поле", "type": "string", "system": False})
    mod.entities.update("water_bodies", {"fields": old}, actor="test")
    sp = mod.entities.get("species")
    mod.entities.update("species", {"fields": [f for f in sp["fields"] if f["code"] not in ("family", "tofi_code")]}, actor="t")
    col = mod.records("species")
    for r in col.list():
        v = {k: x for k, x in r["values"].items() if k not in ("family", "tofi_code")}
        if v["code"] == "som":
            v["family"] = "percidae"            # значение пользователя не перезаписывается
        col.update(r["id"], {"values": v}, actor="test")
    dt = mod.dtypes.get("catches")
    mod.dtypes.update("catches", {"columns": [dict(c, type="enum", enum=[{"value": "научный"}], places_entity=None)
                                              if c["code"] == "catch_type" else c for c in dt["columns"]]}, actor="t")
    g = mod.entities.get("gears")
    mod.entities.update("gears", {"fields": [dict(f, enum=[{"value": "seine", "title_ru": "Невод (метод площадей)"},
                                                           {"value": "net", "title_ru": "Сеть (балансовый метод)"}])
                                             if f["code"] == "kind" else f for f in g["fields"]]}, actor="t")
    n0 = mod.entities.get("water_bodies")["current_version"]
    mod._seed()
    kind = next(f for f in mod.entities.get("gears")["fields"] if f["code"] == "kind")
    assert kind["enum"][0]["title_ru"] == "Невод — активное орудие (метод площадей)"
    area = next(c for c in mod.dtypes.get("catches")["columns"] if c["code"] == "area_ha")
    assert area["only_for_gear_kind"] == "seine"
    wf = [f["code"] for f in mod.entities.get("water_bodies")["fields"]]
    assert {"origin", "status", "fishery_kinds"} <= set(wf) and wf[-1] == "my_field"
    assert next(f for f in mod.entities.get("water_bodies")["fields"] if f["code"] == "type")["type"] == "ref"
    assert mod.entities.get("water_bodies")["current_version"] == n0 + 1
    vals = {r["values"]["code"]: r["values"] for r in col.list()}
    assert vals["sudak"]["family"] == "percidae" and vals["sudak"]["tofi_code"] == "_FV_1026"
    assert vals["som"]["family"] == "percidae"
    assert next(c for c in mod.dtypes.get("catches")["columns"] if c["code"] == "catch_type")["type"] == "ref"
    # повторный запуск ничего не меняет
    mod._seed()
    assert mod.entities.get("water_bodies")["current_version"] == n0 + 1


def test_organizations(tmp_path, monkeypatch):
    """Справочник «Организации» (24.10.2026): пустой, появляется и в работающей установке, читают все."""
    import shutil
    from conftest import load_service
    mod = load_service("data_model", tmp_path, monkeypatch)
    assert mod.entities.exists("organizations") and mod.records("organizations").list() == []
    # установка до 24.10: справочника нет → создаётся при запуске, остальное не трогается
    shutil.rmtree(mod.entities.obj_dir("organizations"))
    assert not mod.entities.exists("organizations")
    n0 = mod.entities.get("water_bodies")["current_version"]
    mod._seed()
    assert mod.entities.exists("organizations")
    assert mod.entities.get("water_bodies")["current_version"] == n0
    from fastapi.testclient import TestClient
    from conftest import H
    c = TestClient(mod.app)
    org = {"code": "test_org", "name_ru": "Тестовая организация (для теста)"}   # синтетические данные
    assert c.post("/entities/organizations/records", headers=H("viewer"), json={"values": org}).status_code == 403
    assert c.post("/entities/organizations/records", headers=H("admin"), json={"values": org}).status_code == 201
    rows = c.get("/entities/organizations/records", headers=H("operator")).json()
    assert [r["values"]["code"] for r in (rows["items"] if isinstance(rows, dict) else rows)] == ["test_org"]
