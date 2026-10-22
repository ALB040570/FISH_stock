"""
Сервис 6. Моделирование алгоритмов расчёта (рабочее место математика).

Проекты алгоритмов, черновики (Python-код + манифест параметров), проверка структуры и кода,
тестовый прогон на данных водоёма (с предыдущими шагами цепочки из каталога), сверка с эталонной
версией, публикация проверенной версии в «Администрирование алгоритмов».
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import traceback
import zipfile
from pathlib import Path

import httpx
from fastapi import Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import Collection, atomic_write_json, now_iso, read_json

def _algorithms_dir() -> Path:
    """Каталог пакетов алгоритмов: FISH_ALGORITHMS_DIR; в образе Docker — /srv/algorithms (рядом с app/);
    в копии репозитория — <репозиторий>/algorithms (services/<сервис>/app → на три уровня выше)."""
    if os.environ.get("FISH_ALGORITHMS_DIR"):
        return Path(os.environ["FISH_ALGORITHMS_DIR"])
    here = Path(__file__).resolve()
    candidates = [here.parents[1] / "algorithms"]
    if len(here.parents) > 3:
        candidates.append(here.parents[3] / "algorithms")
    candidates.append(Path("/srv/algorithms"))
    return next((c for c in candidates if (c / "build.py").exists()), candidates[-1])


ALGOS = _algorithms_dir()
sys.path.insert(0, str(ALGOS))
import build  # noqa: E402
import executor  # noqa: E402

app = create_app("algo_model", "Моделирование алгоритмов расчёта",
                 "Черновики алгоритмов (код и параметры), проверка, тестовый прогон, сверка, публикация версий.")
ST = app.state.settings
ROOT = ST.service_dir()
projects = Collection(ROOT, "algorithms")
drafts = Collection(ROOT, "drafts")
TESTS = ROOT / "tests"
TESTS.mkdir(exist_ok=True)
TEXT_EXT = (".py", ".json", ".md", ".txt", ".csv", ".yaml", ".yml")
CATEGORIES = ("fixed", "waterbody", "run")
PARAM_TYPES = ("integer", "number", "enum", "boolean", "string", "species_list", "year_map", "species_map",
               "species_year_map", "profile")
_test_lock = threading.Lock()


class Svc:
    def __init__(self, name, http=None):
        self.name = name
        self.http = http or httpx.Client(base_url=ST.urls[name], timeout=120)

    def _h(self):
        return {"X-Service-Token": ST.service_token}

    def get(self, path, **params):
        try:
            r = self.http.get(path, params=params or None, headers=self._h())
        except httpx.HTTPError:
            raise AppError("service.unavailable", f"Сервис «{self.name}» недоступен", 503)
        if r.status_code >= 300:
            raise AppError("service.error", f"{self.name}: {path} — {r.status_code}", 502 if r.status_code != 404 else 404)
        return r

    def post(self, path, **kw):
        try:
            r = self.http.post(path, headers=self._h(), **kw)
        except httpx.HTTPError:
            raise AppError("service.unavailable", f"Сервис «{self.name}» недоступен", 503)
        return r


SVC = {"algo_admin": Svc("algo_admin"), "data_admin": Svc("data_admin"), "data_model": Svc("data_model")}


def audit(user, action, otype, oid, details=None):
    app.state.audit.log(user, action, otype, oid, details)


def _zip(files):
    return build.zip_bytes(files)


def _unzip(data: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            out = {}
            for n in z.namelist():
                if n.endswith("/") or "__pycache__" in n or n.startswith("__MACOSX"):
                    continue
                if ".." in Path(n).parts or Path(n).is_absolute():
                    raise AppError("draft.zip", f"Недопустимое имя файла в архиве: {n}", 422)
                out[n] = z.read(n)
    except zipfile.BadZipFile:
        raise AppError("draft.zip", "Файл не является zip-архивом", 422)
    # архив с одной папкой верхнего уровня → снимаем её
    tops = {n.split("/")[0] for n in out}
    if len(tops) == 1 and not any("/" not in n for n in out) and f"{next(iter(tops))}/manifest.json" in out:
        pre = next(iter(tops)) + "/"
        out = {n[len(pre):]: v for n, v in out.items()}
    return out


# ================================================================ проекты
def _seed():
    for manifest, files in build.builtin():
        code = manifest["code"]
        if not projects.exists(code):
            projects.create({"code": code, "title_ru": manifest["title_ru"], "title_kk": manifest.get("title_kk", ""),
                             "description": manifest.get("description", ""), "builtin": True}, actor="system", obj_id=code)


_seed()


class ProjectIn(BaseModel):
    code: str
    title_ru: str
    title_kk: str = ""
    description: str = ""


def _published(code: str) -> list[dict]:
    try:
        return SVC["algo_admin"].get(f"/catalog/{code}").json().get("versions", [])
    except AppError:
        return []


@app.get("/algorithms", tags=["алгоритмы"])
def list_projects(user: User = Depends(require("algo.develop"))):
    out = []
    for p in projects.list():
        if p.get("deleted"):
            continue
        ds = [d for d in drafts.list() if d["algorithm"] == p["code"] and not d.get("deleted")]
        out.append({**p, "drafts": len([d for d in ds if d.get("status") != "published"])})
    order = {c: i for i, c in enumerate(build.ORDER)}
    return sorted(out, key=lambda p: (order.get(p["code"], 99), p["code"]))


TEMPLATE_ALGO = '''"""{title}

