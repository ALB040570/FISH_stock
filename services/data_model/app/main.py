"""
Сервис 5. Моделирование данных (справочник).

Конструктор сущностей справочников (поля, типы, единицы, обязательность), записи справочников
(водоёмы с геометрией, виды рыб, орудия лова и любые новые) и типы наборов данных — схемы таблиц,
по которым сервис «Входные данные» строит Excel-шаблоны и проверяет загрузки.
Каждое изменение схемы или записи — новая версия.
"""
from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import Depends, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, current_user, require
from fishcommon.errors import AppError, not_found
from fishcommon.schema import TYPE_TITLES, TYPES, CODE_RE, coerce, validate_field_def, validate_record
from fishcommon.storage import Collection, dumps, read_json

from . import seed_defs

app = create_app("data_model", "Моделирование данных (справочник)",
                 "Конструктор справочников, водоёмы, виды, орудия лова, типы наборов данных.")
ST = app.state.settings
ROOT = ST.service_dir()
SEED_DIR = Path(__file__).parent / "seed"
entities = Collection(ROOT, "entities")
dtypes = Collection(ROOT, "dataset_types")


def records(code: str) -> Collection:
    return Collection(ROOT / "records", code)


def audit(user, action, otype, oid, details=None):
    app.state.audit.log(user, action, otype, oid, details)


# ------------------------------------------------------------------ начальное наполнение
def _seed() -> None:
    for e in seed_defs.ENTITIES:
        if not entities.exists(e["code"]):
            entities.create(copy.deepcopy(e), actor="system", obj_id=e["code"])
            entities.add_version(e["code"], {"schema.json": dumps(e).encode()}, {"comment": "начальная версия"}, "system")
    for t in seed_defs.DATASET_TYPES:
        if not dtypes.exists(t["code"]):
            dtypes.create(copy.deepcopy(t), actor="system", obj_id=t["code"])
            dtypes.add_version(t["code"], {"schema.json": dumps(t).encode()}, {"comment": "начальная версия"}, "system")
    # системные записи добавляются по коду, если их ещё нет (в том числе удалённых) —
    # так новые виды и водоёмы появляются и в уже работающей установке
    def have(entity):
        return {r["values"].get("code") for r in records(entity).list()}

    for ent, rows in seed_defs.CLASSIFIERS.items():
        got = have(ent)
        for code, ru, kk, tofi in rows:
            if code not in got:
                vals = {"code": code, "name_ru": ru, "name_kk": kk, "tofi_code": tofi}
                if seed_defs.CLASSIFIER_ALIASES.get((ent, code)):
                    vals["aliases"] = seed_defs.CLASSIFIER_ALIASES[(ent, code)]
                _create_record(ent, vals, "system")
    fam = have("fish_families")
    for code, ru, kk, tofi in seed_defs.FAMILIES:
        if code not in fam:
            _create_record("fish_families", {"code": code, "name_ru": ru, "name_kk": kk, "tofi_code": tofi}, "system")

    rg = have("regions")
    for code, ru, kk in seed_defs.REGIONS:
        if code not in rg:
            _create_record("regions", {"code": code, "name_ru": ru, "name_kk": kk}, "system")
    _migrate_regions()
    _upgrade_schemas()

    sp = have("species")
    for code, ru, kk, latin, pred in seed_defs.SPECIES:
        if code not in sp:
            _create_record("species", {"code": code, "name_ru": ru, "name_kk": kk, "latin": latin,
                                       "family": seed_defs.SPECIES_FAMILY.get(code),
                                       "is_predator": pred, "tofi_code": seed_defs.SPECIES_TOFI.get(code)}, "system")
    _fill_missing("species", lambda v: {"family": seed_defs.SPECIES_FAMILY.get(v.get("code")),
                                        "tofi_code": seed_defs.SPECIES_TOFI.get(v.get("code"))},
                  "семейство и код ТОФИ (классификатор ТОФИ)")
    gr = have("gears")
    for code, ru, kk, kind in seed_defs.GEARS:
        if code not in gr:
            _create_record("gears", {"code": code, "name_ru": ru, "name_kk": kk, "kind": kind}, "system")
    wbs = have("water_bodies")
    fc = json.loads((SEED_DIR / "water_bodies.geojson").read_text(encoding="utf-8"))
    for f in fc["features"]:
        p = f["properties"]
        if p.get("code") in wbs:
            continue
        vals = {k: p.get(k) for k in ("code", "name_ru", "name_kk", "type", "area_km2", "point", "note")}
        vals["regions"] = seed_defs.regions_for(p.get("code"), p.get("region"))
        vals["shape"] = f.get("geometry")
        vals["basin"] = None
        _create_record("water_bodies", vals, "system", source=p.get("source"))


