"""Сравнение расчётов (кабинет «Мониторинг» → «Сравнение расчётов», решение № 77).

Ряд сравнения — водоём + расчёт + вид (+ k для прогноза, + орудие для запаса по уловам):
    forecast — прогноз и ПДУ по модели (алгоритм j): численность / промысловая биомасса по годам (история модели и
               прогноз при выбранном k), ПДУ по годам прогноза, вероятность снижения запаса, F;
    model    — запас по математической модели (алгоритм i): численность по годам с интервалом;
    catch    — запас по уловам (алгоритм g): численность или промысловый запас по годам выбранным орудием.
Данные — результаты расчётов как есть; сервис ничего не пересчитывает.
"""
from __future__ import annotations

from fishcommon.errors import AppError

SOURCES = {"forecast": "forecast_pdu", "model": "bayes_cohort", "catch": "combined_stock"}
GEARS = ("сеть", "невод", "сеть+невод")
MAX_SERIES = 12


def kf(k) -> str:
    return f"{float(k):g}".replace(".", ",")


def _L(lang, ru, kk):
    return kk if lang == "kk" else ru


class Store:
    """Результаты расчётов, прочитанные за один запрос (ряды одного расчёта не читают его повторно)."""

    def __init__(self, svc):
        self.svc = svc
        self._res: dict = {}

    def result(self, cid):
        if cid not in self._res:
            try:
                self._res[cid] = self.svc["algo_admin"].get(f"/calcs/{cid}/result")
            except AppError:
                self._res[cid] = None
        return self._res[cid]


def list_calcs(svc, source: str, water_body: str | None = None) -> list[dict]:
    """Расчёты алгоритма источника с результатом (служебные результаты — подбор egg_scale — не показываются)."""
    alg = SOURCES.get(source)
    if not alg:
        raise AppError("compare.source", "Неизвестный источник сравнения", 400)
    q = {"algorithm": alg, **({"water_body": water_body} if water_body else {})}
    cs = svc["algo_admin"].get("/calcs", **q) or []
    out = []
    for c in cs:
        r = c.get("result") or {}
        if not (c.get("has_result") or r.get("result_id")) or r.get("not_main"):
            continue
        out.append({"id": c["id"], "title": c.get("title"), "is_main": bool(c.get("is_main")), "water_body": c.get("water_body"),
                    "finished_at": r.get("finished_at"), "version": r.get("version"), "stale": bool(c.get("stale")),
                    "param_set_name": c.get("param_set_name")})
    return sorted(out, key=lambda c: (c["water_body"] or "", not c["is_main"], c["title"] or ""))


def _species_list(source, pl, res, codes):
    """[(название в расчёте, код справочника)]."""
    if source == "catch":
        names = []
        for r in ((res.get("tables") or {}).get("tonnes") or {}).get("rows") or []:
            if r.get("species") not in names:
                names.append(r.get("species"))
        return [(n, codes.get(str(n).strip().lower(), n)) for n in names]
    return [(n, (R or {}).get("code") or codes.get(str(n).strip().lower(), n))
            for n, R in (pl.get("species") or {}).items() if (R or {}).get("available", True)]


def forecast_ks(pl) -> tuple[list[float], float, bool]:
    """k, для которых в результате прогноза есть траектории по годам; k текущего расчёта; есть ли сетка 3.2.0."""
    base = float(pl.get("k") if pl.get("k") is not None else 1.0)
    full, grid = False, set()
    for R in (pl.get("species") or {}).values():
        K = (R or {}).get("k_scen") or {}
        if K.get("total_q_years"):
            full = True
            grid |= {float(k) for k in K.get("k") or []}
    return sorted(grid | {base, 0.0}), base, full


