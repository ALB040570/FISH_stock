"""
Сервис 4. Администрирование дашбордов.

Дашборды — сохранённые представления исходных данных и результатов расчётов: вкладки, виджеты
(показатели, графики, таблицы, особые представления), источники, фильтры, сравнение водоёмов/лет/сценариев,
доступ личный или общий. Системные шаблоны (мониторинг водоёма) ведут администратор и математик;
любой пользователь может сделать копию и настроить её.
"""
from __future__ import annotations

import copy
from collections import OrderedDict

import httpx
from fastapi import Depends
from fastapi.responses import Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import Collection, dumps

from . import explain, export, insights, kk, templates

app = create_app("dashboards", "Администрирование дашбордов",
                 "Шаблоны мониторинга, конструктор дашбордов, данные виджетов, доступ.")
ST = app.state.settings
ROOT = ST.service_dir()
boards = Collection(ROOT, "dashboards")
WIDGET_TYPES = ("kpi", "line", "bar", "table", "band", "text", "special", "view")
SOURCE_KINDS = ("dataset", "run", "payload", "status", "insight", "help")
settings = Collection(ROOT, "settings")


class Svc:
    def __init__(self, name, http=None):
        self.name = name
        self.http = http or httpx.Client(base_url=ST.urls[name], timeout=60)

    def get(self, path, **params):
        try:
            r = self.http.get(path, params=params or None, headers={"X-Service-Token": ST.service_token})
        except httpx.HTTPError:
            raise AppError("service.unavailable", f"Сервис «{self.name}» недоступен", 503)
        if r.status_code == 404:
            return None
        if r.status_code >= 300:
            raise AppError("service.error", f"Ошибка сервиса «{self.name}» ({r.status_code})", 502)
        return r.json()


SVC = {"algo_admin": Svc("algo_admin"), "data_admin": Svc("data_admin"), "data_model": Svc("data_model")}


def audit(user, action, oid, details=None):
    app.state.audit.log(user, action, "dashboard", oid, details)


def _seed():
    for t in templates.SYSTEM:
        rev = templates.TEMPLATE_REV
        cur = boards.get(t["code"])
        if cur is None:
            boards.create({**copy.deepcopy(t), "owner": "system", "template_rev": rev}, actor="system", obj_id=t["code"])
            boards.add_version(t["code"], {"dashboard.json": dumps(t).encode()}, {"comment": "системный шаблон"}, "system")
        elif cur.get("template_rev", 1) < rev and cur.get("updated_by") == "system":
            boards.update(t["code"], {**copy.deepcopy(t), "template_rev": rev}, actor="system")
            boards.add_version(t["code"], {"dashboard.json": dumps(t).encode()},
                               {"comment": f"обновление системного шаблона (ревизия {rev})"}, "system")


_seed()


def _can_view(d, user):
    return d.get("visibility") == "shared" or d.get("owner") == user.id or d.get("is_template") or user.role == "admin"


def _can_edit(d, user):
    if d.get("is_template") or d.get("system"):
        return user.can("dashboard.template")
    return user.can("dashboard.edit") and (d.get("owner") == user.id or user.role == "admin")


def _get(did, user):
    d = boards.get(did)
    if not d or d.get("deleted") or not _can_view(d, user):
        raise not_found("Дашборд")
    return {**d, "can_edit": _can_edit(d, user)}


class BoardIn(BaseModel):
    title_ru: str
    title_kk: str = ""
    description: str = ""
    visibility: str = "private"
    filters: dict = {}
    tabs: list[dict] = []
    widgets: list[dict] = []
    comment: str = ""


def _check(body: dict) -> list[str]:
    errs = []
    if not body["title_ru"].strip():
        errs.append("Нужно название дашборда")
    if body["visibility"] not in ("private", "shared"):
        errs.append("Доступ: private (только мне) или shared (всем пользователям)")
    ids = set()
    tabs = {t.get("code") for t in body["tabs"]} or {"main"}
    for w in body["widgets"]:
        if not w.get("id") or w["id"] in ids:
            errs.append("У каждого виджета должен быть уникальный id")
        ids.add(w.get("id"))
        if w.get("type") not in WIDGET_TYPES:
            errs.append(f"Виджет «{w.get('title_ru', w.get('id'))}»: неизвестный тип")
        src = w.get("source") or {}
        if w.get("type") != "text" and src.get("kind") not in SOURCE_KINDS:
            errs.append(f"Виджет «{w.get('title_ru', w.get('id'))}»: не выбран источник данных")
        if w.get("tab") and w["tab"] not in tabs:
            errs.append(f"Виджет «{w.get('title_ru')}»: вкладка «{w['tab']}» не найдена")
    return errs