def _migrate_regions() -> None:
    """Установки до 21.10.2026: поле «Область» (строка) → «Области» (несколько ссылок на справочник областей)."""
    e = entities.get("water_bodies")
    if not e or any(f["code"] == "regions" for f in e["fields"]):
        return
    new_field = next(f for d in seed_defs.ENTITIES if d["code"] == "water_bodies" for f in d["fields"]
                     if f["code"] == "regions")
    fields, placed = [], False
    for f in e["fields"]:
        if f["code"] == "region":
            fields.append(copy.deepcopy(new_field))
            placed = True
        else:
            fields.append(f)
    if not placed:
        fields.append(copy.deepcopy(new_field))
    d = {**e, "fields": fields}
    entities.update("water_bodies", {"fields": fields}, actor="system")
    entities.add_version("water_bodies", {"schema.json": dumps(d).encode()},
                         {"comment": "области: несколько значений из справочника «Области» (деление 2022 г.)"}, "system")
    col = records("water_bodies")
    for r in col.list():
        v = dict(r.get("values", {}))
        old = v.pop("region", None)
        v["regions"] = seed_defs.regions_for(v.get("code"), old) or None
        col.update(r["id"], {"values": v}, actor="system")
        col.add_version(r["id"], {"record.json": dumps(v).encode()},
                        {"comment": f"области: «{old or '—'}» → {', '.join(v['regions'] or []) or '—'}"}, "system")


def _sig(f: dict) -> tuple:
    return f.get("type"), f.get("ref_entity"), f.get("places_entity")


def _upgrade_fields(old: list[dict], seed: list[dict]) -> tuple[list[dict], list[str]]:
    """Поля поставки, которых нет в установке, добавляются; поле поставки со сменившимся типом или
    ссылкой заменяется описанием поставки. Поля, добавленные пользователем, остаются в конце."""
    by = {f["code"]: f for f in old}
    out, notes = [], []
    for sf in seed:
        of = by.get(sf["code"])
        if of is None:
            out.append(copy.deepcopy(sf))
            notes.append(f"+{sf['code']}")
        elif _sig(of) != _sig(sf):
            out.append(copy.deepcopy(sf))
            notes.append(f"{sf['code']}: {of.get('type')} → {sf.get('type')}")
        else:
            out.append(of)
    seed_codes = {f["code"] for f in seed}
    out += [f for f in old if f["code"] not in seed_codes]
    return out, notes


def _upgrade_schemas() -> None:
    """Установки до 21.10.2026: справочники классификатора ТОФИ — новые поля и ссылки вместо списков."""
    for sd in seed_defs.ENTITIES:
        e = entities.get(sd["code"])
        if not e:
            continue
        fields, notes = _upgrade_fields(e["fields"], sd["fields"])
        if notes:
            d = {**e, "fields": fields}
            entities.update(sd["code"], {"fields": fields}, actor="system")
            entities.add_version(sd["code"], {"schema.json": dumps(d).encode()},
                                 {"comment": "обновление поставки (классификатор ТОФИ): " + ", ".join(notes)}, "system")
    for sd in seed_defs.DATASET_TYPES:
        t = dtypes.get(sd["code"])
        if not t:
            continue
        cols, notes = _upgrade_fields(t["columns"], sd["columns"])
        if notes:
            d = {**t, "columns": cols}
            dtypes.update(sd["code"], {"columns": cols}, actor="system")
            dtypes.add_version(sd["code"], {"schema.json": dumps(d).encode()},
                               {"comment": "обновление поставки: " + ", ".join(notes)}, "system")


