"""Что видят роли без права «results.view» (наблюдатель, оператор, «Презентация»; docs/decisions.md, № 62).

Им показываются исходные данные и ПДУ НПЦ (официальный). Уловистость, запасы (по уловам и байесовская модель,
проверки) и ПДУ, рассчитанный в приложении (F = k·M), видят только администратор, математик и ихтиолог.
Ограничение — в сервисе дашбордов, а не только в интерфейсе: шаблон и общие дашборды отдаются без скрытых
вкладок, разделов и виджетов, а данные скрытых представлений по прямому запросу — 403.
"""
from __future__ import annotations

import copy

from fishcommon.errors import AppError

from . import insights
from .insights import calc_stock_views, calc_views  # после insights: он их подключает

PERM = "results.view"

# алгоритмы, результаты которых — оценки модели; pdu_by_age (h) — ПДУ НПЦ по возрастам (официальная квота);
# stock_by_catch — прежний код (до решения № 70) в сохранённых дашбордах
RESULT_ALGOS = {"net_catchability", "seine_catchability", "seine_likelihood", "net_likelihood", "seine_stock", "net_stock",
                "combined_stock", "stock_by_catch", "bayes_cohort", "forecast_pdu", "bayes_checks", "removal_pdu"}
# представления результатов расчёта, кроме раздела «ПДУ НПЦ (официальный)» (pn_*)
RESULT_VIEWS = {v for v in (*calc_views.VIEWS, *calc_stock_views.VIEWS) if not v.startswith("pn_")}
assert RESULT_VIEWS.isdisjoint({v for v in insights.VIEWS if v not in calc_views.VIEWS and v not in calc_stock_views.VIEWS})

# проверки модели (шаг «Проверки байесовской модели», раздел «Запасы → Проверки модели») скрыты для всех ролей —
# решение заказчика 24.10 (№ 65); код расчёта и прежние запуски сохраняются
OFF_ALGOS = {"bayes_checks"}
OFF_VIEWS = {v for v in calc_views.VIEWS if v.startswith("bc_")}

FORBIDDEN_MSG = "Результаты модели (уловистость, запасы, ПДУ приложения) доступны администратору, математику и ихтиологу"


def full(user) -> bool:
    return user.can(PERM)


def _match(src: dict | None, views, algos) -> bool:
    src = src or {}
    kind = src.get("kind")
    if kind == "insight":
        return src.get("view") in views
    if kind in ("run", "payload"):
        return src.get("algorithm") in algos
    return False


def restricted_source(src: dict | None) -> bool:
    return _match(src, RESULT_VIEWS, RESULT_ALGOS)


def off_source(src: dict | None) -> bool:
    return _match(src, OFF_VIEWS, OFF_ALGOS)


def check_source(user, src: dict) -> None:
    if off_source(src):
        raise AppError("widget.hidden", "Этот раздел скрыт", 404)
    if not full(user) and restricted_source(src):
        raise AppError("auth.forbidden", FORBIDDEN_MSG, 403)


def hidden_widgets(board: dict, full_access: bool = False) -> set[str]:
    """id скрытых виджетов: проверки модели — для всех; без права на результаты — и результаты модели.
    Плюс текстовые виджеты вкладок и разделов, в которых не осталось ничего другого."""
    ws = board.get("widgets") or []
    hid = {w.get("id") for w in ws if w.get("type") != "text"
           and (off_source(w.get("source")) or (not full_access and restricted_source(w.get("source"))))}

    def emptied(key):
        groups: dict = {}
        for w in ws:
            groups.setdefault(key(w), []).append(w)
        out = set()
        for g in groups.values():
            data = [w for w in g if w.get("type") != "text"]
            if data and all(w.get("id") in hid for w in data):
                out |= {w.get("id") for w in g}
        return out

    hid |= emptied(lambda w: (w.get("tab"), w.get("section")))
    hid |= emptied(lambda w: w.get("tab"))
    return hid


def filter_board(board: dict, user) -> dict:
    """Дашборд для роли: без скрытых виджетов, а также вкладок и разделов, где не осталось виджетов."""
    d = copy.deepcopy(board)
    hid = hidden_widgets(d, full(user))
    if not hid:
        return d
    before = d.get("widgets") or []
    d["widgets"] = [w for w in before if w.get("id") not in hid]
    had_tab = {w.get("tab") for w in before}
    had_sec = {(w.get("tab"), w.get("section")) for w in before if w.get("section")}
    left_tab = {w.get("tab") for w in d["widgets"]}
    left_sec = {(w.get("tab"), w.get("section")) for w in d["widgets"] if w.get("section")}
    tabs = []
    for t in d.get("tabs") or []:
        code = t.get("code")
        if code in had_tab and code not in left_tab:
            continue
        if t.get("sections"):
            t["sections"] = [s for s in t["sections"]
                             if not ((code, s.get("code")) in had_sec and (code, s.get("code")) not in left_sec)]
        tabs.append(t)
    d["tabs"] = tabs
    if full(user):
        return d
    d["restricted"] = True
    if d.get("system") and d.get("id") == "monitoring":
        d["description"] = "Исходные данные и ПДУ НПЦ выбранного водоёма."
    return d


# пояснения, отсылающие к скрытому разделу «ПДУ, рассчитанный в приложении», ролям без права не показываются
APP_PDU_MARKS = ("рассчитанный в приложении", "ПДУ приложения", "қосымшада есептелген", "қосымша ШРА")


def filter_explain(res: dict, hidden: set[str]) -> dict:
    """Пояснения без ссылок на скрытые слайды и без отсылок к ПДУ приложения."""
    ex = res.get("explain")
    if not ex:
        return res
    if ex.get("next"):
        ex["next"] = [n for n in ex["next"] if n.get("widget") not in hidden]
    for k in ("how", "now"):
        if ex.get(k):
            ex[k] = [x for x in ex[k] if not (isinstance(x, str) and any(m.lower() in x.lower() for m in APP_PDU_MARKS))]
    return res


def strip_status(runs: dict | None, user) -> dict | None:
    """Сводка запусков водоёма: ПДУ приложения заменяется ПДУ НПЦ."""
    if runs is None or full(user):
        return runs
    runs = dict(runs)
    runs["pdu"] = runs.get("pdu_npc")
    return runs