@app.get("/dashboards", tags=["дашборды"])
def list_boards(user: User = Depends(require("dashboard.view"))):
    out = []
    for d in boards.list():
        if d.get("deleted") or not _can_view(d, user):
            continue
        out.append({k: d.get(k) for k in ("id", "title_ru", "title_kk", "description", "visibility", "is_template",
                                           "system", "owner", "owner_name", "updated_at", "current_version")}
                   | {"can_edit": _can_edit(d, user), "widgets": len(d.get("widgets", []))})
    return sorted(out, key=lambda d: (not d["is_template"], d["title_ru"]))


@app.get("/dashboards/{did}", tags=["дашборды"])
def get_board(did: str, user: User = Depends(require("dashboard.view"))):
    return _get(did, user)


@app.post("/dashboards", tags=["дашборды"], status_code=201)
def create_board(body: BoardIn, user: User = Depends(require("dashboard.edit"))):
    d = body.model_dump()
    comment = d.pop("comment")
    errs = _check(d)
    if errs:
        raise AppError("dashboard.invalid", "Дашборд задан с ошибками", 422, errs)
    b = boards.create({**d, "owner": user.id, "owner_name": user.name, "is_template": False, "system": False}, actor=user.id)
    boards.add_version(b["id"], {"dashboard.json": dumps(d).encode()}, {"comment": comment or "создание"}, user.id)
    audit(user, "dashboard.create", b["id"], {"title": d["title_ru"]})
    return _get(b["id"], user)


@app.put("/dashboards/{did}", tags=["дашборды"])
def update_board(did: str, body: BoardIn, user: User = Depends(require("dashboard.edit"))):
    cur = _get(did, user)
    if not cur["can_edit"]:
        raise AppError("auth.forbidden", "Изменять этот дашборд может владелец (шаблоны — администратор и математик)", 403)
    d = body.model_dump()
    comment = d.pop("comment")
    errs = _check(d)
    if errs:
        raise AppError("dashboard.invalid", "Дашборд задан с ошибками", 422, errs)
    if cur.get("is_template"):
        d["visibility"] = "shared"
    boards.update(did, d, actor=user.id)
    v = boards.add_version(did, {"dashboard.json": dumps(d).encode()}, {"comment": comment}, user.id)
    audit(user, "dashboard.update", did, {"version": v["n"]})
    return _get(did, user)


class CopyIn(BaseModel):
    title_ru: str | None = None
    visibility: str = "private"


@app.post("/dashboards/{did}/copy", tags=["дашборды"], status_code=201)
def copy_board(did: str, body: CopyIn, user: User = Depends(require("dashboard.edit"))):
    src = _get(did, user)
    data = {k: copy.deepcopy(src.get(k)) for k in ("title_kk", "description", "filters", "tabs", "widgets")}
    b = BoardIn(title_ru=body.title_ru or f"{src['title_ru']} (копия)", visibility=body.visibility, **data,
                comment=f"копия дашборда «{src['title_ru']}»")
    out = create_board(b, user)
    boards.update(out["id"], {"copied_from": did}, actor=user.id)
    return _get(out["id"], user)


@app.delete("/dashboards/{did}", tags=["дашборды"])
def delete_board(did: str, user: User = Depends(require("dashboard.edit"))):
    cur = _get(did, user)
    if cur.get("system"):
        raise AppError("dashboard.system", "Системный шаблон удалить нельзя", 400)
    if not cur["can_edit"]:
        raise AppError("auth.forbidden", "Удалить дашборд может только владелец", 403)
    boards.delete(did)
    audit(user, "dashboard.delete", did)
    return {"ok": True}


@app.get("/dashboards/{did}/versions", tags=["дашборды"])
def versions(did: str, user: User = Depends(require("dashboard.view"))):
    _get(did, user)
    return list(reversed(boards.list_versions(did)))


# ================================================================ данные виджетов
class DataIn(BaseModel):
    source: dict
    filters: dict = {}          # water_body | water_bodies, species (код), year
    options: dict = {}


def _species_names():
    recs = SVC["data_model"].get("/entities/species/records") or []
    return {r["values"]["code"]: r["values"]["name_ru"] for r in recs}