def _fill_missing(entity: str, make, comment: str) -> None:
    """Заполнить у системных записей новые поля, которых в записи ещё нет (значения пользователя не трогаются)."""
    col = records(entity)
    for r in col.list():
        if r.get("deleted"):
            continue
        v = dict(r.get("values", {}))
        add = {k: x for k, x in make(v).items() if k not in v and x is not None}
        if not add:
            continue
        v.update(add)
        col.update(r["id"], {"values": v}, actor="system")
        col.add_version(r["id"], {"record.json": dumps(v).encode()}, {"comment": comment}, "system")


# ------------------------------------------------------------------ сущности
class EntityIn(BaseModel):
    code: str
    title_ru: str
    title_kk: str = ""
    description: str = ""
    display_field: str | None = None
    fields: list[dict]
    comment: str = ""


def _entity(code: str) -> dict:
    e = entities.get(code)
    if not e or e.get("deleted"):
        raise not_found("Справочник")
    return e


def _check_entity_def(body: dict, old: dict | None) -> None:
    errs = []
    if not CODE_RE.match(body["code"]):
        errs.append("Код справочника: латинские строчные буквы, цифры и _")
    if not body["title_ru"].strip():
        errs.append("Нужно название справочника на русском")
    codes = [f.get("code") for f in body["fields"]]
    if len(codes) != len(set(codes)):
        errs.append("Коды полей повторяются")
    if not body["fields"]:
        errs.append("Нужно хотя бы одно поле")
    for f in body["fields"]:
        errs += validate_field_def(f)
        if f.get("type") in ("ref", "ref_list") and f.get("ref_entity") and not entities.exists(f["ref_entity"]) \
                and f["ref_entity"] != body["code"]:
            errs.append(f"Поле «{f.get('code')}»: справочник «{f['ref_entity']}» не найден")
    if old:
        new_by = {f["code"]: f for f in body["fields"]}
        for f in old["fields"]:
            if f.get("system"):
                nf = new_by.get(f["code"])
                if nf is None:
                    errs.append(f"Системное поле «{f['code']}» используется расчётами — его нельзя удалить")
                elif nf.get("type") != f.get("type"):
                    errs.append(f"Системному полю «{f['code']}» нельзя менять тип")
                else:
                    nf["system"] = True
    if errs:
        raise AppError("schema.invalid", "Описание справочника содержит ошибки", 422, errs)


@app.get("/field-types", tags=["справочники"])
def field_types(user: User = Depends(current_user)):
    return [{"code": t, "title": TYPE_TITLES[t]} for t in TYPES]


@app.get("/entities", tags=["справочники"])
def list_entities(user: User = Depends(require("dict.view"))):
    out = []
    for e in entities.list():
        if e.get("deleted"):
            continue
        out.append({**e, "records_count": sum(1 for r in records(e["code"]).list() if not r.get("deleted"))})
    return out


@app.get("/entities/{code}", tags=["справочники"])
def get_entity(code: str, user: User = Depends(require("dict.view"))):
    return _entity(code)


