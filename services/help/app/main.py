"""
Сервис 7. Справка (руководство пользователя в приложении).

Статьи на русском и казахском (Markdown) по разделам: общее, ихтиологу, математику, дашборды, администратору,
установка, глоссарий. Начальное содержание поставляется с приложением (app/content) и обновляется вместе с ним;
администратор и математик могут править статьи в браузере — каждая правка сохраняется новой версией.
Поиск, контекстная справка для экранов («?»), выгрузка всего руководства или раздела в Word и PDF.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx

from fastapi import Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from fishcommon.app import create_app
from fishcommon.auth import User, require
from fishcommon.errors import AppError, not_found
from fishcommon.storage import Collection, atomic_write_bytes, new_id

from . import export

app = create_app("help", "Справка",
                 "Руководство пользователя: статьи RU/KK, поиск, контекстная справка, версии, выгрузка Word/PDF.")
ST = app.state.settings
ROOT = ST.service_dir()
CONTENT = Path(__file__).parent / "content"
LANGS = ("ru", "kk")
articles = Collection(ROOT, "articles")
IMAGES = ROOT / "images"
IMAGES.mkdir(parents=True, exist_ok=True)
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def audit(user, action, oid, details=None):
    app.state.audit.log(user, action, "help_article", oid, details)


# ------------------------------------------------------------------ поставка
def bundle_sections() -> list[dict]:
    return json.loads((CONTENT / "sections.json").read_text(encoding="utf-8"))


def bundle_articles() -> list[dict]:
    return json.loads((CONTENT / "articles.json").read_text(encoding="utf-8"))


def bundle_text(aid: str) -> dict[str, str]:
    out = {}
    for lang in LANGS:
        p = CONTENT / lang / f"{aid}.md"
        out[lang] = p.read_text(encoding="utf-8") if p.exists() else ""
    return out


def _hash(texts: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _files(texts: dict[str, str]) -> dict[str, bytes]:
    return {f"{lang}.md": texts.get(lang, "").encode("utf-8") for lang in LANGS}


def _seed() -> None:
    """Статьи поставки: новые создаются, неизменённые пользователями — обновляются до текста поставки.
    Если статью правили в приложении, её текст сохраняется, а у статьи отмечается «есть обновление поставки»."""
    seen = set()
    for a in bundle_articles():
        aid = a["id"]
        seen.add(aid)
        texts = bundle_text(aid)
        h = _hash(texts)
        struct = {"section": a["section"], "order": a["order"], "routes": a.get("routes", []), "bundled": True,
                  "presenter": bool(a.get("presenter"))}
        cur = articles.get(aid)
        if cur is None:
            articles.create({**struct, "bundled_hash": h, "edited": False}, actor="system", obj_id=aid)
            articles.add_version(aid, _files(texts), {"comment": "поставка"}, "system")
            continue
        changes = dict(struct)
        if cur.get("deleted"):
            changes["deleted"] = False
        if cur.get("bundled_hash") != h:
            if not cur.get("edited"):
                articles.add_version(aid, _files(texts), {"comment": "обновление поставки"}, "system")
                changes.update(bundled_hash=h, bundle_update=False)
            else:
                changes.update(bundle_update=True)
        articles.update(aid, changes, actor="system")
    for cur in articles.list():
        if cur.get("bundled") and cur["id"] not in seen and not cur.get("deleted") and not cur.get("edited"):
            articles.update(cur["id"], {"deleted": True}, actor="system")


_seed()


# ------------------------------------------------------------------ чтение
def _texts(aid: str, n: int | None = None) -> dict[str, str]:
    a = articles.get(aid)
    if a is None or (a.get("deleted") and n is None):
        raise not_found("Статья")
    n = n or a.get("current_version")
    try:
        return {lang: articles.read_version_file(aid, n, f"{lang}.md").decode("utf-8") for lang in LANGS}
    except FileNotFoundError:
        raise not_found("Версия статьи")


def title_of(md: str, fallback: str = "") -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _text_in(texts: dict[str, str], lang: str) -> tuple[str, bool]:
    """Текст на языке; если перевода нет — русский (второй элемент — признак замены)."""
    t = texts.get(lang) or ""
    if t.strip():
        return t, False
    return texts.get("ru", ""), lang != "ru"


def _sections_title(code: str, lang: str) -> str:
    for s in bundle_sections():
        if s["code"] == code:
            return s.get(f"title_{lang}") or s["title_ru"]
    return code


def _visible(a: dict, user: User | None) -> bool:
    """«Презентация» видит только обзорные статьи (отметка presenter в поставке), без формул и установки (№ 62)."""
    return user is None or user.can("help.full") or bool(a.get("presenter"))


def _live(user: User | None = None) -> list[dict]:
    return sorted([a for a in articles.list() if not a.get("deleted") and _visible(a, user)],
                  key=lambda a: (a["section"], a["order"], a["id"]))


HELP_LINK = re.compile(r"\[([^\]]*)\]\(help:([\w-]+)(#[^)]*)?\)")


def _unlink_hidden(md: str, user: User | None) -> str:
    """Ссылки на статьи, закрытые для роли, остаются текстом без ссылки."""
    if user is None or user.can("help.full"):
        return md
    vis = {a["id"] for a in _live(user)}
    return HELP_LINK.sub(lambda m: m.group(0) if m.group(2) in vis else m.group(1), md)


def _article(aid: str, user: User) -> dict:
    a = articles.get(aid)
    if a is None or not _visible(a, user):
        raise not_found("Статья")
    return a


def toc(lang: str, user: User | None = None) -> list[dict]:
    out = []
    by_sec: dict[str, list] = {}
    for a in _live(user):
        texts = _texts(a["id"])
        md, fb = _text_in(texts, lang)
        by_sec.setdefault(a["section"], []).append(
            {"id": a["id"], "title": title_of(md, a["id"]), "order": a["order"], "fallback": fb,
             "edited": a.get("edited", False), "bundle_update": a.get("bundle_update", False)})
    for s in sorted(bundle_sections(), key=lambda s: s["order"]):
        items = sorted(by_sec.pop(s["code"], []), key=lambda x: (x["order"], x["id"]))
        if not items and user is not None and not user.can("help.full"):
            continue
        out.append({"code": s["code"], "title": s.get(f"title_{lang}") or s["title_ru"], "articles": items})
    for code, items in by_sec.items():  # разделы, которых нет в поставке
        out.append({"code": code, "title": code, "articles": sorted(items, key=lambda x: (x["order"], x["id"]))})
    return out


def _lang(lang: str) -> str:
    if lang not in LANGS:
        raise AppError("help.lang", "Язык: ru или kk", 400)
    return lang


@app.get("/sections", tags=["справка"])
def get_sections(lang: str = "ru", user: User = Depends(require("help.view"))):
    """Оглавление: разделы и статьи."""
    return toc(_lang(lang), user)


@app.get("/articles/{aid}", tags=["справка"])
def get_article(aid: str, lang: str = "ru", version: int | None = None, expand_: bool = Query(False, alias="expand"),
                wb: str | None = None, species: str | None = None, year: int | None = None,
                wb_name: str | None = None, user: User = Depends(require("help.view"))):
    """expand=1 — подставить таблицы параметров и пример на числах (для чтения); без него — исходный текст."""
    a = _article(aid, user)
    texts = _texts(aid, version)
    md, fb = _text_in(texts, _lang(lang))
    has_example = "{{example}}" in md
    if expand_:
        md = expand(md, lang, {"wb": wb, "species": species, "year": year, "wb_name": wb_name})
    md = _unlink_hidden(md, user)
    return {"id": aid, "section": a["section"], "section_title": _sections_title(a["section"], lang),
            "order": a["order"], "routes": a.get("routes", []), "title": title_of(md, aid), "markdown": md,
            "fallback": fb, "version": version or a.get("current_version"), "current_version": a.get("current_version"),
            "updated_at": a.get("updated_at"), "updated_by": a.get("updated_by"), "edited": a.get("edited", False),
            "bundled": a.get("bundled", False), "bundle_update": a.get("bundle_update", False),
            "can_edit": user.can("help.edit"), "texts": texts if user.can("help.edit") else None,
            "has_example": has_example}


@app.get("/articles/{aid}/versions", tags=["справка"])
def get_versions(aid: str, user: User = Depends(require("help.view"))):
    _article(aid, user)
    return list(reversed(articles.list_versions(aid)))


def _words(s: str) -> list[str]:
    return re.findall(r"[\wёәғқңөұүһі]+", s.lower())


def _plain(md: str) -> str:
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    return re.sub(r"[#*_`>|]", " ", md)


@app.get("/search", tags=["справка"])
def search(q: str, lang: str = "ru", user: User = Depends(require("help.view"))):
    terms = [t for t in _words(q) if len(t) >= 2]
    if not terms:
        return []
    out = []
    for a in _live(user):
        md, _ = _text_in(_texts(a["id"]), _lang(lang))
        title = title_of(md, a["id"])
        plain = _plain(md)
        low_t, low_b = title.lower(), plain.lower()
        score = 0
        for t in terms:
            if t not in low_b and t not in low_t:
                score = 0
                break
            score += 5 * low_t.count(t) + low_b.count(t)
        if score:
            pos = low_b.find(terms[0])
            start = max(0, pos - 80)
            snippet = re.sub(r"\s+", " ", plain[start:pos + 160]).strip()
            out.append({"id": a["id"], "title": title, "section": _sections_title(a["section"], lang),
                        "score": score, "snippet": ("…" if start else "") + snippet + "…"})
    return sorted(out, key=lambda x: -x["score"])[:30]


def _route_match(pattern: str, route: str) -> int:
    """Длина совпадения шаблона маршрута ('/datasets/*' — любой подпуть); 0 — не совпадает."""
    if pattern.endswith("/*"):
        base = pattern[:-2]
        return len(base) + 1 if route == base or route.startswith(base + "/") else 0
    return len(pattern) + 2 if route.rstrip("/") == pattern.rstrip("/") else 0


@app.get("/context", tags=["справка"])
def context(route: str, lang: str = "ru", user: User = Depends(require("help.view"))):
    """Статья для экрана приложения (значок «?»)."""
    best, best_len = None, 0
    for a in _live(user):
        for p in a.get("routes", []):
            n = _route_match(p, route)
            if n > best_len:
                best, best_len = a, n
    if best is None:
        best = articles.get("intro")
    if best is None:
        raise not_found("Статья")
    md, _ = _text_in(_texts(best["id"]), _lang(lang))
    return {"id": best["id"], "title": title_of(md, best["id"])}


# ------------------------------------------------------------------ вставки из работающего приложения
# {{params:<код алгоритма>}} — таблица параметров последней включённой версии алгоритма (каталог);
# {{example}} — пример распределения ПДУ НПЦ по возрастам из основного расчёта h выбранного водоёма (решение № 66).
DIRECTIVE = re.compile(r"^\{\{(params|example)(?::([\w-]+))?\}\}[ \t]*$", re.M)
L = {
    "ru": {"param": "Параметр", "default": "По умолчанию", "cat": "Категория", "desc": "Описание",
           "fixed": "неизменяемый", "waterbody": "водоём (профиль)", "run": "запуск", "version": "Версия алгоритма",
           "param": "набор «Параметры алгоритма»", "calc": "в расчёте",
           "no_algo": "Алгоритм не найден в каталоге.", "none": "—", "no_run": "Для водоёма ещё нет основного "
           "расчёта «h. ПДУ в экземплярах особей» — пример появится после него.", "unavail": "Сервис расчётов недоступен — "
           "пример не построен.", "wb": "Водоём", "run_main": "основной расчёт", "run_last": "расчёт",
           "sp": "Вид", "year": "Год", "age": "Возраст", "stock": "Запас, шт", "w": "Ср. вес, г",
           "bio": "Биомасса, т", "load": "Нагрузка j/m1", "pcs": "ПДУ, шт", "t": "ПДУ, т", "expl": "Изъятие, %",
           "immature": "не вылавливается", "P": "ПДУ НПЦ", "dist": "распределено", "left": "не распределено",
           "fish_bio": "промысловая биомасса", "iters": "итераций", "stop": "остановка", "cap": "ограничение 75 %"},
    "kk": {"param": "Параметр", "default": "Әдепкі мәні", "cat": "Санаты", "desc": "Сипаттамасы",
           "fixed": "өзгермейтін", "waterbody": "су айдыны (профиль)", "run": "іске қосу", "version": "Алгоритм нұсқасы",
           "param": "«Алгоритм параметрлері» жиыны", "calc": "есептеуде",
           "no_algo": "Алгоритм каталогта табылмады.", "none": "—", "no_run": "Су айдыны үшін «h. Дарақ данасымен ШРА» "
           "негізгі есептеуі әлі жоқ — мысал одан кейін пайда болады.", "unavail": "Есептеулер қызметі қолжетімсіз — "
           "мысал құрылмады.", "wb": "Су айдыны", "run_main": "негізгі есептеу", "run_last": "есептеу",
           "sp": "Түр", "year": "Жыл", "age": "Жасы", "stock": "Қор, дана", "w": "Орт. салмақ, г",
           "bio": "Биомасса, т", "load": "Жүктеме j/m1", "pcs": "ШРА, дана", "t": "ШРА, т", "expl": "Алу үлесі, %",
           "immature": "ауланбайды", "P": "ҒӨО ШРА", "dist": "бөлінді", "left": "бөлінбеді",
           "fish_bio": "кәсіптік биомасса", "iters": "итерация", "stop": "тоқтау себебі", "cap": "75 % шектеу"},
}


def _svc(name: str, path: str, **params):
    try:
        r = httpx.get(ST.urls[name] + path, params=params or None, headers={"X-Service-Token": ST.service_token},
                      timeout=30)
    except httpx.HTTPError:
        return "unavailable"
    return r.json() if r.status_code == 200 else None


def _num(v, digits=0) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.{digits}f}".replace(",", " ")
    return s.replace(".", ",") if digits else s


def _params_table(code: str, lang: str) -> str:
    t = L[lang]
    cat = _svc("algo_admin", "/catalog")
    if cat == "unavailable":
        return f"> {t['unavail']}"
    item = next((a for a in (cat or []) if a["code"] == code), None)
    if not item or not item.get("manifest"):
        return f"> {t['no_algo']}"
    rows = [f"| {t['param']} | {t['default']} | {t['cat']} | {t['desc']} |", "|---|---|---|---|"]
    for p in item["manifest"].get("parameters", []):
        d = p.get("default")
        dv = t["none"] if d in (None, "", {}, []) else (str(d).replace(".", ",") if isinstance(d, float) else str(d))
        title = (p.get("title_kk") if lang == "kk" else None) or p.get("title_ru") or ""
        title = re.sub(r"\s*\(\d{1,2}\)(\s*[–-]\s*\(\d{1,2}\))?", "", title)   # номера формул источника
        rows.append(f"| `{p['code']}` | {dv} | {t.get(p.get('category'), p.get('category'))} | "
                    f"{title.replace('|', '/')} |")
    return f"*{t['version']}: {item.get('latest')}*\n\n" + "\n".join(rows)


def example_data(wb: str, species: str | None, year: int | None) -> dict:
    """Данные примера: результат основного расчёта h (ПДУ в экземплярах) водоёма."""
    m = _svc("algo_admin", f"/water-bodies/{wb}/main-result", algorithm="pdu_by_age")
    if m == "unavailable":
        return {"error": "unavail"}
    calc = (m or {}).get("calc")
    res = (m or {}).get("result")
    if not calc or not isinstance(res, dict) or not res.get("payload"):
        return {"error": "no_run"}
    run = {"id": calc["id"], "created_at": calc.get("finished_at")}
    p = res["payload"]
    sp_list = p.get("species_list") or list(p.get("species", {}))
    species = species if species in p.get("species", {}) else (sp_list[0] if sp_list else None)
    years = p.get("years", [])
    year = year if year in years else (years[-1] if years else None)
    return {"run": {"id": run["id"], "created_at": run.get("created_at"), "is_main": True},
            "payload": p, "species": species, "year": year, "species_list": sp_list, "years": years}


def _wb_name(code: str, lang: str) -> str:
    recs = _svc("data_model", "/entities/water_bodies/records")
    for r in recs if isinstance(recs, list) else []:
        v = r.get("values", {})
        if v.get("code") == code:
            return (v.get("name_kk") if lang == "kk" else None) or v.get("name_ru") or code
    return code


def _example(lang: str, ctx: dict) -> str:
    t = L[lang]
    d = example_data(ctx.get("wb") or "zhaysan", ctx.get("species"), ctx.get("year"))
    if d.get("error"):
        return f"> {t[d['error']]}"
    p, sp, year = d["payload"], d["species"], d["year"]
    s = p["species"][sp]
    yi = p["years"].index(year)
    by = s["by_year"][yi]
    m0, m1 = s["m0"], s["m1"]
    wbname = ctx.get("wb_name") or _wb_name(p.get("waterbody"), lang)
    when = (d["run"]["created_at"] or "")[:10]
    head = (f"**{t['wb']}:** {wbname} · {t['run_main'] if d['run']['is_main'] else t['run_last']} {when} · "
            f"**{t['sp']}:** {sp} · **{t['year']}:** {year} · m0 = {m0}, m1 = {m1}")
    rows = [f"| {t['age']} | {t['stock']} | {t['w']} | {t['bio']} | {t['load']} | {t['pcs']} | {t['t']} | {t['expl']} |",
            "|---|---|---|---|---|---|---|---|"]
    for i, j in enumerate(s["ages"]):
        x, w = by["stock"][i], by["weight"][i]
        mature = m0 <= j <= m1
        bio = (x or 0) * (w or 0) / 1e6
        if not mature:
            rows.append(f"| {j - 1}–{j} | {_num(x)} | {_num(w)} | {_num(bio, 1)} | {t['immature']} | — | — | — |")
            continue
        mark = " *" if by["capped"][i] else ""
        rows.append(f"| {j - 1}–{j} | {_num(x)} | {_num(w)} | {_num(bio, 1)} | {_num(j / m1, 2)} | "
                    f"{_num(by['pieces'][i])} | {_num(by['tonnes'][i], 1)} | {_num(100 * by['exploitation'][i], 1)}{mark} |")
    summary = (f"{t['P']}: **{_num(s['pdu_t'][yi], 1)} т** · {t['dist']}: {_num(s['distributed_t'][yi], 1)} т · "
               f"{t['left']}: {_num(s['left_t'][yi], 1)} т · {t['fish_bio']}: {_num(s['biomass_t'][yi], 1)} т · "
               f"{t['iters']}: {s['iterations'][yi]} · {t['stop']}: {s['stop_reason'][yi]}")
    if any(by["capped"]):
        summary += f" · * — {t['cap']}"
    return "\n\n".join([head, "\n".join(rows), summary])


def expand(md: str, lang: str, ctx: dict) -> str:
    def rep(m):
        kind, arg = m.group(1), m.group(2)
        return _params_table(arg, lang) if kind == "params" else _example(lang, ctx)
    return DIRECTIVE.sub(rep, md)


@app.get("/example", tags=["справка"])
def example(wb: str = "zhaysan", user: User = Depends(require("help.view"))):
    """Варианты для примера на числах: виды и годы запуска для мониторинга водоёма."""
    d = example_data(wb, None, None)
    return {k: d.get(k) for k in ("error", "species_list", "years", "species", "year", "run")}


@app.get("/bundled/{name}", tags=["справка"])
def bundled_image(name: str, user: User = Depends(require("help.view"))):
    p = export.BUNDLED_IMAGES / Path(name).name
    if not p.exists():
        raise not_found("Рисунок")
    return FileResponse(p)


# ------------------------------------------------------------------ правка
class ArticleIn(BaseModel):
    lang: str
    markdown: str
    comment: str = ""
    base_version: int | None = None


@app.put("/articles/{aid}", tags=["правка"])
def save_article(aid: str, body: ArticleIn, user: User = Depends(require("help.edit"))):
    a = articles.get(aid)
    if a is None or a.get("deleted"):
        raise not_found("Статья")
    _lang(body.lang)
    if body.base_version is not None and body.base_version != a.get("current_version"):
        raise AppError("help.conflict", "Статью изменили, пока вы её правили: откройте заново и повторите правку", 409,
                       {"current_version": a.get("current_version")})
    if body.lang == "ru" and not title_of(body.markdown):
        raise AppError("help.title", "Первая строка статьи — заголовок: «# Название»", 422)
    texts = _texts(aid)
    if texts.get(body.lang, "") == body.markdown:
        return {"version": a.get("current_version"), "changed": False}
    texts[body.lang] = body.markdown
    v = articles.add_version(aid, _files(texts), {"comment": body.comment or f"правка ({body.lang})", "lang": body.lang},
                             user.id)
    articles.update(aid, {"edited": True}, actor=user.id)
    audit(user, "help.edit", aid, {"lang": body.lang, "version": v["n"]})
    return {"version": v["n"], "changed": True}


@app.post("/articles/{aid}/restore/{n}", tags=["правка"])
def restore(aid: str, n: int, user: User = Depends(require("help.edit"))):
    texts = _texts(aid, n)
    v = articles.add_version(aid, _files(texts), {"comment": f"восстановлена версия {n}"}, user.id)
    articles.update(aid, {"edited": True}, actor=user.id)
    audit(user, "help.restore", aid, {"from": n, "version": v["n"]})
    return {"version": v["n"]}


@app.post("/articles/{aid}/take-bundled", tags=["правка"])
def take_bundled(aid: str, user: User = Depends(require("help.edit"))):
    """Заменить текст статьи текстом из поставки (после обновления приложения)."""
    a = articles.get(aid)
    if a is None or not a.get("bundled"):
        raise not_found("Статья поставки")
    texts = bundle_text(aid)
    v = articles.add_version(aid, _files(texts), {"comment": "текст поставки"}, user.id)
    articles.update(aid, {"edited": False, "bundle_update": False, "bundled_hash": _hash(texts)}, actor=user.id)
    audit(user, "help.take_bundled", aid, {"version": v["n"]})
    return {"version": v["n"]}


class NewArticleIn(BaseModel):
    id: str
    section: str
    order: int = 100
    title_ru: str
    title_kk: str = ""
    routes: list[str] = []


@app.post("/articles", tags=["правка"], status_code=201)
def create_article(body: NewArticleIn, user: User = Depends(require("help.edit"))):
    if not ID_RE.match(body.id):
        raise AppError("help.id", "Код статьи: латинские строчные буквы, цифры, «-», «_»", 422)
    if articles.get(body.id) is not None:
        raise AppError("help.exists", "Статья с таким кодом уже есть", 409)
    texts = {"ru": f"# {body.title_ru}\n\n", "kk": f"# {body.title_kk}\n\n" if body.title_kk else ""}
    articles.create({"section": body.section, "order": body.order, "routes": body.routes, "bundled": False,
                     "edited": True}, actor=user.id, obj_id=body.id)
    articles.add_version(body.id, _files(texts), {"comment": "создание"}, user.id)
    audit(user, "help.create", body.id)
    return {"id": body.id}


@app.delete("/articles/{aid}", tags=["правка"])
def delete_article(aid: str, user: User = Depends(require("help.edit"))):
    a = articles.get(aid)
    if a is None or a.get("deleted"):
        raise not_found("Статья")
    if a.get("bundled"):
        raise AppError("help.bundled", "Статью из поставки удалить нельзя — её можно изменить", 400)
    articles.delete(aid)
    audit(user, "help.delete", aid)
    return {"ok": True}


# ------------------------------------------------------------------ рисунки
@app.post("/images", tags=["правка"], status_code=201)
async def upload_image(file: UploadFile = File(...), user: User = Depends(require("help.edit"))):
    ext = IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise AppError("help.image_type", "Рисунок: PNG, JPEG, GIF или WebP", 415)
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise AppError("help.image_size", "Рисунок больше 10 МБ", 413)
    try:
        import io

        from PIL import Image
        Image.open(io.BytesIO(data)).verify()
    except Exception:  # noqa: BLE001 — любой сбой разбора = не рисунок
        raise AppError("help.image_type", "Файл не является рисунком PNG, JPEG, GIF или WebP", 415)
    name = new_id().lower() + ext
    atomic_write_bytes(IMAGES / name, data)
    audit(user, "help.image", name, {"source": file.filename})
    return {"name": name, "markdown": f"![{Path(file.filename or 'рисунок').stem}](help-image:{name})"}


@app.get("/images/{name}", tags=["справка"])
def get_image(name: str, user: User = Depends(require("help.view"))):
    p = image_path(name)
    if p is None:
        raise not_found("Рисунок")
    return FileResponse(p)


def image_path(name: str) -> Path | None:
    if not re.match(r"^[a-z0-9]+\.(png|jpg|gif|webp)$", name):
        return None
    p = IMAGES / name
    return p if p.exists() else None


# ------------------------------------------------------------------ выгрузка
def _collect(lang: str, section: str | None, article: str | None, ctx: dict | None = None,
             user: User | None = None) -> tuple[str, list[dict]]:
    parts = []
    for s in toc(lang, user):
        if section and s["code"] != section:
            continue
        items = []
        for it in s["articles"]:
            if article and it["id"] != article:
                continue
            md, _ = _text_in(_texts(it["id"]), lang)
            items.append({"id": it["id"], "title": it["title"], "markdown": _unlink_hidden(expand(md, lang, ctx or {}), user)})
        if items:
            parts.append({"title": s["title"], "articles": items})
    if not parts:
        raise not_found("Раздел или статья")
    if article:
        title = parts[0]["articles"][0]["title"]
    elif section:
        title = parts[0]["title"]
    else:
        title = export.T[lang]["guide"]
    return title, parts


def _filename(lang: str, section: str | None, article: str | None, ext: str) -> str:
    return f"FishStock_{article or section or 'guide'}_{lang}.{ext}"


@app.get("/export.docx", tags=["выгрузка"])
def export_docx(lang: str = "ru", section: str | None = None, article: str | None = None, wb: str = "zhaysan",
                species: str | None = None, year: int | None = None,
                user: User = Depends(require("help.view"))):
    title, parts = _collect(_lang(lang), section, article, {"wb": wb, "species": species, "year": year}, user)
    data = export.to_docx(title, parts, lang, image_path)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(lang, section, article, "docx")}"'})


@app.get("/export.pdf", tags=["выгрузка"])
def export_pdf(lang: str = "ru", section: str | None = None, article: str | None = None, wb: str = "zhaysan",
                species: str | None = None, year: int | None = None,
               user: User = Depends(require("help.view"))):
    title, parts = _collect(_lang(lang), section, article, {"wb": wb, "species": species, "year": year}, user)
    data = export.to_pdf(title, parts, lang, image_path)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(lang, section, article, "pdf")}"'})


@app.get("/export.md", tags=["выгрузка"])
def export_md(lang: str = "ru", section: str | None = None, article: str | None = None, wb: str = "zhaysan",
                species: str | None = None, year: int | None = None,
              user: User = Depends(require("help.view"))):
    """Markdown одним файлом (так получен docs/install.md)."""
    title, parts = _collect(_lang(lang), section, article, {"wb": wb, "species": species, "year": year}, user)
    return Response(export.to_markdown(title, parts), media_type="text/markdown; charset=utf-8")