def _gear_names():
    recs = SVC["data_model"].get("/entities/gears/records") or []
    return {r["values"]["code"]: r["values"]["name_ru"] for r in recs}


def _monitoring_run(wb, algorithm=None):
    q = f"?algorithm={algorithm}" if algorithm else ""
    return SVC["algo_admin"].get(f"/water-bodies/{wb}/monitoring-run{q}") or {"run": None}


def _step_index(run, algorithm):
    for i, s in enumerate(run["steps"]):
        if s["algorithm"] == algorithm and s.get("status") in ("done", "reused"):
            return i
    return None


def _subst(v, ctx):
    if isinstance(v, str) and v.startswith("$"):
        return ctx.get(v[1:], v)
    return v


def _rows_dataset(wb, dtype, ctx):
    bundle = SVC["data_admin"].get(f"/bundle/{wb}") or {}
    if dtype not in bundle:
        return None, None
    src = bundle[dtype]
    data = SVC["data_admin"].get(f"/datasets/{src['dataset_id']}/data", version=src["version"])
    table = data["table"]
    gears = _gear_names()
    rows = []
    for r in table["rows"]:
        r = dict(r)
        if "gear" in r:
            r["gear"] = gears.get(r["gear"], r["gear"])
        rows.append(r)
    return rows, {"dataset_id": src["dataset_id"], "version": src["version"], "species": table.get("species", [])}


def _rows_run(wb, algorithm, table, run_id=None):
    if run_id:
        run = SVC["algo_admin"].get(f"/runs/{run_id}")
        info = {"run": run, "is_main": None}
    else:
        info = _monitoring_run(wb, algorithm)
        run = info.get("run")
    if not run:
        return None, {"reason": "no_run"}
    i = _step_index(run, algorithm)
    if i is None:
        return None, {"reason": "no_step", "run_id": run["id"]}
    res = SVC["algo_admin"].get(f"/runs/{run['id']}/steps/{i}/result")
    meta = {"run_id": run["id"], "is_main": info.get("is_main"), "run_finished_at": run.get("finished_at"),
            "calculation_title": run.get("calculation_title")}
    if table is None:
        return res, meta
    t = (res.get("tables") or {}).get(table)
    if not t:
        return None, {**meta, "reason": "no_table"}
    return t["rows"], {**meta, "columns": t["columns"], "title": t["title"]}


def _aggregate(rows, x, y, series, agg):
    groups: dict = OrderedDict()
    xs = []
    for r in rows:
        xv = r.get(x)
        if xv not in xs:
            xs.append(xv)
        key = r.get(series) if series else "_"
        val = r.get(y) if y != "count" else 1
        g = groups.setdefault(key, {})
        g.setdefault(xv, []).append(val)
    try:
        xs = sorted(xs, key=lambda v: (v is None, v))
    except TypeError:
        pass
    out = []
    for key, g in groups.items():
        vals = []
        for xv in xs:
            items = [v for v in g.get(xv, []) if v is not None]
            if not items:
                vals.append(None)
            elif agg == "mean":
                vals.append(sum(items) / len(items))
            elif agg == "last":
                vals.append(items[-1])
            elif agg == "count":
                vals.append(len(g.get(xv, [])))
            else:
                vals.append(sum(items))
        out.append({"name": key if key != "_" else None, "values": vals})
    return {"x": xs, "series": out}


def _filter(rows, flt, ctx):
    out = []
    for r in rows:
        ok = True
        for k, v in (flt or {}).items():
            v = _subst(v, ctx)
            if v in (None, "", []):
                continue
            if isinstance(v, list):
                ok &= r.get(k) in v
            else:
                ok &= r.get(k) == v
        if ok:
            out.append(r)
    return out


