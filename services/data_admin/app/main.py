"""
Сервис 2. Администрирование входных данных.

Наборы данных (водоём × тип набора), Excel-шаблоны по справочникам, загрузка с проверкой
(структура, обязательные поля, типы, единицы, ссылки на справочники, ключи, правила),
правка в браузере, неизменяемые версии, сравнение версий, выгрузка.
"""
from __future__ import annotations

import io
import json
from collections import Counter

import httpx
from fastapi import Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import Collection, dumps

from . import tables

app = create_app("data_admin", "Администрирование входных данных",
                 "Наборы данных по водоёмам, шаблоны Excel, загрузка и проверка, правка, версии.")
ST = app.state.settings
ROOT = ST.service_dir()
datasets = Collection(ROOT, "datasets")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DictClient:
    """Чтение справочников из сервиса data-model (служебный токен)."""

    def __init__(self, http=None):
        self.http = http or httpx.Client(base_url=ST.urls["data_model"], timeout=15)

    def _get(self, path):
        try:
            r = self.http.get(path, headers={"X-Service-Token": ST.service_token})
        except httpx.HTTPError:
            raise AppError("dict.unavailable", "Сервис справочников недоступен, повторите позже", 503)
        if r.status_code == 404:
            raise AppError("not_found", "Не найдено в справочнике", 404)
        if r.status_code >= 300:
            raise AppError("dict.error", f"Ошибка сервиса справочников ({r.status_code})", 502)
        return r.json()

    def dtype(self, code, version=None):
        return self._get(f"/dataset-types/{code}" + (f"?version={version}" if version else ""))

    def records(self, entity):
        return [r["values"] | {"_id": r["id"]} for r in self._get(f"/entities/{entity}/records")]

    def lookup(self, entity):
        return self._get(f"/entities/{entity}/lookup")

    def create_record(self, entity, values):
        try:
            r = self.http.post(f"/entities/{entity}/records", json={"values": values},
                               headers={"X-Service-Token": ST.service_token})
        except httpx.HTTPError:
            raise AppError("dict.unavailable", "Сервис справочников недоступен, повторите позже", 503)
        if r.status_code >= 300:
            raise AppError("dict.error", f"Справочник не принял запись ({r.status_code})", 502, r.json().get("details"))
        return r.json()


DICT = DictClient()

# «Тип лова» в уловах до 21.10.2026 — список значений; теперь — ссылка на справочник «Типы вылова» (коды)
OLD_CATCH_TYPES = {"научный": "scientific", "промысловый": "commercial", "спортивно-любительский": "sport"}


def _migrate_catch_types() -> None:
    for d in datasets.list():
        if d.get("deleted") or d.get("dataset_type") != "catches" or not d.get("current_version"):
            continue
        table = json.loads(datasets.read_version_file(d["id"], d["current_version"], "data.json"))
        rows = table.get("rows") or []
        if not any(str(r.get("catch_type") or "").strip().lower() in OLD_CATCH_TYPES for r in rows):
            continue
        for r in rows:
            r["catch_type"] = OLD_CATCH_TYPES.get(str(r.get("catch_type") or "").strip().lower(), r.get("catch_type"))
        info = datasets.version_info(d["id"], d["current_version"]) or {}
        datasets.add_version(d["id"], {"data.json": dumps(table).encode("utf-8")},
                             {"comment": "«Тип лова» — коды справочника «Типы вылова» (без изменения данных)",
                              "origin": "migration", "type_version": info.get("type_version"),
                              "summary": d.get("summary")}, "system", technical=True)


_migrate_catch_types()


def audit(user, action, oid, details=None):
    app.state.audit.log(user, action, "dataset", oid, details)


def _ref_maps(dtype):
    return {c["ref_entity"]: DICT.lookup(c["ref_entity"]) for c in dtype["columns"] if c["type"] == "ref"}


def _place_maps(dtype, water_body):
    """{код столбца: {ключ написания: название места}} — места лова своего водоёма (справочник «Места лова»)."""
    out = {}
    for c in dtype["columns"]:
        ent = c.get("places_entity")
        if not ent:
            continue
        m = {}
        for r in DICT.records(ent):
            if r.get("water_body") != water_body or not r.get("name_ru"):
                continue
            for cand in (r.get("name_ru"), r.get("name_kk"), *str(r.get("aliases") or "").splitlines()):
                if cand and cand.strip():
                    m.setdefault(tables.place_key(cand), r["name_ru"])
        out[c["code"]] = m
    return out