Контракт: run(ctx) — ctx.tables (наборы данных водоёма), ctx.params (параметры: неизменяемые, водоёма, запуска),
ctx.load_state("<шаг>") (результаты предыдущего шага цепочки), ctx.add_table / ctx.add_frame / ctx.add_file /
ctx.set_payload / ctx.metric / ctx.note — результаты; ctx.log, ctx.progress — журнал и ход выполнения.
"""


def run(ctx):
    rows = ctx.tables["npc_pdu"]["rows"]
    k = ctx.params["k"]
    ctx.log(f"строк: {{len(rows)}}, k = {{k}}")
    out = [{{"year": r["year"], "value": sum(v or 0 for c, v in r.items() if c != "year") * k}} for r in rows]
    ctx.add_table("result", "Результат", [{{"code": "year", "title": "Год", "type": "integer"}},
                                         {{"code": "value", "title": "Значение", "type": "number"}}], out)
    return {{"rows": len(out)}}
'''


@app.post("/algorithms", tags=["алгоритмы"], status_code=201)
def create_project(body: ProjectIn, user: User = Depends(require("algo.develop"))):
    if not re.match(r"^[a-z][a-z0-9_]{2,40}$", body.code):
        raise AppError("algo.code", "Код алгоритма: латинские строчные буквы, цифры и _ (3–40 символов)", 422)
    if projects.exists(body.code):
        raise AppError("algo.exists", "Алгоритм с таким кодом уже есть", 409)
    p = projects.create({**body.model_dump(), "builtin": False}, actor=user.id, obj_id=body.code)
    manifest = {"code": body.code, "version": "0.1.0", "title_ru": body.title_ru, "title_kk": body.title_kk,
                "description": body.description, "author": user.name, "entrypoint": "algorithm:run", "language": "python",
                "runtime": {"python": ">=3.11", "timeout_minutes": 30},
                "requires": {"datasets": ["npc_pdu"], "steps": []},
                "parameters": [{"code": "k", "title_ru": "Коэффициент", "type": "number", "default": 1.0,
                                "category": "run", "min": 0}],
                "outputs": [{"code": "result", "title_ru": "Результат", "format": "table"}]}
    files = {"manifest.json": json.dumps(manifest, ensure_ascii=False, indent=1).encode(),
             "algorithm.py": TEMPLATE_ALGO.format(title=body.title_ru).encode()}
    d = _new_draft(body.code, files, None, user, "новый алгоритм из шаблона")
    audit(user, "algo.create", "algorithm", body.code)
    return {**p, "draft_id": d["id"]}


@app.get("/algorithms/{code}", tags=["алгоритмы"])
def get_project(code: str, user: User = Depends(require("algo.develop"))):
    p = projects.get(code)
    if not p:
        raise not_found("Алгоритм")
    ds = sorted((d for d in drafts.list() if d["algorithm"] == code and not d.get("deleted")),
                key=lambda d: d["created_at"], reverse=True)
    return {**p, "drafts": ds, "published": _published(code)}


# ================================================================ черновики
def _new_draft(code, files, base_version, user, comment):
    d = drafts.create({"algorithm": code, "base_version": base_version, "status": "draft", "last_test": None,
                       "validation": None, "author_name": user.name}, actor=user.id)
    drafts.add_version(d["id"], {"package.zip": _zip(files)}, {"comment": comment}, user.id)
    return drafts.get(d["id"])


def _draft(did):
    d = drafts.get(did)
    if not d or d.get("deleted"):
        raise not_found("Черновик")
    return d


def _files(did, n=None):
    d = _draft(did)
    return _unzip(drafts.read_version_file(did, n or d["current_version"], "package.zip"))


def _save_files(did, files, user, comment):
    d = _draft(did)
    if d["status"] == "published":
        raise AppError("draft.published", "Черновик уже опубликован — создайте новый черновик от этой версии", 400)
    v = drafts.add_version(did, {"package.zip": _zip(files)}, {"comment": comment}, user.id)
    drafts.update(did, {"status": "draft", "validation": None}, actor=user.id)
    return v


class DraftIn(BaseModel):
    from_version: str | None = None


@app.post("/algorithms/{code}/drafts", tags=["черновики"], status_code=201)
def create_draft(code: str, body: DraftIn, user: User = Depends(require("algo.develop"))):
    if not projects.exists(code):
        raise not_found("Алгоритм")
    pub = _published(code)
    ver = body.from_version or (pub[0]["version"] if pub else None)
    if not ver:
        raise AppError("draft.base", "Нет опубликованных версий — черновик создаётся при создании алгоритма", 400)
    data = SVC["algo_admin"].get(f"/catalog/{code}/versions/{ver}/package.zip").content
    files = _unzip(data)
    m = json.loads(files["manifest.json"])
    parts = [int(x) for x in m["version"].split(".")]
    parts[-1] += 1
    m["version"] = ".".join(map(str, parts))
    files["manifest.json"] = json.dumps(m, ensure_ascii=False, indent=1).encode()
    d = _new_draft(code, files, ver, user, f"от версии {ver}")
    audit(user, "algo.draft_create", "draft", d["id"], {"algorithm": code, "from": ver})
    return d


@app.get("/drafts/{did}", tags=["черновики"])
def get_draft(did: str, user: User = Depends(require("algo.develop"))):
    d = _draft(did)
    files = _files(did)
    manifest = None
    try:
        manifest = json.loads(files.get("manifest.json", b"{}"))
    except json.JSONDecodeError:
        pass
    tree = [{"path": k, "size": len(v), "text": k.endswith(TEXT_EXT)} for k, v in sorted(files.items())]
    return {**d, "manifest": manifest, "files": tree, "history": list(reversed(drafts.list_versions(did))),
            "tests": _tests(did)}


@app.get("/drafts/{did}/file", tags=["черновики"])
def get_file(did: str, path: str, user: User = Depends(require("algo.develop"))):
    files = _files(did)
    if path not in files:
        raise not_found("Файл")
    return {"path": path, "text": files[path].decode("utf-8", errors="replace")}


class FileIn(BaseModel):
    path: str
    text: str
    comment: str = ""


@app.put("/drafts/{did}/file", tags=["черновики"])
def put_file(did: str, body: FileIn, user: User = Depends(require("algo.develop"))):
    p = body.path.strip().lstrip("/")
    if not p or ".." in Path(p).parts or not p.endswith(TEXT_EXT):
        raise AppError("draft.path", "Имя файла: относительный путь, расширения .py .json .md .txt .csv .yaml", 422)
    files = _files(did)
    files[p] = body.text.encode("utf-8")
    v = _save_files(did, files, user, body.comment or f"изменён {p}")
    audit(user, "algo.file_save", "draft", did, {"path": p, "version": v["n"]})
    return get_draft(did, user)


@app.delete("/drafts/{did}/file", tags=["черновики"])
def delete_file(did: str, path: str, user: User = Depends(require("algo.develop"))):
    files = _files(did)
    if path not in files:
        raise not_found("Файл")
    if path == "manifest.json":
        raise AppError("draft.manifest", "manifest.json удалить нельзя", 400)
    files.pop(path)
    _save_files(did, files, user, f"удалён {path}")
    return get_draft(did, user)


@app.post("/drafts/{did}/upload", tags=["черновики"])
async def upload(did: str, file: UploadFile = File(...), user: User = Depends(require("algo.develop"))):
    files = _unzip(await file.read())
    if "manifest.json" not in files:
        raise AppError("draft.manifest", "В архиве нет manifest.json", 422)
    _save_files(did, files, user, f"загружен архив {file.filename}")
    audit(user, "algo.upload", "draft", did, {"file": file.filename})
    return get_draft(did, user)


@app.get("/drafts/{did}/download.zip", tags=["черновики"])
def download(did: str, user: User = Depends(require("algo.develop"))):
    d = _draft(did)
    return Response(_zip(_files(did)), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{d["algorithm"]}_draft.zip"'})


@app.delete("/drafts/{did}", tags=["черновики"])
def delete_draft(did: str, user: User = Depends(require("algo.develop"))):
    _draft(did)
    drafts.delete(did)
    audit(user, "algo.draft_delete", "draft", did)
    return {"ok": True}


# ================================================================ проверка
def validate_files(code: str, files: dict[str, bytes], published: list[dict]) -> dict:
    errors, warnings = [], []
    try:
        m = json.loads(files.get("manifest.json", b""))
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [f"manifest.json: ошибка JSON — {e}"], "warnings": []}
    for k in ("code", "version", "title_ru", "entrypoint", "parameters", "requires"):
        if k not in m:
            errors.append(f"manifest.json: нет поля «{k}»")
    if m.get("code") != code:
        errors.append(f"manifest.json: code должен быть «{code}»")
    if not re.match(r"^\d+\.\d+\.\d+$", str(m.get("version", ""))):
        errors.append("manifest.json: version в виде 1.2.3")
    elif any(p["version"] == m["version"] for p in published):
        errors.append(f"Версия {m['version']} уже опубликована — увеличьте номер версии")
    elif published and tuple(map(int, m["version"].split("."))) <= max(tuple(map(int, p["version"].split("."))) for p in published):
        warnings.append("Номер версии не больше уже опубликованных")
    seen = set()
    for p in m.get("parameters", []):
        c = p.get("code")
        if not c or not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", c):
            errors.append(f"Параметр «{c}»: код — латиница, цифры, _")
        if c in seen:
            errors.append(f"Параметр «{c}» повторяется")
        seen.add(c)
        if p.get("category") not in CATEGORIES:
            errors.append(f"Параметр «{c}»: категория fixed (неизменяемый), waterbody (водоём) или run (запуск)")
        if p.get("type") not in PARAM_TYPES:
            errors.append(f"Параметр «{c}»: тип из {', '.join(PARAM_TYPES)}")
        if p.get("type") == "enum" and p.get("default") is not None and p["default"] not in [e.get("value") for e in p.get("enum", [])]:
            errors.append(f"Параметр «{c}»: значение по умолчанию не из списка")
        if p.get("category") == "fixed" and p.get("default") is None:
            errors.append(f"Параметр «{c}»: у неизменяемого параметра должно быть значение")
        if not p.get("title_ru"):
            warnings.append(f"Параметр «{c}»: нет названия")
    req = m.get("requires", {})
    for s in req.get("steps", []):
        if s not in build.ORDER and s != code:
            warnings.append(f"Шаг-предшественник «{s}» не входит в эталонную цепочку")
    ep = str(m.get("entrypoint", "algorithm:run"))
    mod = ep.split(":")[0].replace(".", "/") + ".py"
    if mod not in files:
        errors.append(f"Нет файла точки входа {mod}")
    for path, content in files.items():
        if path.endswith(".py"):
            try:
                compile(content.decode("utf-8"), path, "exec")
            except SyntaxError as e:
                errors.append(f"{path}, строка {e.lineno}: синтаксическая ошибка — {e.msg}")
            except UnicodeDecodeError:
                errors.append(f"{path}: файл не в кодировке UTF-8")
    if mod in files and ep.count(":") == 1:
        fn = ep.split(":")[1]
        if not re.search(rf"^def {re.escape(fn)}\(", files[mod].decode("utf-8", "replace"), re.M):
            errors.append(f"В {mod} нет функции {fn}(ctx)")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "manifest": m}


@app.post("/drafts/{did}/validate", tags=["проверка"])
def validate(did: str, user: User = Depends(require("algo.develop"))):
    d = _draft(did)
    res = validate_files(d["algorithm"], _files(did), _published(d["algorithm"]))
    res.pop("manifest", None)
    res["version"] = d["current_version"]
    drafts.update(did, {"validation": {**res, "at": now_iso()}}, actor=user.id)
    return res


# ================================================================ тестовый прогон
class TestIn(BaseModel):
    water_body: str = "zhaysan"
    params: dict = {}
    compare_with: str | None = None     # опубликованная версия этого алгоритма для сверки


def _tests(did):
    out = []
    for p in sorted(TESTS.glob(f"{did}_*/test.json"), reverse=True):
        t = read_json(p)
        if t:
            out.append({k: t.get(k) for k in ("id", "status", "message", "created_at", "finished_at", "draft_version",
                                               "water_body", "compare_with", "comparison_ok")})
    return out


def _defaults(m):
    return {p["code"]: p.get("default") for p in m.get("parameters", []) if p.get("default") is not None}


def _profile(code, wb):
    try:
        r = SVC["algo_admin"].get(f"/profiles/{code}/{wb}").json()
        return ((r.get("profile") or {}).get("values")) or {}
    except AppError:
        return {}


def _compare(new: dict, ref: dict) -> dict:
    """Сравнение таблиц результатов: наибольшее относительное отличие числовых столбцов."""
    out, ok = [], True
    for code, t in (ref.get("tables") or {}).items():
        nt = (new.get("tables") or {}).get(code)
        if not nt:
            out.append({"table": code, "status": "нет в новой версии"})
            ok = False
            continue
        if len(nt["rows"]) != len(t["rows"]):
            out.append({"table": code, "status": f"разное число строк: {len(t['rows'])} → {len(nt['rows'])}"})
            ok = False
            continue
        worst, col = 0.0, None
        for c in t["columns"]:
            if c.get("type") not in ("number", "integer"):
                continue
            for a, b in zip(t["rows"], nt["rows"]):
                x, y = a.get(c["code"]), b.get(c["code"])
                if x is None and y is None:
                    continue
                if (x is None) != (y is None):
                    worst, col = float("inf"), c["code"]
                    break
                rel = abs(x - y) / max(abs(x), 1e-12) if x else abs(y)
                if rel > worst:
                    worst, col = rel, c["code"]
        same = worst <= 1e-9
        out.append({"table": code, "max_rel_diff": worst if worst != float("inf") else None, "column": col,
                    "status": "совпадает" if same else "отличается"})
    return {"ok": ok, "tables": out}


def _run_test(tid: str, did: str, d: dict, files: dict, body: TestIn, user_name: str):
    tdir = TESTS / tid
    meta_p = tdir / "test.json"
    meta = read_json(meta_p)
    try:
        with _test_lock:
            meta["status"] = "running"
            atomic_write_json(meta_p, meta)
            m = json.loads(files["manifest.json"])
            bundle = SVC["data_admin"].get(f"/bundle/{body.water_body}").json()
            need = set(m.get("requires", {}).get("datasets", []))
            chain = [s for s in build.ORDER if s in _upstream(m)]
            pkgs = {}
            for s in chain:
                vs = _published(s)
                ver = next((v["version"] for v in vs if v.get("enabled", True)), None)
                if not ver:
                    raise RuntimeError(f"Нет опубликованной версии шага «{s}»")
                pkgs[s] = (_unzip(SVC["algo_admin"].get(f"/catalog/{s}/versions/{ver}/package.zip").content), ver)
                need |= set(json.loads(pkgs[s][0]["manifest.json"]).get("requires", {}).get("datasets", []))
            tables = {}
            for t in sorted(need):
                if t in bundle:
                    tables[t] = SVC["data_admin"].get(f"/datasets/{bundle[t]['dataset_id']}/data",
                                                      version=bundle[t]["version"]).json()["table"]
            (tdir / "tables.json").write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8")
            sp = {r["values"]["code"]: r["values"]["name_ru"] for r in SVC["data_model"].get("/entities/species/records").json()}
            gk = {r["values"]["code"]: r["values"]["kind"] for r in SVC["data_model"].get("/entities/gears/records").json()}
            done = {}

            def step(code, pfiles, params, name):
                pm = json.loads(pfiles["manifest.json"])
                prm = {**_defaults(pm), **{p["code"]: v for p in pm["parameters"] if p.get("category") == "waterbody"
                                          for k, v in _profile(code, body.water_body).items() if k == p["code"]},
                       **params}
                sd = tdir / name
                ctx = {"run_id": tid, "step": code, "water_body": body.water_body, "params": prm, "species_names": sp,
                       "gear_kinds": gk, "inputs": {k: str(v / "out") for k, v in done.items()},
                       "tables_path": str(tdir / "tables.json")}
                executor.prepare_step(sd, pfiles, ctx)
                st = executor.run_step(sd, timeout_s=float(pm.get("runtime", {}).get("timeout_minutes", 30)) * 60)
                if st["status"] != "done":
                    raise RuntimeError(f"Шаг «{pm['title_ru']}»: {st.get('message')}")
                return sd

            upstream = dict(body.params.get("_upstream") or {})
            own = {k: v for k, v in body.params.items() if k != "_upstream"}
            for s in chain:
                # байесовская модель как предшественник — короткая выборка (проверяется работоспособность шага)
                quick = {"draws": 100, "tune": 100, "chains": 2} if s == "bayes_cohort" else {}
                done[s] = step(s, pkgs[s][0], {**quick, **(upstream.get(s) or {})}, f"up_{s}")
            sd = step(d["algorithm"], files, own, "draft")
            result = executor.read_result(sd)
            meta.update(status="passed", message="Тестовый прогон выполнен", summary={
                "tables": {k: {"title": v["title"], "rows": len(v["rows"])} for k, v in (result.get("tables") or {}).items()},
                "files": result.get("files"), "metrics": result.get("metrics"), "notes": result.get("notes"),
                "seconds": result.get("seconds")})
            if body.compare_with:
                ref_files = _unzip(SVC["algo_admin"].get(
                    f"/catalog/{d['algorithm']}/versions/{body.compare_with}/package.zip").content)
                rd = step(d["algorithm"], ref_files, own, "reference")
                cmp_ = _compare(result, executor.read_result(rd))
                meta.update(comparison=cmp_, comparison_ok=cmp_["ok"])
    except Exception as e:  # noqa: BLE001
        meta.update(status="failed", message=str(e), traceback=traceback.format_exc())
    meta["finished_at"] = now_iso()
    atomic_write_json(meta_p, meta)
    drafts.update(did, {"last_test": {k: meta.get(k) for k in ("id", "status", "message", "draft_version", "finished_at",
                                                                 "comparison_ok")}}, actor="system")


def _upstream(m: dict) -> set[str]:
    """Все предшественники по эталонной цепочке (transitive)."""
    req = set(m.get("requires", {}).get("steps", []))
    out = set()
    stack = list(req)
    deps = {"stock_by_catch": ["seine_catchability"], "pdu_by_age": ["stock_by_catch"],
            "bayes_cohort": ["stock_by_catch", "pdu_by_age"], "forecast_pdu": ["bayes_cohort"]}
    while stack:
        s = stack.pop()
        if s in out or s == m.get("code"):
            continue
        out.add(s)
        stack += deps.get(s, [])
    return out


@app.post("/drafts/{did}/test", tags=["проверка"], status_code=202)
def start_test(did: str, body: TestIn, user: User = Depends(require("algo.develop"))):
    d = _draft(did)
    files = _files(did)
    v = validate_files(d["algorithm"], files, _published(d["algorithm"]))
    if not v["ok"]:
        raise AppError("draft.invalid", "Черновик не прошёл проверку — исправьте ошибки", 422, v["errors"])
    from fishcommon.storage import new_id
    tid = f"{did}_{new_id()}"
    tdir = TESTS / tid
    tdir.mkdir(parents=True)
    meta = {"id": tid, "draft_id": did, "draft_version": d["current_version"], "status": "queued", "created_at": now_iso(),
            "water_body": body.water_body, "params": body.params, "compare_with": body.compare_with, "author": user.id}
    atomic_write_json(tdir / "test.json", meta)
    threading.Thread(target=_run_test, args=(tid, did, d, files, body, user.name), daemon=True).start()
    audit(user, "algo.test", "draft", did, {"water_body": body.water_body, "compare_with": body.compare_with})
    return meta


@app.get("/tests/{tid}", tags=["проверка"])
def get_test(tid: str, user: User = Depends(require("algo.develop"))):
    if "/" in tid or ".." in tid:
        raise not_found("Тест")
    t = read_json(TESTS / tid / "test.json")
    if not t:
        raise not_found("Тест")
    log = ""
    for name in ("draft", "reference"):
        f = TESTS / tid / name / "log.txt"
        if f.exists():
            log += f"── {name} ──\n" + f.read_text(encoding="utf-8")[-50_000:] + "\n"
    return {**t, "log": log}


@app.get("/tests/{tid}/result", tags=["проверка"])
def get_test_result(tid: str, user: User = Depends(require("algo.develop"))):
    r = executor.read_result(TESTS / tid / "draft")
    if r is None:
        raise not_found("Результат теста")
    return r


# ================================================================ публикация
class PublishIn(BaseModel):
    comment: str = ""


@app.post("/drafts/{did}/publish", tags=["публикация"])
def publish(did: str, body: PublishIn, user: User = Depends(require("algo.develop"))):
    d = _draft(did)
    files = _files(did)
    v = validate_files(d["algorithm"], files, _published(d["algorithm"]))
    if not v["ok"]:
        raise AppError("draft.invalid", "Черновик не прошёл проверку", 422, v["errors"])
    lt = d.get("last_test") or {}
    if lt.get("status") != "passed" or lt.get("draft_version") != d["current_version"]:
        raise AppError("draft.untested", "Перед публикацией выполните тестовый прогон текущей версии черновика", 400)
    t = read_json(TESTS / lt["id"] / "test.json") or {}
    report = {"status": "passed", "test_id": lt["id"], "water_body": t.get("water_body"), "comment": body.comment,
              "comparison": t.get("comparison"), "validated_at": now_iso(), "warnings": v["warnings"]}
    r = SVC["algo_admin"].post("/internal/catalog/publish", files={"package": ("p.zip", _zip(files))},
                               data={"report": json.dumps(report, ensure_ascii=False), "author": user.id})
    if r.status_code >= 300:
        try:
            msg = r.json()["error"]["message"]
        except Exception:  # noqa: BLE001
            msg = r.text
        raise AppError("publish.failed", f"Каталог отклонил публикацию: {msg}", 409 if r.status_code == 409 else 502)
    drafts.update(did, {"status": "published", "published_version": v["manifest"]["version"], "published_at": now_iso()},
                  actor=user.id)
    audit(user, "algo.publish", "algorithm", d["algorithm"], {"version": v["manifest"]["version"], "draft": did})
    return get_draft(did, user)