@app.post("/entities", tags=["справочники"], status_code=201)
def create_entity(body: EntityIn, user: User = Depends(require("dict.edit"))):
    d = body.model_dump()
    comment = d.pop("comment")
    if entities.exists(d["code"]):
        raise AppError("schema.exists", "Справочник с таким кодом уже есть", 409)
    for f in d["fields"]:
        f["system"] = False
    _check_entity_def(d, None)
    d["system"] = False
    e = entities.create(d, actor=user.id, obj_id=d["code"])
    entities.add_version(d["code"], {"schema.json": dumps(d).encode()}, {"comment": comment or "создание"}, user.id)
    audit(user, "dict.entity_create", "entity", d["code"], {"title": d["title_ru"]})
    return entities.get(d["code"])


@app.put("/entities/{code}", tags=["справочники"])
def update_entity(code: str, body: EntityIn, user: User = Depends(require("dict.edit"))):
    old = _entity(code)
    d = body.model_dump()
    comment = d.pop("comment")
    if d["code"] != code:
        raise AppError("schema.code_change", "Код справочника менять нельзя", 400)
    _check_entity_def(d, old)
    d["system"] = old.get("system", False)
    entities.update(code, d, actor=user.id)
    v = entities.add_version(code, {"schema.json": dumps(d).encode()}, {"comment": comment}, user.id)
    audit(user, "dict.entity_update", "entity", code, {"version": v["n"]})
    return entities.get(code)


@app.delete("/entities/{code}", tags=["справочники"])
def delete_entity(code: str, user: User = Depends(require("dict.edit"))):
    e = _entity(code)
    if e.get("system"):
        raise AppError("schema.system", "Системный справочник используется расчётами — удалить нельзя", 400)
    entities.delete(code)
    audit(user, "dict.entity_delete", "entity", code)
    return {"ok": True}


@app.get("/entities/{code}/versions", tags=["справочники"])
def entity_versions(code: str, user: User = Depends(require("dict.view"))):
    _entity(code)
    return entities.list_versions(code)


@app.get("/entities/{code}/versions/{n}", tags=["справочники"])
def entity_version(code: str, n: int, user: User = Depends(require("dict.view"))):
    return json.loads(entities.read_version_file(code, n, "schema.json"))


# ------------------------------------------------------------------ записи
def _ref_maps(fields: list[dict]) -> dict[str, dict]:
    out = {}
    for f in fields:
        ent = f.get("ref_entity")
        if f.get("type") in ("ref", "ref_list") and ent and ent not in out:
            out[ent] = lookup_map(ent)
    return out


def lookup_map(ent: str) -> dict:
    """{нижний регистр кода / названия / id: ключ}. Ключ — значение поля code (если есть), иначе id."""
    m = {}
    for r in records(ent).list():
        if r.get("deleted"):
            continue
        vals = r.get("values", {})
        key = vals.get("code") or r["id"]
        aliases = str(vals.get("aliases") or "").splitlines()
        for cand in (r["id"], vals.get("code"), vals.get("name_ru"), vals.get("name_kk"), *aliases):
            if cand and str(cand).strip():
                m.setdefault(str(cand).strip().lower(), key)
    return m


def _check_unique(code: str, fields: list[dict], values: dict, rid: str | None) -> list[dict]:
    errs = []
    uniq = [f for f in fields if f.get("unique")]
    if not uniq:
        return errs
    others = [r for r in records(code).list() if not r.get("deleted") and r["id"] != rid]
    for f in uniq:
        v = values.get(f["code"])
        if v is None:
            continue
        if any(str(r.get("values", {}).get(f["code"], "")).lower() == str(v).lower() for r in others):
            errs.append({"field": f["code"], "message": f"«{f['title_ru']}»: значение «{v}» уже есть"})
    return errs


def _create_record(code: str, values: dict, actor: str, source: str | None = None) -> dict:
    e = entities.get(code)
    clean, errors = validate_record(e["fields"], values, _ref_maps(e["fields"]))
    errors += _check_unique(code, e["fields"], clean, None)
    if errors:
        raise AppError("record.invalid", "Запись содержит ошибки", 422, errors)
    col = records(code)
    r = col.create({"values": clean, "source": source}, actor=actor)
    col.add_version(r["id"], {"record.json": dumps(clean).encode()}, {"comment": "создание"}, actor)
    return col.get(r["id"])


