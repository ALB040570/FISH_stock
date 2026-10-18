from conftest import H


def test_seed_and_records(svc):
    c = svc("data_model")
    ents = {e["code"]: e for e in c.get("/entities", headers=H("viewer")).json()}
    assert {"water_bodies", "species", "gears"} <= set(ents)
    assert ents["species"]["records_count"] == 11
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