def calc_meta(store: "Store", cid: str, source: str, codes: dict, sp_names: dict) -> dict:
    """Виды, k и орудия расчёта. codes — {название вида строчными: код справочника}."""
    res = store.result(cid)
    if not res:
        return {"id": cid, "source": source, "error": "У расчёта нет результата", "species": []}
    pl = res.get("payload") or {}
    species = [{"code": c, "name": sp_names.get(c, n)} for n, c in _species_list(source, pl, res, codes)]
    c = res.get("calc") or {}
    out = {"id": cid, "source": source, "species": species, "title": c.get("title"), "water_body": c.get("water_body"),
           "is_main": bool(c.get("is_main"))}
    if source == "forecast":
        ks, base, full = forecast_ks(pl)
        out.update({"k": ks, "base_k": base, "k_full": full})
    if source == "catch":
        out["gears"] = list(GEARS)
    return out


def _sp_key(pl_species: dict, species: str, codes: dict):
    if species in pl_species:
        return species
    for k in pl_species:
        if codes.get(str(k).strip().lower()) == species:
            return k
    return None


def _forecast_k(R, k: float):
    """Траектории и итоги прогноза при k: (численность q5×H, промысловая биомасса q5×H, ПДУ по годам (медианы),
    ПДУ первого года q5, численность в конце q5, вероятность снижения, F). None — этого k в расчёте нет."""
    K = R.get("k_scen") or {}
    ks = [float(x) for x in K.get("k") or []]
    S = R.get("scenarios") or {}
    st = R.get("settings") or {}
    if k in ks and K.get("total_q_years"):
        i = ks.index(k)
        return {"total": K["total_q_years"][i], "fishable": (K.get("fishable_q_years") or [None] * len(ks))[i],
                "pdu_years": K["pdu_t_median_years"][i], "pdu1": K["pdu_t_q"][i],
                "end": K["total_end_q"][i], "risk": K["p_decline"][i], "F": K["F"][i]}
    if k == 0.0 and S.get("none"):
        n = S["none"]
        h = len(R.get("years_fc") or [])
        return {"total": n["total_q"], "fishable": n.get("fishable_q"), "pdu_years": [0.0] * h, "pdu1": [0.0] * 5,
                "end": [q[-1] for q in n["total_q"]], "risk": n.get("p_decline"), "F": 0.0}
    if st.get("k") is not None and k == float(st["k"]) and S.get("baranov"):
        b = S["baranov"]
        return {"total": b["total_q"], "fishable": b.get("fishable_q"), "pdu_years": b["pdu_t_q"][2],
                "pdu1": [q[0] for q in b["pdu_t_q"]], "end": [q[-1] for q in b["total_q"]], "risk": b.get("p_decline"),
                "F": (R.get("F_q") or [[None]] * 3)[2][0]}
    return None


def series_data(st: Store, items: list[dict], measure: str, codes: dict, wb_names: dict, sp_names: dict, lang: str = "ru") -> dict:
    """Данные рядов. items — [{source, calc, species, k?, gear?}]; measure — total (численность) или fishable
    (промысловая биомасса / промысловый запас, т)."""
    if not items:
        return {"series": []}
    if len(items) > MAX_SERIES:
        raise AppError("compare.too_many", f"Не больше {MAX_SERIES} рядов в одном сравнении", 400)
    measure = measure if measure in ("total", "fishable") else "total"
    out = []
    for n, it in enumerate(items):
        src, cid, sp = it.get("source") or "forecast", it.get("calc"), it.get("species")
        base = {"n": n, "source": src, "calc": cid, "species": sp, "k": it.get("k"), "gear": it.get("gear")}
        res = st.result(cid) if cid else None
        if not res:
            out.append({**base, "error": _L(lang, "Расчёт не найден или у него нет результата", "Есептеу табылмады немесе нәтижесі жоқ")})
            continue
        c = res.get("calc") or {}
        base.update({"calc_title": c.get("title"), "is_main": bool(c.get("is_main")), "water_body": c.get("water_body"),
                     "water_body_name": wb_names.get(c.get("water_body"), c.get("water_body")),
                     "species_name": sp_names.get(codes.get(str(sp).strip().lower(), sp), sp)})
        pl = res.get("payload") or {}
        try:
            if src == "forecast":
                out.append({**base, **_forecast_series(pl, sp, it, measure, codes, lang)})
            elif src == "model":
                out.append({**base, **_model_series(pl, sp, measure, codes, lang)})
            elif src == "catch":
                out.append({**base, **_catch_series(res, sp, it, measure, codes, lang)})
            else:
                out.append({**base, "error": _L(lang, "Неизвестный источник", "Белгісіз дереккөз")})
        except _Skip as e:
            out.append({**base, "error": str(e)})
    return {"series": out, "measure": measure}