class RecordIn(BaseModel):
    values: dict
    comment: str = ""


@app.get("/entities/{code}/records", tags=["записи"])
def list_records(code: str, include_deleted: bool = False, user: User = Depends(require("dict.view"))):
    _entity(code)
    return [r for r in records(code).list() if include_deleted or not r.get("deleted")]


@app.get("/entities/{code}/lookup", tags=["записи"])
def lookup(code: str, user: User = Depends(require("dict.view"))):
    _entity(code)
    return lookup_map(code)


@app.post("/entities/{code}/records", tags=["записи"], status_code=201)
def create_record(code: str, body: RecordIn, user: User = Depends(require("dict.edit"))):
    _entity(code)
    r = _create_record(code, body.values, user.id)
    audit(user, "dict.record_create", code, r["id"], {"values": _short(r["values"])})
    return r


def _short(values: dict) -> dict:
    return {k: v for k, v in values.items() if k not in ("shape",)}


@app.get("/entities/{code}/records/{rid}", tags=["записи"])
def get_record(code: str, rid: str, user: User = Depends(require("dict.view"))):
    r = records(code).get(rid)
    if not r:
        raise not_found("Запись")
    return r


@app.put("/entities/{code}/records/{rid}", tags=["записи"])
def update_record(code: str, rid: str, body: RecordIn, user: User = Depends(require("dict.edit"))):
    e = _entity(code)
    col = records(code)
    cur = col.get(rid)
    if not cur or cur.get("deleted"):
        raise not_found("Запись")
    clean, errors = validate_record(e["fields"], body.values, _ref_maps(e["fields"]))
    errors += _check_unique(code, e["fields"], clean, rid)
    if errors:
        raise AppError("record.invalid", "Запись содержит ошибки", 422, errors)
    if e.get("system") and "code" in clean and clean.get("code") != cur["values"].get("code"):
        raise AppError("record.code_change", "Код записи используется в данных и расчётах — менять нельзя", 400)
    col.update(rid, {"values": clean}, actor=user.id)
    v = col.add_version(rid, {"record.json": dumps(clean).encode()}, {"comment": body.comment}, user.id)
    changed = [k for k in clean if clean.get(k) != cur["values"].get(k)]
    audit(user, "dict.record_update", code, rid, {"version": v["n"], "changed": changed})
    return col.get(rid)


@app.delete("/entities/{code}/records/{rid}", tags=["записи"])
def delete_record(code: str, rid: str, user: User = Depends(require("dict.edit"))):
    col = records(code)
    if not col.get(rid):
        raise not_found("Запись")
    col.delete(rid)
    audit(user, "dict.record_delete", code, rid)
    return {"ok": True}


@app.get("/entities/{code}/records/{rid}/versions", tags=["записи"])
def record_versions(code: str, rid: str, user: User = Depends(require("dict.view"))):
    col = records(code)
    out = []
    for v in col.list_versions(rid):
        out.append({**v, "values": json.loads(col.read_version_file(rid, v["n"], "record.json"))})
    return out