@app.post("/widgets/data", tags=["данные виджетов"])
def widget_data(body: DataIn, user: User = Depends(require("dashboard.view"))):
    src, flt, opt = body.source, body.filters, body.options
    kind = src.get("kind")
    sp_names = _species_names()
    species = flt.get("species")
    wbs = flt.get("water_bodies") if src.get("multi") else None
    wbs = wbs or ([flt.get("water_body")] if flt.get("water_body") else [])
    if kind in ("dataset", "run", "payload", "insight") and not wbs:
        return {"empty": True, "reason": "no_water_body", "message": "Выберите водоём"}  # noqa
    if kind == "insight":
        return _insight(src, flt, opt, wbs[0])
    if kind == "status":
        wb = wbs[0]
        data = SVC["data_admin"].get("/water-bodies/status") or {}
        runs = SVC["algo_admin"].get("/water-bodies/status") or {}
        return {"data": data.get(wb), "runs": runs.get(wb)}
    if kind == "payload":
        res, meta = _rows_run(wbs[0], src["algorithm"], None, src.get("run_id"))
        if res is None:
            return {"empty": True, **meta, "message": _empty_msg(meta)}
        return {"payload": res.get("payload"), "tables": {k: {"title": v["title"], "columns": v["columns"]}
                                                           for k, v in (res.get("tables") or {}).items()},
                "metrics": res.get("metrics"), "notes": res.get("notes"), "meta": meta}
    all_rows, meta_all = [], {}
    for wb in wbs:
        if kind == "dataset":
            rows, meta = _rows_dataset(wb, src["dataset_type"], {})
            if rows is None:
                continue
        elif kind == "run":
            rows, meta = _rows_run(wb, src["algorithm"], src["table"], src.get("run_id"))
            if rows is None:
                if len(wbs) == 1:
                    return {"empty": True, **meta, "message": _empty_msg(meta)}
                continue
        else:
            raise AppError("widget.source", "Неизвестный источник данных", 400)
        for r in rows:
            r = dict(r)
            r["water_body"] = wb
            all_rows.append(r)
        meta_all = meta
    if not all_rows:
        return {"empty": True, "message": "Нет данных для выбранных фильтров"}
    years = sorted({r.get("year") for r in all_rows if isinstance(r.get("year"), int)})
    ctx = {"last_year": years[-1] if years else None, "water_body": wbs[0], "species": species,
           "species_ru": sp_names.get(species) if species else None}
    y = opt.get("y")
    rows = all_rows
    if kind == "run" and species and rows and "species" in rows[0]:
        rows = [r for r in rows if r.get("species") in (species, sp_names.get(species))]
    rows = _filter(rows, opt.get("filter"), ctx)
    if y == "$species":
        if kind == "dataset":
            y = species or None
            if y is None:  # сумма по всем видам
                spc = meta_all.get("species", [])
                for r in rows:
                    r["_all"] = sum(r.get(s) or 0 for s in spc) if any(r.get(s) is not None for s in spc) else None
                y = "_all"
    if body.options.get("raw") or opt.get("type") == "table" or not opt.get("x"):
        cols = meta_all.get("columns")
        if not cols and rows:
            cols = [{"code": k, "title": sp_names.get(k, k)} for k in rows[0].keys() if not k.startswith("_")]
        limit = int(opt.get("limit", 2000))
        return {"columns": cols, "rows": rows[:limit], "total": len(rows), "meta": meta_all, "years": years}
    agg = _aggregate(rows, opt["x"], y, opt.get("series"), opt.get("agg", "sum"))
    return {**agg, "meta": meta_all, "years": years, "y": y,
            "y_title": sp_names.get(y, y) if y not in (None, "_all") else "все виды"}


def _empty_msg(meta):
    r = meta.get("reason")
    return {"no_run": "Для водоёма ещё нет выполненного расчёта",
            "no_step": "В запуске для мониторинга нет этого шага расчёта",
            "no_table": "В результатах шага нет этой таблицы"}.get(r, "Нет данных")


# ================================================================ представления исходных данных
def _rules() -> dict:
    d = settings.get("signal_rules")
    return {r["code"]: r for r in (d or {}).get("rules", [])}


def _all_wbs(lang):
    recs = SVC["data_model"].get("/entities/water_bodies/records") or []
    names = {r["values"]["code"]: (lang == "kk" and r["values"].get("name_kk")) or r["values"]["name_ru"] for r in recs}
    st = SVC["data_admin"].get("/water-bodies/status") or {}
    return [(c, names.get(c, c), insights.Data(c, SVC, lang)) for c in st if "species_props" in (st[c].get("datasets") or {})]