def _ref_names(dtype, lang="ru"):
    out = {}
    for c in dtype["columns"]:
        if c["type"] == "ref":
            out[c["ref_entity"]] = [r.get(f"name_{lang}") or r.get("name_ru") or r.get("code") for r in DICT.records(c["ref_entity"])]
    return out


def _ref_display(dtype, lang="ru"):
    out = {}
    for c in dtype["columns"]:
        if c["type"] == "ref":
            out[c["ref_entity"]] = {r.get("code") or r["_id"]: r.get(f"name_{lang}") or r.get("name_ru") or r.get("code")
                                    for r in DICT.records(c["ref_entity"])}
    return out


def _water_body(code):
    wbs = {r["code"]: r for r in DICT.records("water_bodies")}
    if code not in wbs:
        raise AppError("dataset.water_body", f"Водоём «{code}» не найден в справочнике", 404)
    return wbs[code]


def _get_ds(ds_id):
    d = datasets.get(ds_id)
    if not d or d.get("deleted"):
        raise not_found("Набор данных")
    return d


def _find(water_body, dataset_type):
    for d in datasets.list():
        if not d.get("deleted") and d["water_body"] == water_body and d["dataset_type"] == dataset_type:
            return d
    return None


def _table(ds_id, n=None):
    d = _get_ds(ds_id)
    n = n or d.get("current_version")
    if not n:
        return None, None
    return json.loads(datasets.read_version_file(ds_id, n, "data.json")), n


# ------------------------------------------------------------------ наборы
class DatasetIn(BaseModel):
    water_body: str
    dataset_type: str
    title: str = ""
    description: str = ""


@app.get("/datasets", tags=["наборы данных"])
def list_datasets(water_body: str | None = None, dataset_type: str | None = None,
                  user: User = Depends(require("data.view"))):
    out = []
    for d in datasets.list():
        if d.get("deleted"):
            continue
        if water_body and d["water_body"] != water_body:
            continue
        if dataset_type and d["dataset_type"] != dataset_type:
            continue
        out.append(d)
    return out


def _create(body: DatasetIn, user) -> dict:
    wb = _water_body(body.water_body)
    dt = DICT.dtype(body.dataset_type)
    if _find(body.water_body, body.dataset_type):
        raise AppError("dataset.exists", "Для этого водоёма набор такого типа уже есть", 409)
    d = datasets.create({"water_body": body.water_body, "dataset_type": body.dataset_type,
                         "title": body.title or f"{dt['title_ru']} — {wb['name_ru']}",
                         "description": body.description, "current_version": None, "summary": None}, actor=user.id)
    audit(user, "data.dataset_create", d["id"], {"water_body": body.water_body, "type": body.dataset_type})
    return d


@app.post("/datasets", tags=["наборы данных"], status_code=201)
def create_dataset(body: DatasetIn, user: User = Depends(require("data.edit"))):
    return _create(body, user)


@app.get("/datasets/{ds_id}", tags=["наборы данных"])
def get_dataset(ds_id: str, user: User = Depends(require("data.view"))):
    return _get_ds(ds_id)


@app.delete("/datasets/{ds_id}", tags=["наборы данных"])
def delete_dataset(ds_id: str, user: User = Depends(require("data.edit"))):
    _get_ds(ds_id)
    datasets.delete(ds_id)
    audit(user, "data.dataset_delete", ds_id)
    return {"ok": True}


@app.get("/datasets/{ds_id}/versions", tags=["наборы данных"])
def versions(ds_id: str, user: User = Depends(require("data.view"))):
    _get_ds(ds_id)
    return list(reversed(datasets.list_versions(ds_id)))


@app.get("/datasets/{ds_id}/data", tags=["наборы данных"])
def get_data(ds_id: str, version: int | None = None, user: User = Depends(require("data.view"))):
    d = _get_ds(ds_id)
    table, n = _table(ds_id, version)
    if table is None:
        return {"dataset": d, "version": None, "table": None}
    return {"dataset": d, "version": n, "version_info": datasets.version_info(ds_id, n), "table": table}