# ------------------------------------------------------------------ водоёмы и карта
@app.get("/water-bodies.geojson", tags=["водоёмы"])
def water_bodies_geojson(user: User = Depends(require("dict.view"))):
    feats = []
    for r in records("water_bodies").list():
        if r.get("deleted"):
            continue
        v = r["values"]
        pt = v.get("point")
        geom = v.get("shape") or ({"type": "Point", "coordinates": [pt[1], pt[0]]} if pt else None)
        props = {k: v.get(k) for k in ("code", "name_ru", "name_kk", "type", "origin", "status", "fishery_kinds",
                                    "regions", "basin", "area_km2", "point")}
        props["regions"] = props.get("regions") or []
        props["fishery_kinds"] = props.get("fishery_kinds") or []
        props["id"] = r["id"]
        feats.append({"type": "Feature", "id": r["id"], "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": feats,
            "attribution": "Контуры: Natural Earth (общественное достояние) и пользователи FishStocke"}


@app.get("/kazakhstan.geojson", tags=["водоёмы"])
def kazakhstan(user: User = Depends(current_user)):
    return JSONResponse(json.loads((SEED_DIR / "kazakhstan.geojson").read_text(encoding="utf-8")))


def _parse_kml(text: str) -> dict:
    root = ET.fromstring(text)
    polys = []
    for el in root.iter():
        if el.tag.endswith("Polygon"):
            rings = []
            for c in el.iter():
                if c.tag.endswith("coordinates") and c.text:
                    pts = []
                    for tok in c.text.split():
                        parts = tok.split(",")
                        if len(parts) >= 2:
                            pts.append([float(parts[0]), float(parts[1])])
                    if len(pts) >= 4:
                        rings.append(pts)
            if rings:
                polys.append(rings)
    if not polys:
        raise AppError("geo.empty", "В файле KML не найдено ни одного многоугольника", 422)
    return {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys}


def _geom_from_geojson(d: dict) -> dict:
    t = d.get("type")
    if t == "FeatureCollection":
        geoms = [f.get("geometry") for f in d.get("features", []) if f.get("geometry")]
        polys = [g for g in geoms if g["type"] in ("Polygon", "MultiPolygon")]
        if not polys:
            raise AppError("geo.empty", "В файле нет многоугольников", 422)
        if len(polys) == 1:
            return polys[0]
        coords = []
        for g in polys:
            coords += [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        return {"type": "MultiPolygon", "coordinates": coords}
    if t == "Feature":
        return _geom_from_geojson(d.get("geometry") or {})
    if t in ("Polygon", "MultiPolygon"):
        return d
    raise AppError("geo.type", "Нужен многоугольник (Polygon/MultiPolygon)", 422)


def _centroid(geom: dict) -> list[float]:
    pts = []

    def walk(c):
        if isinstance(c[0], (int, float)):
            pts.append(c)
        else:
            for x in c:
                walk(x)
    walk(geom["coordinates"])
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return [round(lat, 5), round(lon, 5)]


@app.post("/geo/parse", tags=["водоёмы"])
async def parse_geo(file: UploadFile = File(...), user: User = Depends(require("dict.edit"))):
    raw = (await file.read()).decode("utf-8", errors="replace")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".kml") or raw.lstrip().startswith("<"):
            geom = _parse_kml(raw)
        else:
            geom = _geom_from_geojson(json.loads(raw))
    except (json.JSONDecodeError, ET.ParseError, KeyError, ValueError, TypeError):
        raise AppError("geo.parse", "Файл не распознан: нужен GeoJSON или KML с многоугольником", 422)
    return {"shape": geom, "point": _centroid(geom)}


# ------------------------------------------------------------------ типы наборов данных
class DatasetTypeIn(BaseModel):
    code: str
    title_ru: str
    title_kk: str = ""
    description: str = ""
    period_field: str | None = "year"
    columns: list[dict]
    species_columns: dict = {"enabled": False}
    key_fields: list[str] = []
    rules: list[dict] = []
    comment: str = ""


def _dtype(code: str) -> dict:
    t = dtypes.get(code)
    if not t or t.get("deleted"):
        raise not_found("Тип набора данных")
    return t


def _check_dtype(d: dict, old: dict | None) -> None:
    errs = []
    if not CODE_RE.match(d["code"]):
        errs.append("Код типа: латинские строчные буквы, цифры и _")
    codes = [c.get("code") for c in d["columns"]]
    if len(codes) != len(set(codes)):
        errs.append("Коды столбцов повторяются")
    for c in d["columns"]:
        errs += validate_field_def(c)
        if c.get("type") in ("geo_shape",):
            errs.append(f"Столбец «{c.get('code')}»: контур нельзя хранить в таблице")
        if c.get("type") in ("ref", "ref_list") and not entities.exists(c.get("ref_entity") or ""):
            errs.append(f"Столбец «{c.get('code')}»: справочник «{c.get('ref_entity')}» не найден")
    sc = d.get("species_columns") or {}
    if sc.get("enabled") and sc.get("value_type") not in ("integer", "number"):
        errs.append("Столбцы видов: тип значения — целое или число")
    if d.get("period_field") and d["period_field"] not in codes:
        errs.append("Поле периода должно быть одним из столбцов")
    for k in d.get("key_fields") or []:
        if k not in codes:
            errs.append(f"Ключевое поле «{k}» должно быть одним из столбцов")
    for r in d.get("rules") or []:
        if r.get("type") not in ("le", "lt") or r.get("left") not in codes or r.get("right") not in codes:
            errs.append(f"Правило проверки {r} задано неверно")
    if old:
        new_by = {c["code"]: c for c in d["columns"]}
        for c in old["columns"]:
            if c.get("system"):
                nc = new_by.get(c["code"])
                if nc is None:
                    errs.append(f"Системный столбец «{c['code']}» используется алгоритмами — удалить нельзя")
                elif nc.get("type") != c.get("type"):
                    errs.append(f"Системному столбцу «{c['code']}» нельзя менять тип")
                else:
                    nc["system"] = True
    if errs:
        raise AppError("schema.invalid", "Описание типа набора данных содержит ошибки", 422, errs)


@app.get("/dataset-types", tags=["типы наборов данных"])
def list_dtypes(user: User = Depends(require("dict.view"))):
    return [t for t in dtypes.list() if not t.get("deleted")]


@app.get("/dataset-types/{code}", tags=["типы наборов данных"])
def get_dtype(code: str, version: int | None = None, user: User = Depends(require("dict.view"))):
    t = _dtype(code)
    if version:
        d = json.loads(dtypes.read_version_file(code, version, "schema.json"))
        return {**t, **d, "current_version": version}
    return t


@app.post("/dataset-types", tags=["типы наборов данных"], status_code=201)
def create_dtype(body: DatasetTypeIn, user: User = Depends(require("dict.edit"))):
    d = body.model_dump()
    comment = d.pop("comment")
    if dtypes.exists(d["code"]):
        raise AppError("schema.exists", "Тип с таким кодом уже есть", 409)
    for c in d["columns"]:
        c["system"] = False
    _check_dtype(d, None)
    d["system"] = False
    dtypes.create(d, actor=user.id, obj_id=d["code"])
    dtypes.add_version(d["code"], {"schema.json": dumps(d).encode()}, {"comment": comment or "создание"}, user.id)
    audit(user, "dict.dtype_create", "dataset_type", d["code"])
    return dtypes.get(d["code"])


@app.put("/dataset-types/{code}", tags=["типы наборов данных"])
def update_dtype(code: str, body: DatasetTypeIn, user: User = Depends(require("dict.edit"))):
    old = _dtype(code)
    d = body.model_dump()
    comment = d.pop("comment")
    if d["code"] != code:
        raise AppError("schema.code_change", "Код типа менять нельзя", 400)
    _check_dtype(d, old)
    d["system"] = old.get("system", False)
    dtypes.update(code, d, actor=user.id)
    v = dtypes.add_version(code, {"schema.json": dumps(d).encode()}, {"comment": comment}, user.id)
    audit(user, "dict.dtype_update", "dataset_type", code, {"version": v["n"]})
    return dtypes.get(code)


@app.get("/dataset-types/{code}/versions", tags=["типы наборов данных"])
def dtype_versions(code: str, user: User = Depends(require("dict.view"))):
    _dtype(code)
    return dtypes.list_versions(code)


_seed()
