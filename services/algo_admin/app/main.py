"""
Сервис 3. Администрирование алгоритмов расчёта.

Каталог опубликованных версий алгоритмов (включение/отключение), профили параметров водоёмов,
расчёты — цепочки шагов с наборами данных и параметрами, очередь запусков с воркерами,
статусы, история, результаты, выгрузка, основной запуск водоёма.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, current_user, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import atomic_write_json, now_iso, read_json

from . import params as P
from .clients import Clients
from .engine import STEP_ORDER, TERMINAL, Engine, build

app = create_app("algo_admin", "Администрирование алгоритмов расчёта",
                 "Каталог версий алгоритмов, профили водоёмов, расчёты, очередь запусков, результаты.")
ST = app.state.settings
ROOT = ST.service_dir()
E = Engine(ROOT)
CLIENTS = Clients(ST)
MAIN_RUNS = ROOT / "main_runs.json"


def audit(user, action, otype, oid, details=None):
    app.state.audit.log(user, action, otype, oid, details)


E.seed_builtin()


# ================================================================ каталог
@app.get("/catalog", tags=["каталог"])
def catalog(user: User = Depends(require("catalog.view"))):
    out = []
    for a in E.catalog.list():
        vs = E.versions(a["code"])
        latest = next((v for v in vs if v["enabled"]), None)
        out.append({**a, "versions": [{k: v.get(k) for k in ("version", "checksum", "enabled", "source", "created_at",
                                                            "created_by", "report")} for v in vs],
                    "latest": latest["version"] if latest else None,
                    "manifest": latest["manifest"] if latest else (vs[0]["manifest"] if vs else None),
                    "order": STEP_ORDER.get(a["code"], 99)})
    return sorted(out, key=lambda a: (a["order"], a["code"]))


@app.get("/catalog/{code}", tags=["каталог"])
def catalog_item(code: str, user: User = Depends(require("catalog.view"))):
    a = E.catalog.get(code)
    if not a:
        raise not_found("Алгоритм")
    return {**a, "versions": E.versions(code)}


@app.get("/catalog/{code}/versions/{version}/package.zip", tags=["каталог"])
def package(code: str, version: str, user: User = Depends(require("catalog.view"))):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    return Response(E.package_zip(code, version), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{code}-{version}.zip"'})


@app.get("/catalog/{code}/versions/{version}/files", tags=["каталог"])
def package_files(code: str, version: str, path: str | None = None, user: User = Depends(require("catalog.view"))):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    files = E.package_files(code, version)
    if path:
        if path not in files:
            raise not_found("Файл")
        return {"path": path, "text": files[path].decode("utf-8", errors="replace")}
    return [{"path": k, "size": len(v)} for k, v in sorted(files.items())]


def _toggle(code, version, enabled, user):
    if not E.find_version(code, version):
        raise not_found("Версия алгоритма")
    E.set_enabled(code, version, enabled, user.id)
    audit(user, "catalog.enable" if enabled else "catalog.disable", "algorithm", code, {"version": version})
    return catalog_item(code, user)


@app.post("/catalog/{code}/versions/{version}/enable", tags=["каталог"])
def enable(code: str, version: str, user: User = Depends(require("catalog.manage"))):
    return _toggle(code, version, True, user)


@app.post("/catalog/{code}/versions/{version}/disable", tags=["каталог"])
def disable(code: str, version: str, user: User = Depends(require("catalog.manage"))):
    return _toggle(code, version, False, user)


@app.post("/internal/catalog/publish", tags=["каталог"], include_in_schema=False)
async def internal_publish(package: UploadFile = File(...), report: str = Form("{}"), author: str = Form(""),
                           user: User = Depends(current_user)):
    """Публикация проверенной версии из сервиса «Моделирование алгоритмов»."""
    if not user.is_service:
        raise AppError("auth.forbidden", "Только для сервисов", 403)
    data = await package.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    manifest = json.loads(files["manifest.json"])
    try:
        v = E.publish(manifest, files, actor=author or "algo_model", source="algo_model", report=json.loads(report))
    except ValueError as e:
        raise AppError("catalog.exists", str(e), 409)
    return {"ok": True, "version": v}


# ================================================================ профили водоёмов
def _waterbody_params(manifest):
    return [p for p in manifest.get("parameters", []) if p.get("category") == "waterbody"]


def _profile_schema(code: str):
    v = E.latest_enabled(code)
    if not v:
        return None, []
    files = E.package_files(code, v["version"])
    schema = json.loads(files["profile_schema.json"]) if "profile_schema.json" in files else None
    return schema, _waterbody_params(v["manifest"])


@app.get("/profiles", tags=["профили водоёмов"])
def list_profiles(water_body: str | None = None, algorithm: str | None = None,
                  user: User = Depends(require("profile.view"))):
    out = []
    for p in E.profiles.list():
        if water_body and p["water_body"] != water_body:
            continue
        if algorithm and p["algorithm"] != algorithm:
            continue
        out.append(p)
    return out


@app.get("/profiles/{code}/{water_body}", tags=["профили водоёмов"])
def get_profile(code: str, water_body: str, user: User = Depends(require("profile.view"))):
    schema, wparams = _profile_schema(code)
    prof = E.get_profile(code, water_body)
    pid = E.profile_id(code, water_body)
    return {"algorithm": code, "water_body": water_body, "profile": prof, "schema": schema, "parameters": wparams,
            "versions": list(reversed(E.profiles.list_versions(pid))) if prof else [],
            "available_sources": sorted({p["water_body"] for p in E.profiles.list() if p["algorithm"] == code})}


@app.get("/profiles/{code}/{water_body}/versions/{n}", tags=["профили водоёмов"])
def profile_version(code: str, water_body: str, n: int, user: User = Depends(require("profile.view"))):
    return E.profile_version_values(code, water_body, n)


class ProfileIn(BaseModel):
    values: dict
    comment: str = ""


def _validate_profile(code: str, values: dict) -> list[str]:
    schema, wparams = _profile_schema(code)
    errors = []
    for p in wparams:
        if p.get("type") == "profile":
            prof = values.get(p["code"]) or {}
            if not isinstance(prof, dict):
                errors.append("Профиль по видам должен быть набором значений")
                continue
            if code == "bayes_cohort":
                from fishcore.bayes import config as bc  # пакеты алгоритмов доступны сервису (algorithms/)
                names = CLIENTS.species_names()
                for sp, vals in prof.items():
                    errs = bc.validate(names.get(sp, sp), vals)
                    errors += [f"{names.get(sp, sp)}: {e}" for e in errs]
        else:
            _, err = P.check_value(p, values.get(p["code"]))
            if err:
                errors.append(err)
    return errors


@app.put("/profiles/{code}/{water_body}", tags=["профили водоёмов"])
def save_profile(code: str, water_body: str, body: ProfileIn, user: User = Depends(require("profile.edit"))):
    if not E.catalog.exists(code):
        raise not_found("Алгоритм")
    errors = _validate_profile(code, body.values)
    if errors:
        raise AppError("profile.invalid", "Профиль содержит ошибки", 422, errors)
    p = E.save_profile(code, water_body, body.values, user.id, body.comment)
    audit(user, "profile.save", "profile", E.profile_id(code, water_body), {"version": p["current_version"]})
    return get_profile(code, water_body, user)


@app.post("/profiles/{code}/{water_body}/copy-from/{source}", tags=["профили водоёмов"])
def copy_profile(code: str, water_body: str, source: str, user: User = Depends(require("profile.edit"))):
    src = E.get_profile(code, source)
    if not src:
        raise not_found("Профиль-источник")
    E.save_profile(code, water_body, src["values"], user.id, f"скопирован из профиля водоёма «{source}» — проверьте значения")
    audit(user, "profile.copy", "profile", E.profile_id(code, water_body), {"from": source})
    return get_profile(code, water_body, user)


# ================================================================ расчёты
class StepIn(BaseModel):
    algorithm: str
    version: str | None = None      # None — последняя включённая версия на момент запуска


class CalcIn(BaseModel):
    title: str
    water_body: str
    description: str = ""
    steps: list[StepIn]
    params: dict = {}               # {код алгоритма: {параметр запуска: значение}}
    datasets: dict = {}             # {тип набора: {"dataset_id", "version"}} — пусто: текущие версии
    result_formats: list[str] = ["json", "xlsx", "nc"]
    comment: str = ""


def _calc(cid):
    c = E.calculations.get(cid)
    if not c or c.get("deleted"):
        raise not_found("Расчёт")
    return c


def _check_steps(steps: list[dict]) -> list[str]:
    errs = []
    codes = [s["algorithm"] for s in steps]
    if not codes:
        errs.append("В расчёте нет ни одного шага")
    if len(codes) != len(set(codes)):
        errs.append("Алгоритм повторяется в цепочке")
    for s in steps:
        if not E.catalog.exists(s["algorithm"]):
            errs.append(f"Алгоритм «{s['algorithm']}» не найден в каталоге")
            continue
        if s.get("version"):
            v = next((x for x in E.versions(s["algorithm"]) if x["version"] == s["version"]), None)
            if not v:
                errs.append(f"{s['algorithm']}: версии {s['version']} нет")
            elif not v["enabled"]:
                errs.append(f"{s['algorithm']} {s['version']}: версия отключена")
        elif not E.latest_enabled(s["algorithm"]):
            errs.append(f"{s['algorithm']}: нет включённых версий")
    known = [c for c in codes if c in STEP_ORDER]
    if known != sorted(known, key=lambda c: STEP_ORDER[c]):
        errs.append("Шаги идут не в порядке методики (уловистость невода → запас → ПДУ по возрастам → модель → прогноз)")
    return errs


@app.get("/calculations", tags=["расчёты"])
def list_calcs(water_body: str | None = None, user: User = Depends(require("run.view"))):
    return [c for c in E.calculations.list() if not c.get("deleted") and (not water_body or c["water_body"] == water_body)]


@app.post("/calculations", tags=["расчёты"], status_code=201)
def create_calc(body: CalcIn, user: User = Depends(require("run.execute"))):
    d = body.model_dump()
    comment = d.pop("comment")
    errs = _check_steps(d["steps"])
    if errs:
        raise AppError("calc.invalid", "Расчёт задан с ошибками", 422, errs)
    c = E.calculations.create(d, actor=user.id)
    E.calculations.add_version(c["id"], {"definition.json": json.dumps(d, ensure_ascii=False).encode()},
                               {"comment": comment or "создание"}, user.id)
    audit(user, "calc.create", "calculation", c["id"], {"title": d["title"], "water_body": d["water_body"]})
    return E.calculations.get(c["id"])


@app.get("/calculations/{cid}", tags=["расчёты"])
def get_calc(cid: str, user: User = Depends(require("run.view"))):
    c = _calc(cid)
    return {**c, "versions": list(reversed(E.calculations.list_versions(cid)))}


@app.put("/calculations/{cid}", tags=["расчёты"])
def update_calc(cid: str, body: CalcIn, user: User = Depends(require("run.execute"))):
    _calc(cid)
    d = body.model_dump()
    comment = d.pop("comment")
    errs = _check_steps(d["steps"])
    if errs:
        raise AppError("calc.invalid", "Расчёт задан с ошибками", 422, errs)
    E.calculations.update(cid, d, actor=user.id)
    v = E.calculations.add_version(cid, {"definition.json": json.dumps(d, ensure_ascii=False).encode()},
                                   {"comment": comment}, user.id)
    audit(user, "calc.update", "calculation", cid, {"version": v["n"]})
    return get_calc(cid, user)


@app.delete("/calculations/{cid}", tags=["расчёты"])
def delete_calc(cid: str, user: User = Depends(require("run.execute"))):
    _calc(cid)
    E.calculations.delete(cid)
    audit(user, "calc.delete", "calculation", cid)
    return {"ok": True}


TEMPLATES = {
    "full": ("Полный расчёт ПДУ (этапы 1–5)", build.ORDER),
    "stock": ("Запас по уловам и ПДУ НПЦ по возрастам (этапы 1–3)", build.ORDER[:3]),
    "bayes_forecast": ("Байесовская модель и прогноз (этапы 1–5, модель — только выбранные виды)", build.ORDER),
}


class TemplateIn(BaseModel):
    water_body: str
    template: str = "full"


@app.post("/calculations/from-template", tags=["расчёты"], status_code=201)
def from_template(body: TemplateIn, user: User = Depends(require("run.execute"))):
    if body.template not in TEMPLATES:
        raise AppError("calc.template", "Неизвестный шаблон расчёта", 400)
    title, steps = TEMPLATES[body.template]
    wbs = CLIENTS.water_bodies()
    if body.water_body not in wbs:
        raise AppError("calc.water_body", "Водоём не найден в справочнике", 404)
    return create_calc(CalcIn(title=f"{title} — {wbs[body.water_body]['name_ru']}", water_body=body.water_body,
                              steps=[StepIn(algorithm=s) for s in steps]), user)


def _plan(c: dict, overrides: dict | None = None) -> tuple[dict, list[str], list[str]]:
    """План запуска: версии, параметры, наборы данных. Возвращает (план, ошибки, предупреждения)."""
    errors, warnings = [], []
    errors += _check_steps(c["steps"])
    if errors:
        return {}, errors, warnings
    current = CLIENTS.current_datasets(c["water_body"])
    names = CLIENTS.species_names()
    datasets = {}
    steps = []
    need = set()
    for s in c["steps"]:
        v = s.get("version") or E.latest_enabled(s["algorithm"])["version"]
        m = E.manifest(s["algorithm"], v)
        need |= set(m.get("requires", {}).get("datasets", []))
        run_vals = {**(c.get("params", {}).get(s["algorithm"]) or {}), **((overrides or {}).get(s["algorithm"]) or {})}
        prof = E.get_profile(s["algorithm"], c["water_body"])
        if _waterbody_params(m) and not prof:
            if s["algorithm"] == "bayes_cohort":
                errors.append("Нет профиля параметров байесовской модели для этого водоёма: "
                              "Каталог → Профили водоёмов (можно скопировать профиль Жайсана и проверить)")
        merged, errs = P.merge(m, (prof or {}).get("values"), run_vals, set(names))
        errors += [f"{m['title_ru']}: {e}" for e in errs]
        steps.append({"algorithm": s["algorithm"], "version": v, "title": m["title_ru"], "params": merged,
                      "profile_version": (prof or {}).get("current_version"), "status": "pending",
                      "checksum": E.find_version(s["algorithm"], v)["checksum"]})
        for dep in m.get("requires", {}).get("steps", []):
            if dep not in [x["algorithm"] for x in c["steps"]]:
                warnings.append(f"«{m['title_ru']}»: шаг «{dep}» не входит в цепочку — будет рассчитан внутри шага"
                                if s["algorithm"] != "forecast_pdu" else
                                f"«{m['title_ru']}» требует шаг «Байесовская когортная модель» в цепочке")
                if s["algorithm"] == "forecast_pdu" and dep == "bayes_cohort":
                    errors.append("Прогноз требует шаг «Байесовская когортная модель» в цепочке")
    for t in sorted(need):
        pinned = (c.get("datasets") or {}).get(t)
        if pinned:
            datasets[t] = pinned
        elif t in current:
            datasets[t] = {"dataset_id": current[t]["dataset_id"], "version": current[t]["version"]}
        elif t not in ("npc_stock",):
            errors.append(f"Для водоёма не загружен набор данных «{t}»")
    for t in ("npc_stock",):
        if t in need and t not in datasets and t in current:
            datasets[t] = {"dataset_id": current[t]["dataset_id"], "version": current[t]["version"]}
    return {"steps": steps, "datasets": datasets}, errors, warnings


class RunIn(BaseModel):
    params: dict = {}
    from_step: str | None = None      # начать с шага (предыдущие — из базового запуска)
    base_run: str | None = None
    comment: str = ""


@app.post("/calculations/{cid}/check", tags=["расчёты"])
def check_calc(cid: str, body: RunIn = RunIn(), user: User = Depends(require("run.view"))):
    plan, errors, warnings = _plan(_calc(cid), body.params)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "plan": plan}


@app.post("/calculations/{cid}/run", tags=["запуски"], status_code=201)
def start_run(cid: str, body: RunIn, user: User = Depends(require("run.execute"))):
    c = _calc(cid)
    plan, errors, warnings = _plan(c, body.params)
    if errors:
        raise AppError("run.invalid", "Расчёт нельзя запустить", 422, errors)
    if body.from_step:
        if not body.base_run:
            raise AppError("run.base", "Для запуска с шага нужен базовый запуск", 400)
        base = E.runs.get(body.base_run)
        if not base or base.get("status") != "done":
            raise AppError("run.base", "Базовый запуск не найден или не завершён", 400)
        codes = [s["algorithm"] for s in plan["steps"]]
        if body.from_step not in codes:
            raise AppError("run.base", "Шаг не входит в расчёт", 400)
        k = codes.index(body.from_step)
        for i in range(k):
            bs = next((x for x in base["steps"] if x["algorithm"] == plan["steps"][i]["algorithm"]), None)
            if not bs or bs.get("checksum") != plan["steps"][i]["checksum"] or base["datasets"] != plan["datasets"]:
                raise AppError("run.base", f"Шаг «{plan['steps'][i]['title']}» базового запуска выполнен с другой версией "
                                           "алгоритма или данных — запустите расчёт целиком", 400)
            plan["steps"][i].update(skip=True, reuse_from=str(E.run_dir(base["id"]) / bs["dir"]),
                                    reused_run=base["id"])
    cv = c.get("current_version")
    r = E.runs.create({"calculation_id": cid, "calculation_version": cv, "calculation_title": c["title"],
                       "water_body": c["water_body"], "status": "queued", "author": user.id, "author_name": user.name,
                       "comment": body.comment, "warnings": warnings, "result_formats": c.get("result_formats"),
                       **plan}, actor=user.id)
    audit(user, "run.start", "run", r["id"], {"calculation": cid, "water_body": c["water_body"],
                                             "steps": [s["algorithm"] for s in plan["steps"]]})
    return r


# ================================================================ запуски
def _run(rid):
    r = E.runs.get(rid)
    if not r:
        raise not_found("Запуск")
    return r


def _progress(r):
    i = r.get("current_step")
    if r.get("status") != "running" or i is None:
        return None
    st = r["steps"][i]
    d = E.run_dir(r["id"]) / st.get("dir", "")
    return read_json(d / "progress.json")


@app.get("/runs", tags=["запуски"])
def list_runs(water_body: str | None = None, calculation: str | None = None, status: str | None = None,
              limit: int = 200, user: User = Depends(require("run.view"))):
    rs = [r for r in E.runs.list()
          if (not water_body or r["water_body"] == water_body) and (not calculation or r["calculation_id"] == calculation)
          and (not status or r["status"] == status)]
    rs.sort(key=lambda r: r["created_at"], reverse=True)
    mains = read_json(MAIN_RUNS, {})
    for r in rs:
        r["is_main"] = mains.get(r["water_body"], {}).get("run_id") == r["id"]
    return rs[:limit]


@app.get("/runs/{rid}", tags=["запуски"])
def get_run(rid: str, user: User = Depends(require("run.view"))):
    r = _run(rid)
    mains = read_json(MAIN_RUNS, {})
    q = E.queue()
    pos = next((i + 1 for i, x in enumerate(q) if x["id"] == rid), None)
    return {**r, "progress": _progress(r), "queue_position": pos,
            "is_main": mains.get(r["water_body"], {}).get("run_id") == rid}


def _step(r, i):
    if not 0 <= i < len(r["steps"]):
        raise not_found("Шаг")
    st = r["steps"][i]
    if st.get("status") == "reused":
        return st, Path(st["reuse_from"])
    if not st.get("dir"):
        raise AppError("run.step_pending", "Шаг ещё не выполнялся", 404)
    return st, E.run_dir(r["id"]) / st["dir"]


@app.get("/runs/{rid}/steps/{i}/result", tags=["запуски"])
def step_result(rid: str, i: int, user: User = Depends(require("run.view"))):
    st, d = _step(_run(rid), i)
    res = read_json(d / "out" / "result.json")
    if res is None:
        raise AppError("run.no_result", "У шага нет результатов", 404)
    return {"step": st, **res}


@app.get("/runs/{rid}/steps/{i}/log", tags=["запуски"])
def step_log(rid: str, i: int, user: User = Depends(require("run.view"))):
    st, d = _step(_run(rid), i)
    log = (d / "log.txt").read_text(encoding="utf-8") if (d / "log.txt").exists() else ""
    status = read_json(d / "status.json", {})
    tb = status.get("traceback") if user.role in ("admin", "mathematician") else None
    return {"log": log[-200_000:], "status": status.get("status"), "message": status.get("message"), "traceback": tb}


@app.get("/runs/{rid}/steps/{i}/files/{name}", tags=["запуски"])
def step_file(rid: str, i: int, name: str, user: User = Depends(require("run.view"))):
    st, d = _step(_run(rid), i)
    f = d / "out" / name
    if "/" in name or "\\" in name or name.startswith(".") or not f.is_file() or name == "state.pkl":
        raise not_found("Файл")
    return FileResponse(f, filename=name)


@app.post("/runs/{rid}/cancel", tags=["запуски"])
def cancel(rid: str, user: User = Depends(require("run.execute"))):
    r = _run(rid)
    if r["status"] in TERMINAL:
        raise AppError("run.finished", "Запуск уже завершён", 400)
    if r["status"] == "queued":
        E.update_run(rid, status="cancelled", finished_at=now_iso(), message="Отменён до начала выполнения")
    else:
        E.update_run(rid, cancel_requested=True)
    audit(user, "run.cancel", "run", rid)
    return get_run(rid, user)


@app.post("/runs/{rid}/main", tags=["запуски"])
def set_main(rid: str, user: User = Depends(require("run.execute"))):
    r = _run(rid)
    if r["status"] != "done":
        raise AppError("run.not_done", "Основным можно отметить только выполненный запуск", 400)
    data = read_json(MAIN_RUNS, {})
    data[r["water_body"]] = {"run_id": rid, "set_by": user.id, "set_by_name": user.name, "set_at": now_iso()}
    atomic_write_json(MAIN_RUNS, data)
    audit(user, "run.set_main", "run", rid, {"water_body": r["water_body"]})
    return get_run(rid, user)


@app.get("/runs/{rid}/export.zip", tags=["запуски"])
def export_zip(rid: str, user: User = Depends(require("run.view"))):
    r = _run(rid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("run.json", json.dumps(r, ensure_ascii=False, indent=1))
        for i, st in enumerate(r["steps"]):
            if not st.get("dir") and st.get("status") != "reused":
                continue
            _, d = _step(r, i)
            for f in sorted((d / "out").glob("*")):
                if f.is_file() and f.name != "state.pkl":
                    z.write(f, f"{i + 1:02d}_{st['algorithm']}/{f.name}")
            if (d / "log.txt").exists():
                z.write(d / "log.txt", f"{i + 1:02d}_{st['algorithm']}/log.txt")
    audit(user, "run.export", "run", rid)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="run_{rid}.zip"'})


@app.get("/runs/{rid}/report.{fmt}", tags=["запуски"])
def report(rid: str, fmt: str, lang: str = "ru", user: User = Depends(require("run.view"))):
    from . import report as rep
    r = _run(rid)
    if r["status"] != "done":
        raise AppError("run.not_done", "Отчёт доступен для выполненного запуска", 400)
    results = {}
    for i, st in enumerate(r["steps"]):
        try:
            _, d = _step(r, i)
            results[st["algorithm"]] = read_json(d / "out" / "result.json")
        except AppError:
            pass
    wb = CLIENTS.water_bodies().get(r["water_body"], {"name_ru": r["water_body"]})
    if fmt == "docx":
        data, mt = rep.docx_report(r, results, wb), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "pdf":
        data, mt = rep.pdf_report(r, results, wb), "application/pdf"
    else:
        raise AppError("report.format", "Формат отчёта: docx или pdf", 400)
    audit(user, "run.report", "run", rid, {"format": fmt})
    return Response(data, media_type=mt, headers={"Content-Disposition": f'attachment; filename="pdu_report_{rid}.{fmt}"'})


@app.get("/queue", tags=["запуски"])
def queue(user: User = Depends(require("run.view"))):
    running = [r for r in E.runs.list() if r.get("status") == "running"]
    return {"queued": E.queue(), "running": running}


# ================================================================ сводка по водоёмам
def _pdu_summary(r):
    """Итог ПДУ основного/последнего запуска: прогноз (F = k·M) или ПДУ НПЦ по возрастам."""
    for i, st in enumerate(r["steps"]):
        if st["algorithm"] == "forecast_pdu" and st.get("status") in ("done", "reused"):
            _, d = _step(r, i)
            res = read_json(d / "out" / "result.json") or {}
            rows = res.get("tables", {}).get("forecast_summary", {}).get("rows", [])
            return {"source": "forecast", "rows": [{"species": x["species"], "pdu_t": x["pdu_next_t"],
                                                    "year": x.get("year_first_fc")} for x in rows]}
    return None


@app.get("/water-bodies/status", tags=["сводка"])
def wb_status(user: User = Depends(require("run.view"))):
    mains = read_json(MAIN_RUNS, {})
    out = {}
    runs = sorted(E.runs.list(), key=lambda r: r["created_at"], reverse=True)
    for r in runs:
        s = out.setdefault(r["water_body"], {"last_run": None, "last_done": None, "main_run": None, "runs": 0})
        s["runs"] += 1
        if s["last_run"] is None:
            s["last_run"] = {k: r.get(k) for k in ("id", "status", "created_at", "finished_at", "calculation_title")}
        if r["status"] == "done" and s["last_done"] is None:
            s["last_done"] = {k: r.get(k) for k in ("id", "created_at", "finished_at", "calculation_title")}
    for wb, m in mains.items():
        r = E.runs.get(m["run_id"])
        if r:
            out.setdefault(wb, {"last_run": None, "last_done": None, "runs": 0})["main_run"] = {
                **{k: r.get(k) for k in ("id", "created_at", "finished_at", "calculation_title")}, **m}
    for wb, s in out.items():
        ref = s.get("main_run") or s.get("last_done")
        if ref:
            s["pdu"] = _pdu_summary(E.runs.get(ref["id"]))
    return out


@app.get("/water-bodies/{water_body}/monitoring-run", tags=["сводка"])
def monitoring_run(water_body: str, algorithm: str | None = None, user: User = Depends(require("run.view"))):
    """Запуск для мониторинга: основной; если его нет — последний успешный (с пометкой), при указании
    algorithm — последний успешный, в котором есть этот шаг."""
    mains = read_json(MAIN_RUNS, {})
    m = mains.get(water_body)
    if m and E.runs.get(m["run_id"]):
        return {"run": get_run(m["run_id"], user), "is_main": True}
    done = sorted((r for r in E.runs.list() if r["water_body"] == water_body and r["status"] == "done"),
                  key=lambda r: r["created_at"], reverse=True)
    if algorithm:
        done = [r for r in done if any(s["algorithm"] == algorithm and s.get("status") in ("done", "reused")
                                       for s in r["steps"])] or done
    if done:
        return {"run": get_run(done[0]["id"], user), "is_main": False}
    return {"run": None, "is_main": False}