def _insight(src, flt, opt, wb):
    view = src.get("view")
    fn = insights.VIEWS.get(view)
    if fn is None:
        raise AppError("widget.view", f"Неизвестное представление «{view}»", 400)
    lang = flt.get("lang") or opt.get("lang") or "ru"
    D = insights.Data(wb, SVC, lang)
    o = {**{k: v for k, v in opt.items() if k not in ("raw",)}, "species": flt.get("species") or opt.get("species")}
    if flt.get("year"):
        o["year"] = flt["year"]
    for k in ("variant", "method", "bages", "bdata", "bdetail", "scenario", "hmode"):      # варианты расчёта — общие для слайдов вкладки
        if flt.get(k):
            o[k] = flt[k]
    try:
        if view in insights.NEEDS_RULES:
            res = fn(D, o, _rules())
        elif view == "params_compare":
            res = fn(D, o, _all_wbs(lang))
        else:
            res = fn(D, o)
    except insights.NoData as e:
        return {"empty": True, "message": kk.tr(e.message) if lang == "kk" else e.message}
    if lang == "kk":
        res = kk.translate(res)
    sp = o.get("species") or res.get("species_shown")
    res["explain"] = explain.explain(view, res, lang, o, D.sp_name(sp) if sp else None,
                                     _rules() if view in ("sample_size",) else None)
    cmp = flt.get("compare") or []
    if len(cmp) == 2 and all(cmp):
        res = insights.compare_years(res, int(cmp[0]), int(cmp[1]))
    return {**res, "view": view}


class DrillIn(BaseModel):
    source: dict
    filters: dict = {}
    options: dict = {}
    where: dict = {}
    dataset_type: str | None = None


@app.post("/widgets/drill", tags=["данные виджетов"])
def widget_drill(body: DrillIn, user: User = Depends(require("dashboard.view"))):
    """Строки исходных данных, из которых сложилась точка, столбец или клетка представления."""
    wb = body.filters.get("water_body")
    if not wb:
        raise AppError("widget.wb", "Выберите водоём", 400)
    dtype = body.dataset_type or body.where.pop("_dataset_type", None) or "catches"
    D = insights.Data(wb, SVC, body.filters.get("lang") or "ru")
    o = {**body.options, "species": body.filters.get("species")}
    lang = body.filters.get("lang") or "ru"
    try:
        res = insights.drill_rows(D, dtype, body.where, o)
        return kk.translate(res) if lang == "kk" else res
    except insights.NoData as e:
        return {"empty": True, "message": kk.tr(e.message) if lang == "kk" else e.message, "columns": [], "rows": [], "total": 0}


class ExportIn(BaseModel):
    title: str
    subtitle: str = ""
    context: str = ""
    columns: list[dict] = []
    rows: list[dict] = []
    sources: list[dict] = []
    notes: list[str] = []
    filter_label: str = ""
    image: str | None = None


def _fname(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s)[:60] or "widget"


@app.post("/widgets/export.xlsx", tags=["выгрузка"])
def export_xlsx(body: ExportIn, user: User = Depends(require("dashboard.view"))):
    content = export.to_xlsx(body.model_dump())
    from urllib.parse import quote
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(_fname(body.title))}.xlsx"})


@app.post("/widgets/export.pdf", tags=["выгрузка"])
def export_pdf(body: ExportIn, user: User = Depends(require("dashboard.view"))):
    content = export.to_pdf(body.title, body.context, [body.model_dump()])
    from urllib.parse import quote
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(_fname(body.title))}.pdf"})


class ReportIn(BaseModel):
    title: str
    context: str = ""
    widgets: list[ExportIn] = []


@app.post("/reports/section.pdf", tags=["выгрузка"])
def section_pdf(body: ReportIn, user: User = Depends(require("dashboard.view"))):
    """Отчёт раздела: все виджеты раздела одним PDF (рисунки и таблицы такие, как на экране)."""
    content = export.to_pdf(body.title, body.context, [w.model_dump() for w in body.widgets])
    audit(user, "dashboard.report", "section", {"title": body.title, "widgets": len(body.widgets)})
    from urllib.parse import quote
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(_fname(body.title))}.pdf"})


# ================================================================ правила замечаний
@app.get("/signal-rules", tags=["правила замечаний"])
def get_signal_rules(user: User = Depends(require("dashboard.view"))):
    """Правила «На что обратить внимание»: описание, пороги (по умолчанию и текущие), включено ли."""
    cur = _rules()
    out = []
    for r in insights.RULES:
        en, p = insights.rule_params(cur, r["code"])
        out.append({**r, "enabled": en, "values": p})
    d = settings.get("signal_rules") or {}
    return {"rules": out, "updated_at": d.get("updated_at"), "updated_by": d.get("updated_by_name"),
            "can_edit": user.can("dashboard.edit")}


class RulesIn(BaseModel):
    rules: list[dict]
    comment: str = ""