class _Skip(Exception):
    pass


def _forecast_series(pl, sp, it, measure, codes, lang):
    key = _sp_key(pl.get("species") or {}, sp, codes)
    if key is None:
        raise _Skip(_L(lang, "В этом расчёте прогноза нет такого вида", "Бұл болжам есептеуінде мұндай түр жоқ"))
    R = pl["species"][key]
    try:
        k = float(it.get("k") if it.get("k") is not None else (pl.get("k") if pl.get("k") is not None else 1.0))
    except (TypeError, ValueError):
        raise _Skip(_L(lang, "Неверное k", "k қате")) from None
    d = _forecast_k(R, k)
    if d is None:
        raise _Skip(_L(lang, f"В расчёте нет сценария k = {kf(k)} — нужна версия прогноза 3.2.0 и это k в «Сценариях k»",
                       f"Есептеуде k = {kf(k)} сценарийі жоқ — болжамның 3.2.0 нұсқасы және «k сценарийлерінде» осы k керек"))
    H = R["hist"]
    if measure == "fishable":
        hist, fc = H.get("fishable_q"), d["fishable"]
        last = [q[-1] for q in hist] if hist else None
    else:
        hist, fc = H.get("total_q"), d["total"]
        last = H.get("total_last_draws_q") or ([q[-1] for q in hist] if hist else None)
    if fc is None or hist is None:
        raise _Skip(_L(lang, "В расчёте нет промысловой биомассы по годам для этого k", "Есептеуде осы k үшін жылдар бойынша кәсіптік биомасса жоқ"))
    return {"k": k, "years_hist": R["years_hist"], "years_fc": R["years_fc"], "hist_q": hist, "fc_q": fc, "join_q": last,
            "pdu_years": d["pdu_years"], "pdu1_q": d["pdu1"], "end_q": d["end"], "risk": d["risk"], "F": d["F"],
            "n_draws": R.get("n_draws")}


def _model_series(pl, sp, measure, codes, lang):
    if measure == "fishable":
        raise _Skip(_L(lang, "У модели (i) по годам есть только численность — переключите на «численность»",
                       "Модельде (i) жылдар бойынша тек сан бар — «сан» режиміне ауыстырыңыз"))
    key = _sp_key(pl.get("species") or {}, sp, codes)
    if key is None:
        raise _Skip(_L(lang, "В этом расчёте модели нет такого вида", "Бұл модель есептеуінде мұндай түр жоқ"))
    R = pl["species"][key]
    if not R.get("total_obs_q"):
        raise _Skip(_L(lang, "Модель для этого вида не посчитана", "Бұл түр үшін модель есептелмеген"))
    return {"years_hist": R["years"], "years_fc": [], "hist_q": R["total_obs_q"], "fc_q": None}


def _catch_series(res, sp, it, measure, codes, lang):
    gear = it.get("gear") if it.get("gear") in GEARS else "сеть+невод"
    rows = ((res.get("tables") or {}).get("tonnes") or {}).get("rows") or []
    names = {str(r.get("species")).strip().lower() for r in rows}
    want = None
    for n in names:
        if n == str(sp).strip().lower() or codes.get(n) == sp:
            want = n
    if want is None:
        raise _Skip(_L(lang, "В этом расчёте запаса по уловам нет такого вида", "Бұл ауланым бойынша қор есептеуінде мұндай түр жоқ"))
    col = "tonnes_fishable" if measure == "fishable" else "stock"
    pts = sorted((int(r["year"]), r.get(col)) for r in rows if str(r.get("species")).strip().lower() == want and r.get("gear") == gear)
    if not pts:
        raise _Skip(_L(lang, f"Нет запаса по орудию «{gear}»", f"«{gear}» құралы бойынша қор жоқ"))
    return {"gear": gear, "years_hist": [p[0] for p in pts], "years_fc": [], "hist_q": [[p[1] for p in pts]], "fc_q": None}