# ------------------------------------------------------------------ шаблоны
@app.get("/templates/{dataset_type}.xlsx", tags=["шаблоны"])
def template(dataset_type: str, water_body: str | None = None, species: str | None = None,
             lang: str = "ru", user: User = Depends(require("data.view"))):
    dt = DICT.dtype(dataset_type)
    all_sp = DICT.records("species")
    chosen = None
    if species:
        chosen = [s.strip() for s in species.split(",") if s.strip()]
    elif water_body:
        ds = _find(water_body, dataset_type)
        if ds and ds.get("summary"):
            chosen = ds["summary"].get("species")
    sp = [s for s in all_sp if chosen is None or s["code"] in chosen]
    content = tables.build_template(dt, sp, _ref_names(dt, lang), lang)
    fname = f"template_{dataset_type}.xlsx"
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/datasets/{ds_id}/export.xlsx", tags=["наборы данных"])
def export(ds_id: str, version: int | None = None, lang: str = "ru", user: User = Depends(require("data.view"))):
    d = _get_ds(ds_id)
    table, n = _table(ds_id, version)
    if table is None:
        raise AppError("dataset.empty", "В наборе ещё нет данных", 404)
    info = datasets.version_info(ds_id, n) or {}
    dt = DICT.dtype(d["dataset_type"], info.get("type_version"))
    sp_by = {s["code"]: s for s in DICT.records("species")}
    sp = [sp_by.get(c, {"code": c, "name_ru": c}) for c in table.get("species", [])]
    content = tables.build_template(dt, sp, _ref_names(dt, lang), lang, rows=table["rows"],
                                    ref_display=_ref_display(dt, lang))
    audit(user, "data.export", ds_id, {"version": n})
    return Response(content, media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{d["water_body"]}_{d["dataset_type"]}_v{n}.xlsx"'})


@app.get("/datasets/{ds_id}/versions/{n}/source", tags=["наборы данных"])
def source_file(ds_id: str, n: int, user: User = Depends(require("data.view"))):
    _get_ds(ds_id)
    try:
        content = datasets.read_version_file(ds_id, n, "source.xlsx")
    except FileNotFoundError:
        raise AppError("dataset.no_source", "Эта версия создана правкой в браузере — исходного файла нет", 404)
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="source_v{n}.xlsx"'})


# ------------------------------------------------------------------ загрузка
def _report(ok, errors, warnings, summary=None, version=None, dataset=None):
    return {"ok": ok, "errors": errors[:500], "errors_total": len(errors), "warnings": warnings[:200],
            "summary": summary, "version": version, "dataset": dataset}


def _save_version(d, dt, table, user, comment, source: bytes | None, origin: str):
    files = {"data.json": dumps(table).encode("utf-8")}
    if source is not None:
        files["source.xlsx"] = source
    summ = tables.summarize(dt, table)
    v = datasets.add_version(d["id"], files, {"comment": comment, "origin": origin, "type_version": dt.get("current_version"),
                                              "summary": summ}, user.id)
    datasets.update(d["id"], {"summary": summ}, actor=user.id)
    return v, summ


def _ingest(d, content: bytes, mode: str, dry_run: bool, comment: str, user, filename: str):
    if mode not in ("replace", "merge"):
        raise AppError("dataset.mode", "Режим загрузки: replace (заменить всё) или merge (заменить годы из файла)", 400)
    dt = DICT.dtype(d["dataset_type"])
    species = DICT.records("species")
    try:
        sp_codes, raw = tables.read_excel(content, dt, species)
    except tables.ParseError as e:
        audit(user, "data.upload", d["id"], {"file": filename, "ok": False, "errors": len(e.errors)})
        return _report(False, e.errors, [])
    if not raw:
        return _report(False, [{"row": 2, "column": None, "message": "В файле нет строк с данными"}], [])
    rows, errors, warnings = tables.validate_rows(dt, sp_codes, species, raw, _ref_maps(dt),
                                                  _place_maps(dt, d["water_body"]))
    if errors:
        if not dry_run:
            audit(user, "data.upload", d["id"], {"file": filename, "ok": False, "errors": len(errors)})
        return _report(False, errors, warnings)
    old, _ = _table(d["id"])
    table = tables.merge_rows(dt, old, rows, sp_codes, mode)
    summ = tables.summarize(dt, table)
    if dry_run:
        return _report(True, [], warnings, summ)
    v, summ = _save_version(d, dt, table, user, comment or f"загрузка {filename}", content, f"upload:{mode}")
    audit(user, "data.upload", d["id"], {"file": filename, "version": v["n"], "rows": len(rows), "mode": mode})
    return _report(True, [], warnings, summ, v["n"], datasets.get(d["id"]))


@app.post("/datasets/{ds_id}/upload", tags=["загрузка"])
async def upload(ds_id: str, file: UploadFile = File(...), mode: str = Form("merge"), dry_run: bool = Form(False),
                 comment: str = Form(""), user: User = Depends(require("data.edit"))):
    d = _get_ds(ds_id)
    return _ingest(d, await file.read(), mode, dry_run, comment, user, file.filename or "")


@app.post("/upload", tags=["загрузка"])
async def upload_new(water_body: str = Form(...), dataset_type: str = Form(...), file: UploadFile = File(...),
                     mode: str = Form("merge"), dry_run: bool = Form(False), comment: str = Form(""),
                     user: User = Depends(require("data.edit"))):
    """Загрузка с автоматическим созданием набора (водоём × тип), если его ещё нет."""
    content = await file.read()
    d = _find(water_body, dataset_type)
    if d is None:
        if dry_run:
            _water_body(water_body)
            dt = DICT.dtype(dataset_type)
            fake = {"id": "_dry", "dataset_type": dataset_type}
            try:
                sp_codes, raw = tables.read_excel(content, dt, DICT.records("species"))
            except tables.ParseError as e:
                return _report(False, e.errors, [])
            rows, errors, warnings = tables.validate_rows(dt, sp_codes, DICT.records("species"), raw, _ref_maps(dt),
                                                          _place_maps(dt, water_body))
            table = tables.merge_rows(dt, None, rows, sp_codes, "replace")
            return _report(not errors, errors, warnings, None if errors else tables.summarize(dt, table))
        d = _create(DatasetIn(water_body=water_body, dataset_type=dataset_type), user)
    return _ingest(d, content, mode, dry_run, comment, user, file.filename or "")


# ------------------------------------------------------------------ правка в браузере
class EditIn(BaseModel):
    rows: list[dict]
    species: list[str] | None = None
    comment: str = ""
    base_version: int | None = None


@app.put("/datasets/{ds_id}/data", tags=["правка"])
def edit(ds_id: str, body: EditIn, user: User = Depends(require("data.edit"))):
    d = _get_ds(ds_id)
    if body.base_version is not None and d.get("current_version") not in (None, body.base_version):
        raise AppError("dataset.conflict",
                       f"Набор изменён другим пользователем (сейчас версия {d['current_version']}). Обновите страницу.", 409)
    dt = DICT.dtype(d["dataset_type"])
    species = DICT.records("species")
    old, _ = _table(ds_id)
    sp_codes = body.species if body.species is not None else (old or {}).get("species", [])
    known = {s["code"] for s in species}
    bad = [s for s in sp_codes if s not in known]
    if bad:
        raise AppError("dataset.species", f"Виды не найдены в справочнике: {', '.join(bad)}", 422)
    raw = [(i + 1, r) for i, r in enumerate(body.rows)]
    rows, errors, warnings = tables.validate_rows(dt, sp_codes, species, raw, _ref_maps(dt),
                                                  _place_maps(dt, d["water_body"]))
    if errors:
        for e in errors:
            e["row"] = e["row"]  # номер строки в таблице редактора (с 1)
        return _report(False, errors, warnings)
    table = {"columns": [c["code"] for c in dt["columns"]], "species": list(sp_codes), "rows": rows}
    v, summ = _save_version(d, dt, table, user, body.comment or "правка в браузере", None, "edit")
    audit(user, "data.edit", ds_id, {"version": v["n"], "rows": len(rows)})
    return _report(True, [], warnings, summ, v["n"], datasets.get(ds_id))


# ------------------------------------------------------------------ места лова
@app.post("/fishing-places/collect", tags=["места лова"])
def collect_places(water_body: str | None = None, user: User = Depends(require("dict.edit"))):
    """Добавить в справочник «Места лова» места из текущих версий загруженных уловов, которых там ещё нет.
    Написания, отличающиеся только регистром, пробелами, точками и дефисами, становятся одним местом:
    название — самое частое написание, остальные — «другие написания»."""
    created = []
    for d in datasets.list():
        if d.get("deleted") or not d.get("current_version") or (water_body and d["water_body"] != water_body):
            continue
        dt = DICT.dtype(d["dataset_type"])
        for c in dt["columns"]:
            if not c.get("places_entity"):
                continue
            known = _place_maps(dt, d["water_body"]).get(c["code"], {})
            table, _ = _table(d["id"])
            groups: dict[str, Counter] = {}
            for r in table["rows"]:
                v = r.get(c["code"])
                if v is None or not str(v).strip():
                    continue
                k = tables.place_key(v)
                if k in known:
                    continue
                groups.setdefault(k, Counter())[str(v).strip()] += 1
            for k, cnt in sorted(groups.items(), key=lambda x: -sum(x[1].values())):
                names = [n for n, _ in cnt.most_common()]
                vals = {"water_body": d["water_body"], "name_ru": names[0]}
                if len(names) > 1:
                    vals["aliases"] = "\n".join(names[1:])
                DICT.create_record(c["places_entity"], vals)
                known[k] = names[0]
                created.append({"water_body": d["water_body"], "name_ru": names[0], "aliases": names[1:],
                                "rows": sum(cnt.values())})
    audit(user, "dict.places_collect", water_body or "*", {"created": len(created)})
    return {"created": len(created), "places": created}


@app.post("/datasets/{ds_id}/restore/{n}", tags=["правка"])
def restore(ds_id: str, n: int, user: User = Depends(require("data.edit"))):
    d = _get_ds(ds_id)
    table, _ = _table(ds_id, n)
    dt = DICT.dtype(d["dataset_type"])
    if d["dataset_type"] == "catches":       # версии до 21.10.2026 — прежние значения «Типа лова»
        for r in table.get("rows") or []:
            r["catch_type"] = OLD_CATCH_TYPES.get(str(r.get("catch_type") or "").strip().lower(), r.get("catch_type"))
    v, _ = _save_version(d, dt, table, user, f"восстановлена версия {n}", None, f"restore:{n}")
    audit(user, "data.restore", ds_id, {"from": n, "version": v["n"]})
    return datasets.get(ds_id)


@app.get("/datasets/{ds_id}/diff", tags=["правка"])
def diff(ds_id: str, a: int, b: int, user: User = Depends(require("data.view"))):
    d = _get_ds(ds_id)
    ta, _ = _table(ds_id, a)
    tb, _ = _table(ds_id, b)
    dt = DICT.dtype(d["dataset_type"])
    return {"a": a, "b": b, **tables.diff_tables(dt, ta, tb)}


# ------------------------------------------------------------------ сводка по водоёмам
@app.get("/water-bodies/status", tags=["сводка"])
def water_body_status(user: User = Depends(require("data.view"))):
    out: dict[str, dict] = {}
    for d in datasets.list():
        if d.get("deleted") or not d.get("current_version"):
            continue
        s = out.setdefault(d["water_body"], {"datasets": {}, "updated_at": None, "years": []})
        summ = d.get("summary") or {}
        s["datasets"][d["dataset_type"]] = {"id": d["id"], "version": d["current_version"], "rows": summ.get("rows"),
                                            "period_from": summ.get("period_from"), "period_to": summ.get("period_to"),
                                            "updated_at": d["updated_at"]}
        if not s["updated_at"] or d["updated_at"] > s["updated_at"]:
            s["updated_at"] = d["updated_at"]
        s["years"] = sorted(set(s["years"]) | set(summ.get("years") or []))
    return out


@app.get("/bundle/{water_body}", tags=["для расчётов"])
def bundle(water_body: str, user: User = Depends(require("data.view"))):
    """Текущие версии всех наборов водоёма (для формы запуска расчёта)."""
    out = {}
    for d in datasets.list():
        if not d.get("deleted") and d["water_body"] == water_body and d.get("current_version"):
            out[d["dataset_type"]] = {"dataset_id": d["id"], "version": d["current_version"],
                                      "summary": d.get("summary")}
    return out