@app.put("/signal-rules", tags=["правила замечаний"])
def put_signal_rules(body: RulesIn, user: User = Depends(require("dashboard.edit"))):
    errs, clean = [], []
    for r in body.rules:
        d = insights.RULES_BY.get(r.get("code"))
        if not d:
            errs.append(f"Неизвестное правило «{r.get('code')}»")
            continue
        vals = {}
        for k, spec in d["params"].items():
            v = (r.get("values") or r.get("params") or {}).get(k, spec["default"])
            try:
                v = float(v)
            except (TypeError, ValueError):
                errs.append(f"«{d['title_ru']}»: «{spec['title']}» — нужно число")
                continue
            if v < spec.get("min", float("-inf")) or v > spec.get("max", float("inf")):
                errs.append(f"«{d['title_ru']}»: «{spec['title']}» — от {spec.get('min')} до {spec.get('max')}")
            vals[k] = int(v) if v == int(v) else v
        clean.append({"code": d["code"], "enabled": bool(r.get("enabled", True)), "params": vals})
    if errs:
        raise AppError("rules.invalid", "Правила заданы с ошибками", 422, errs)
    if settings.exists("signal_rules"):
        settings.update("signal_rules", {"rules": clean, "updated_by_name": user.name}, actor=user.id)
    else:
        settings.create({"rules": clean, "updated_by_name": user.name}, actor=user.id, obj_id="signal_rules")
    settings.add_version("signal_rules", {"rules.json": dumps(clean).encode()}, {"comment": body.comment}, user.id)
    audit(user, "dashboard.signal_rules", "signal_rules", {"rules": len(clean)})
    return get_signal_rules(user)


@app.get("/signal-rules/versions", tags=["правила замечаний"])
def signal_rules_versions(user: User = Depends(require("dashboard.view"))):
    return list(reversed(settings.list_versions("signal_rules"))) if settings.exists("signal_rules") else []


# ================================================================ комментарии к виджетам
comments = Collection(ROOT, "comments")


def _ckey(c):
    return c.get("board"), c.get("widget"), c.get("water_body"), c.get("species") or None


@app.get("/comments/counts", tags=["комментарии"])
def comment_counts(board: str, water_body: str | None = None, species: str | None = None,
                   user: User = Depends(require("dashboard.view"))):
    """Число комментариев к каждому виджету дашборда для водоёма и вида."""
    out: dict[str, int] = {}
    for c in comments.list():
        if c.get("deleted") or c.get("board") != board or c.get("water_body") != water_body or (c.get("species") or None) != (species or None):
            continue
        out[c["widget"]] = out.get(c["widget"], 0) + 1
    return out


@app.get("/comments", tags=["комментарии"])
def list_comments(board: str, widget: str, water_body: str | None = None, species: str | None = None,
                  user: User = Depends(require("dashboard.view"))):
    key = (board, widget, water_body, species or None)
    out = [{**c, "can_delete": c.get("author_id") == user.id or user.role == "admin"}
           for c in comments.list() if not c.get("deleted") and _ckey(c) == key]
    return sorted(out, key=lambda c: (c.get("created_at") or "", c.get("id") or ""), reverse=True)


class CommentIn(BaseModel):
    board: str
    widget: str
    water_body: str | None = None
    species: str | None = None
    year: int | None = None
    text: str


@app.post("/comments", tags=["комментарии"], status_code=201)
def add_comment(body: CommentIn, user: User = Depends(require("dashboard.edit"))):
    text = body.text.strip()
    if not text:
        raise AppError("comment.empty", "Напишите текст комментария", 422)
    if len(text) > 2000:
        raise AppError("comment.long", "Комментарий — не длиннее 2000 символов", 422)
    _get(body.board, user)
    c = comments.create({**body.model_dump(), "text": text, "species": body.species or None,
                         "author_id": user.id, "author_name": user.name}, actor=user.id)
    audit(user, "dashboard.comment", body.board, {"widget": body.widget, "water_body": body.water_body})
    return {**c, "can_delete": True}


@app.delete("/comments/{cid}", tags=["комментарии"])
def delete_comment(cid: str, user: User = Depends(require("dashboard.view"))):
    c = comments.get(cid)
    if not c or c.get("deleted"):
        raise not_found("Комментарий")
    if c.get("author_id") != user.id and user.role != "admin":
        raise AppError("auth.forbidden", "Удалить комментарий может автор или администратор", 403)
    comments.delete(cid)
    audit(user, "dashboard.comment_delete", c.get("board"), {"comment": cid})
    return {"ok": True}
