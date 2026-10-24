"""
Вкладка «Запасы»: «Сходятся ли оценки запаса» и представления по ТЗ docs/specs/stock_insights.md
(утверждено заказчиком 24.10.2026).

Новых формул нет: только сравнения и описательная статистика (отношение, доля, медиана, среднее) чисел,
уже посчитанных запуском: байесовская модель (этап 4), запас по уловам (этап 2), ПДУ НПЦ по возрастам (этап 3),
прогноз (этап 5). Критерии сходимости — статьи (R̂ ≤ 1,01, ESS ≥ 400, без расходимостей, E-BFMI > 0,3).
"""
from __future__ import annotations

import statistics as st_
from math import log10

from .insights import NoData, col
from .calc_views import L, nf, pieces, age_label, _bayes, _bayes_species, _bcommon, _bands, _names, _key_for, _year, _pdu, _fc

VIEWS = {}

# критерии сходимости статьи (не правила: их не меняют)
RHAT_MAX, ESS_MIN, EBFMI_MIN = 1.01, 400, 0.3


def _r(v):
    return None if v is None else float(v)


def _ratio(a, b):
    return a / b if (a is not None and b and a > 0 and b > 0) else None


def _x(v, d=2):
    """Отношение «×1,26»."""
    return "—" if v is None else "×" + nf(v, d if v < 10 else 1 if v < 100 else 0)


def _times(v):
    """«в 2,7 раза» — число раз для отношения ≥ 1."""
    return nf(v, 1 if v < 100 else 0)


def convergence(R, lang="ru"):
    """Нарушения критериев сходимости статьи: [(код, текст)]; пусто — модель сошлась."""
    m = R.get("meta") or {}
    dg = m.get("diagnostics") or {}
    out = []
    rh = max([v for v in (m.get("rhat_X_max"), dg.get("rhat_max_params")) if v is not None] or [0])
    if rh > RHAT_MAX:
        out.append(("rhat", f"R̂ {nf(rh, 3)}"))
    div = m.get("divergences") if m.get("divergences") is not None else dg.get("divergences")
    if div:
        out.append(("div", L(lang, f"расходимостей {nf(div, 0)}", f"алшақтық {nf(div, 0)}")))
    eb, et = dg.get("ess_bulk_min_params"), dg.get("ess_tail_min_params")
    if (eb is not None and eb < ESS_MIN) or (et is not None and et < ESS_MIN):
        out.append(("ess", f"ESS {nf(eb, 0) if eb is not None else '—'} / {nf(et, 0) if et is not None else '—'}"))
    if dg.get("ebfmi_min") is not None and dg["ebfmi_min"] <= EBFMI_MIN:
        out.append(("ebfmi", f"E-BFMI {nf(dg['ebfmi_min'], 2)}"))
    return out


def _final_total(R):
    d = R.get("data") or {}
    if d.get("final_total"):
        return [_r(v) for v in d["final_total"]]
    out = []
    for r in d.get("final_by_age") or []:
        vals = [v for v in (r or []) if v is not None]
        out.append(sum(vals) if vals else None)
    return out


def _npc_total(R):
    d = R.get("data") or {}
    return [_r(v) for v in (d.get("npc_total") or [None] * len(R["years"]))]


def death_parts(R, yi):
    dd = R["deaths"]
    nat, pr, ca = (dd["natural"][yi] or 0), (dd["predators"][yi] or 0), (dd["catch"][yi] or 0)
    po = dd["poaching"][yi] or 0
    po = po if po > 0 else 0
    return nat, pr, ca, po


def fishing_share(R, yi):
    """Доля вылова (ПДУ + браконьерство) в убыли за год, % — по медианам составляющих."""
    nat, pr, ca, po = death_parts(R, yi)
    tot = nat + pr + ca + po
    return (ca + po) / tot * 100 if tot > 0 else None


def _rules(rules):
    from .insights import rule_params
    rules = rules or {}
    en_c, p_c = rule_params(rules, "model_vs_catch")
    en_n, p_n = rule_params(rules, "model_vs_npc")
    en_t, p_t = rule_params(rules, "trend_vs_catch")
    return {"en_c": en_c, "Rc": float(p_c["ratio"]), "en_n": en_n, "Rn": float(p_n["ratio"]),
            "en_t": en_t, "Rt": float(p_t["ratio"])}


def _off(r, R):
    return r is not None and (r > R or r < 1 / R)


def trust_row(D, key, R, y, P):
    """Строка сводки по виду за год. None — года нет в модели."""
    lang = D.lang
    names = _names(D)
    code = names.get(key.strip().lower(), key)
    years = R["years"]
    if y not in years:
        return None
    yi = years.index(y)
    tot = R["total_obs_q"]
    med, lo, hi = _r(tot[2][yi]), _r(tot[0][yi]), _r(tot[4][yi])
    fin, npc = _final_total(R), _npc_total(R)
    fy, ny = (fin[yi] if yi < len(fin) else None), (npc[yi] if yi < len(npc) else None)
    r_c, r_n = _ratio(med, fy), _ratio(med, ny)
    # изменение за период: первый год → выбранный
    m0, f0, n0 = _r(tot[2][0]), (fin[0] if fin else None), (npc[0] if npc else None)
    ch_m, ch_c, ch_n = _ratio(med, m0) if yi > 0 else None, _ratio(fy, f0) if yi > 0 else None, _ratio(ny, n0) if yi > 0 else None
    trend = _ratio(ch_m, ch_c)
    conv = convergence(R, lang)
    fsh = fishing_share(R, yi)
    shares = [v for v in (fishing_share(R, i) for i in range(len(years))) if v is not None]
    fsh_mean = sum(shares) / len(shares) if shares else None
    c_hit = P["en_c"] and _off(r_c, P["Rc"])
    n_hit = P["en_n"] and _off(r_n, P["Rn"])
    t_hit = P["en_t"] and _off(trend, P["Rt"])
    items, short = [], []
    if conv:
        what = ", ".join(t for _, t in conv)
        items.append(L(lang, f"модель не сошлась ({what}) — числам модели не доверять, пока не сойдётся",
                       f"модель жинақталмады ({what}) — жинақталғанша модель сандарына сенбеңіз"))
        short.append(L(lang, "Модель не сошлась", "Модель жинақталмады"))
    else:
        if c_hit:
            items.append(L(lang, f"модель в {_times(r_c if r_c >= 1 else 1 / r_c)} раза {'выше' if r_c >= 1 else 'ниже'} оценки по уловам",
                           f"модель ауланым бағасынан {_times(r_c if r_c >= 1 else 1 / r_c)} есе {'жоғары' if r_c >= 1 else 'төмен'}"))
            short.append(L(lang, "уловы", "ауланым"))
        if n_hit:
            items.append(L(lang, f"модель в {_times(r_n if r_n >= 1 else 1 / r_n)} раза {'выше' if r_n >= 1 else 'ниже'} оценки НПЦ",
                           f"модель ҒӨО бағасынан {_times(r_n if r_n >= 1 else 1 / r_n)} есе {'жоғары' if r_n >= 1 else 'төмен'}"))
            short.append(L(lang, "НПЦ", "ҒӨО"))
        if t_hit:
            items.append(L(lang, f"модель и оценка по уловам меняются по-разному: {_x(ch_m)} и {_x(ch_c)} с {years[0]} г.",
                           f"модель мен ауланым бағасы әртүрлі өзгереді: {years[0]} ж. бастап {_x(ch_m)} және {_x(ch_c)}"))
            short.append(L(lang, "динамика", "динамика"))
    fact = (L(lang, f"по модели вылов — {nf(fsh, 0)} % убыли за год (в среднем {nf(fsh_mean, 0)} %)",
              f"модель бойынша аулау — жылдағы кемудің {nf(fsh, 0)} %-ы (орташа {nf(fsh_mean, 0)} %)") if fsh is not None else None)
    if conv:
        level, label = "warning", short[0]
        phrase = L(lang, "Есть вопросы: ", "Сұрақтар бар: ") + items[0] + "."
    elif items:
        level = "warning"
        txt = ", ".join(short)
        label = txt[0].upper() + txt[1:] if len(short) > 1 else {
            L(lang, "уловы", "ауланым"): L(lang, "Расходится с уловами", "Ауланыммен алшақ"),
            L(lang, "НПЦ", "ҒӨО"): L(lang, "Расходится с НПЦ", "ҒӨО-мен алшақ"),
            L(lang, "динамика", "динамика"): L(lang, "Разная динамика", "Динамика әртүрлі")}[short[0]]
        phrase = L(lang, "Есть вопросы: ", "Сұрақтар бар: ") + "; ".join(items) + "."
    else:
        level, label = "ok", L(lang, "Можно опираться", "Сүйенуге болады")
        phrase = L(lang, "Можно опираться: модель сошлась, согласуется с оценкой по уловам и НПЦ, динамика совпадает.",
                   "Сүйенуге болады: модель жинақталды, ауланым бағасымен және ҒӨО-мен үйлеседі, динамика сәйкес.")
    if fact:
        phrase += " " + fact[0].upper() + fact[1:] + "."
    vals = [v for v in (lo, hi, fy, ny, med) if v]
    span = (min(vals) / 2, max(vals) * 2) if vals else None
    spark = {"model": [_ratio(_r(v), m0) for v in tot[2]], "catch": [_ratio(v, f0) for v in fin],
             "npc": [_ratio(v, n0) for v in npc]}
    row = {"_code": code, "species": D.sp_name(code), "_median": med, "_level": level,
           "est": {"median": med, "lo": lo, "hi": hi, "catch": fy, "npc": ny, "span": span,
                   "text": L(lang, f"модель {pieces(med)} · по уловам {pieces(fy)} · НПЦ {pieces(ny)}",
                             f"модель {pieces(med, 'kk')} · ауланым {pieces(fy, 'kk')} · ҒӨО {pieces(ny, 'kk')}"), "to": "by_total"},
           "ratio": {"catch": r_c, "npc": r_n, "hit_c": bool(c_hit), "hit_n": bool(n_hit), "on_c": P["en_c"], "on_n": P["en_n"],
                     "thr_c": P["Rc"], "thr_n": P["Rn"], "to": "by_total"},
           "trend": {"model": ch_m, "catch": ch_c, "npc": ch_n, "ratio": trend, "hit": bool(t_hit), "y0": years[0],
                     "spark": spark, "to": "by_total"},
           "conv": {"ok": not conv, "text": L(lang, "не сошлась", "жинақталмады") if conv else L(lang, "сошлась", "жинақталды"),
                    "detail": " · ".join(t for _, t in conv), "all": [t for _, t in conv], "to": "by_diag"},
           "fishing": {"pct": fsh, "mean": fsh_mean, "to": "by_deaths"},
           "verdict": {"level": level, "label": label, "phrase": phrase}}
    flat = {"species": row["species"], "median": med, "lo": lo, "hi": hi, "catch": fy, "npc": ny,
            "r_c": round(r_c, 3) if r_c else None, "r_n": round(r_n, 3) if r_n else None,
            "ch_m": round(ch_m, 3) if ch_m else None, "ch_c": round(ch_c, 3) if ch_c else None, "ch_n": round(ch_n, 3) if ch_n else None,
            "conv": row["conv"]["text"] + (f": {row['conv']['detail']}" if row["conv"]["detail"] else ""), "fishing": round(fsh, 1) if fsh is not None else None,
            "verdict": label, "phrase": phrase, "_code": code, "_level": level}
    return row, flat


def v_st_trust(D, opt, rules=None):
    pl, meta = _bayes(D)
    lang = D.lang
    P = _rules(rules)
    any_r = next((R for R in pl["species"].values() if R.get("available")), None)
    if any_r is None:
        raise NoData(L(lang, "В запуске нет видов с результатом байесовской модели", "Іске қосуда байестік модель нәтижесі бар түрлер жоқ"))
    y, years = _year({"years": any_r["years"]}, opt)
    rows, flat, skipped = [], [], []
    for key, R in pl["species"].items():
        if not R.get("available"):
            skipped.append(key)
            continue
        res = trust_row(D, key, R, y, P)
        if res:
            rows.append(res[0])
            flat.append(res[1])
    if not rows:
        raise NoData(L(lang, f"За {y} г. нет результатов модели", f"{y} ж. модель нәтижелері жоқ"))
    order = sorted(range(len(rows)), key=lambda i: -(rows[i]["_median"] or 0))
    rows, flat = [rows[i] for i in order], [flat[i] for i in order]
    names = _names(D)
    for key in skipped:
        code = names.get(key.strip().lower(), key)
        rows.append({"_code": code, "species": D.sp_name(code), "_level": None, "skipped": True,
                     "verdict": {"level": None, "label": L(lang, "Модель не считалась", "Модель есептелмеді"), "phrase": ""}})
    ok = sum(1 for r in rows if r["_level"] == "ok")
    n = sum(1 for r in rows if not r.get("skipped"))
    head = L(lang, f"Модели можно опираться у {ok} из {n} видов", f"{n} түрдің {ok}-інде модельге сүйенуге болады")
    thr = L(lang, "Пороги: ", "Шектер: ") + " · ".join([
        L(lang, f"модель ÷ уловы {nf(P['Rc'], 1).rstrip('0').rstrip(',')}×", f"модель ÷ ауланым {nf(P['Rc'], 1).rstrip('0').rstrip(',')}×"),
        L(lang, f"÷ НПЦ {nf(P['Rn'], 1).rstrip('0').rstrip(',')}×", f"÷ ҒӨО {nf(P['Rn'], 1).rstrip('0').rstrip(',')}×"),
        L(lang, f"динамика {nf(P['Rt'], 1).rstrip('0').rstrip(',')}×", f"динамика {nf(P['Rt'], 1).rstrip('0').rstrip(',')}×"),
        L(lang, "сходимость — критерии статьи", "жинақталу — мақала критерийлері")])
    cols = [col("species", L(lang, "Вид", "Түр")), col("median", L(lang, "Модель, медиана", "Модель, медиана"), "integer"),
            col("lo", "2,5 %", "integer"), col("hi", "97,5 %", "integer"), col("catch", L(lang, "По уловам", "Ауланым бойынша"), "integer"),
            col("npc", L(lang, "НПЦ", "ҒӨО"), "integer"), col("r_c", L(lang, "Модель ÷ уловы", "Модель ÷ ауланым"), "number"),
            col("r_n", L(lang, "Модель ÷ НПЦ", "Модель ÷ ҒӨО"), "number"),
            col("ch_m", L(lang, f"Изменение с {years[0]}: модель", f"{years[0]} бастап өзгеріс: модель"), "number"),
            col("ch_c", L(lang, "по уловам", "ауланым"), "number"), col("ch_n", L(lang, "НПЦ", "ҒӨО"), "number"),
            col("conv", L(lang, "Сходимость", "Жинақталу")), col("fishing", L(lang, "Вылов в убыли, %", "Кемудегі аулау, %"), "number"),
            col("verdict", L(lang, "Вывод", "Қорытынды")), col("phrase", L(lang, "Пояснение", "Түсініктеме"))]
    return {"stock_trust": {"rows": rows, "head": head, "thresholds": thr, "year": y, "y0": years[0]},
            "columns": cols, "rows": flat, "default_view": "stock_trust", "chart": None, "row_action": "species",
            "notes": [L(lang, "Возрасты 1–2 и старше. Модель — медиана и 95 % интервал; по уловам — окончательный запас (сеть и невод); "
                              "доля вылова — по медианам составляющих убыли.",
                        "1–2 және үлкен жастар. Модель — медиана және 95 % аралық; ауланым бойынша — түпкілікті қор (ау мен сүзекі); "
                        "аулау үлесі — кему құрамдастарының медианалары бойынша.")],
            "meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "stock-trust", "filter_label": str(y)}


VIEWS["st_trust"] = v_st_trust


# ------------------------------------------------------------------ В. Поколения (модель)
def v_by_cohorts(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    ages = R["model_ages"]
    X = R["X_q"][2]                                  # [год][возраст], медиана
    m0 = (R.get("meta") or {}).get("m0") or _m0(D, R)
    rec = [_r(X[i][0]) for i in range(len(years))]
    pos = sorted(v for v in rec if v)
    med_rec = st_.median(pos) if pos else None
    # медиана численности каждого возраста по годам — «обычная» численность возраста
    med_age = []
    for k in range(len(ages)):
        vals = sorted(_r(X[i][k]) for i in range(len(years)) if X[i][k])
        med_age.append(st_.median(vals) if vals else None)
    sel = y                                          # поколение, рождённое в выбранном году
    best_i = max(range(len(rec)), key=lambda i: rec[i] or 0)
    cells = []
    for i, yy in enumerate(years):
        for k, j in enumerate(ages):
            v = _r(X[i][k])
            if v is None or not med_age[k]:
                continue
            x = v / med_age[k]
            born = yy - (j - 1)
            tip = L(lang, f"поколение {born} г.; численность {pieces(v)}, обычно (медиана возраста) {pieces(med_age[k])}",
                    f"{born} ж. ұрпағы; саны {pieces(v, 'kk')}, әдетте (жас медианасы) {pieces(med_age[k], 'kk')}")
            lab = "×" + nf(x, 1 if x < 10 else 0)
            cells.append([k, i, max(-1, min(1, log10(x))), lab, tip, born == sel])
    rows = []
    for i, yy in enumerate(years):
        k_entry = yy + (m0 - 1) if m0 else None
        last_age_i = years[-1] - yy                  # индекс возраста этого поколения в последнем году
        now = _r(X[-1][last_age_i]) if 0 <= last_age_i < len(ages) else None
        rows.append({"year": yy, "recruits": rec[i], "x_med": round(rec[i] / med_rec, 2) if rec[i] and med_rec else None,
                     "now": now, "now_age": age_label(ages[last_age_i]) if 0 <= last_age_i < len(ages) else "—",
                     "entry": k_entry, "_current": yy == y})
    bx = rows[best_i]["x_med"]
    sx = next((r["x_med"] for r in rows if r["year"] == y), None)
    tiles = [
        {"label": L(lang, f"Поколение {y} г.", f"{y} ж. ұрпағы"), "value": pieces(rec[years.index(y)], lang),
         "hint": L(lang, f"сеголеток; {_x(sx)} медианы; в промысловые возрасты — {y + m0 - 1} г.",
                   f"шабақ; медианадан {_x(sx)}; кәсіптік жасқа — {y + m0 - 1} ж.") if m0 else None},
        {"label": L(lang, "Сильнейшее поколение", "Ең күшті ұрпақ"), "value": str(years[best_i]),
         "hint": L(lang, f"{pieces(rec[best_i])} сеголеток, {_x(bx)} медианы; в промысловые возрасты — {years[best_i] + m0 - 1} г.",
                   f"{pieces(rec[best_i], 'kk')} шабақ, медианадан {_x(bx)}; кәсіптік жасқа — {years[best_i] + m0 - 1} ж.") if m0 else None},
        {"label": L(lang, "Медиана пополнения", "Толықтыру медианасы"), "value": pieces(med_rec, lang),
         "hint": L(lang, f"сеголеток в год, {years[0]}–{years[-1]}", f"жылына шабақ, {years[0]}–{years[-1]}")},
    ]
    xs = [age_label(j) for j in ages]
    return {"chart": {"kind": "heatmap", "fmt": "ratio", "x": xs, "y": years, "cells": cells, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"),
                      "y_title": L(lang, "Год", "Жыл"), "value_title": L(lang, "К обычной для возраста", "Жасқа әдеттегіге"), "y_is_year": True, "selected_y": y},
            "tiles": tiles, "default_view": "chart",
            "columns": [col("year", L(lang, "Год рождения", "Туған жылы"), "integer"), col("recruits", L(lang, "Сеголеток", "Шабақ"), "integer"),
                        col("x_med", L(lang, "× медианы", "× медиана"), "number"), col("now", L(lang, f"Численность в {years[-1]}", f"{years[-1]} жылы саны"), "integer"),
                        col("now_age", L(lang, f"Возраст в {years[-1]}", f"{years[-1]} жылы жасы")),
                        col("entry", L(lang, "Вход в промысловые возрасты", "Кәсіптік жасқа кіру"), "integer")],
            "rows": rows, "row_action": "year",
            "notes": [L(lang, "Цвет и подпись клетки — во сколько раз численность возраста в этом году больше (оранжевое) или меньше (синее) "
                              "обычной для возраста (медиана по годам); численность — в подсказке. Диагональ вверх и вправо — одно поколение; рамкой выделено поколение выбранного года. Вход в промысловые возрасты = "
                              "год рождения + m0 − 1.",
                        "Ұяшық түсі мен жазуы — жастың осы жылғы саны жасқа әдеттегіден (жылдар медианасы) неше есе көп (қызғылт сары) немесе аз (көк); "
                        "сан — кеңесте. Жоғары және оңға диагональ — бір ұрпақ; таңдалған жыл ұрпағы жиекпен белгіленген. Кәсіптік жасқа кіру = туған жыл + m0 − 1.")],
            **_bcommon(D, meta, years, y, code, R)}


def _m0(D, R):
    try:
        pl, _ = _pdu(D)
        sp = pl["species"].get(R["species"]) or {}
        return sp.get("m0")
    except NoData:
        return None


VIEWS["by_cohorts"] = v_by_cohorts


# ------------------------------------------------------------------ Г. Структура запаса
def _structure(ages, row, m0):
    """Доля половозрелых (j ≥ m0) в численности 1–2+ и средний возраст половозрелых (середина интервала, вес — численность)."""
    tot = sum(v for j, v in zip(ages, row) if v and j >= 2)
    mat = [(j, v) for j, v in zip(ages, row) if v and j >= m0 and j >= 2]
    sm = sum(v for _, v in mat)
    share = sm / tot * 100 if tot else None
    mean = sum((j - 0.5) * v for j, v in mat) / sm if sm else None
    return share, mean


def v_by_structure(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    m0 = (R.get("meta") or {}).get("m0") or _m0(D, R)
    if not m0:
        raise NoData(L(lang, "Не задан возраст половозрелости m0", "Жыныстық жетілу жасы m0 берілмеген"))
    ages = R["model_ages"]
    X = R["X_q"][2]
    fba = (R.get("data") or {}).get("final_by_age") or []
    sm, am, sc, ac = [], [], [], []
    for i in range(len(years)):
        a, b = _structure(ages, [_r(v) for v in X[i]], m0)
        sm.append(a), am.append(b)
        row = fba[i] if i < len(fba) else None
        if row:
            c_, d_ = _structure(list(range(2, 2 + len(row))), [_r(v) for v in row], m0)
        else:
            c_, d_ = None, None
        sc.append(c_), ac.append(d_)
    all_mature = m0 <= 2
    yi = years.index(y)
    rows = [{"year": yy, "share_m": None if sm[i] is None else round(sm[i], 1), "share_c": None if sc[i] is None else round(sc[i], 1),
             "age_m": None if am[i] is None else round(am[i], 2), "age_c": None if ac[i] is None else round(ac[i], 2), "_current": yy == y}
            for i, yy in enumerate(years)]
    tiles = []
    if not all_mature:
        tiles.append({"label": L(lang, "Доля половозрелых, модель", "Жыныстық жетілгендер үлесі, модель"),
                      "value": f"{nf(sm[yi], 0)} %", "hint": L(lang, f"{years[0]}: {nf(sm[0], 0)} %", f"{years[0]}: {nf(sm[0], 0)} %")})
        tiles.append({"label": L(lang, "Доля половозрелых, по уловам", "Жыныстық жетілгендер үлесі, ауланым"),
                      "value": f"{nf(sc[yi], 0)} %" if sc[yi] is not None else "—",
                      "hint": L(lang, f"{years[0]}: {nf(sc[0], 0)} %", f"{years[0]}: {nf(sc[0], 0)} %") if sc[0] is not None else None})
    tiles.append({"label": L(lang, "Средний возраст половозрелых, модель", "Жетілгендердің орташа жасы, модель"),
                  "value": L(lang, f"{nf(am[yi], 1)} года", f"{nf(am[yi], 1)} жыл"),
                  "hint": L(lang, f"{years[0]}: {nf(am[0], 1)}", f"{years[0]}: {nf(am[0], 1)}")})
    tiles.append({"label": L(lang, "Средний возраст половозрелых, по уловам", "Жетілгендердің орташа жасы, ауланым"),
                  "value": L(lang, f"{nf(ac[yi], 1)} года", f"{nf(ac[yi], 1)} жыл") if ac[yi] is not None else "—",
                  "hint": L(lang, f"{years[0]}: {nf(ac[0], 1)}", f"{years[0]}: {nf(ac[0], 1)}") if ac[0] is not None else None})
    if all_mature:
        lines = [{"name": L(lang, "Средний возраст половозрелых, модель", "Жетілгендердің орташа жасы, модель"), "values": am, "c": 0, "bold": True},
                 {"name": L(lang, "Средний возраст половозрелых, по уловам", "Жетілгендердің орташа жасы, ауланым"), "values": ac, "c": 1}]
        y_title, y_max = L(lang, "лет", "жыл"), None
    else:
        lines = [{"name": L(lang, "Доля половозрелых, модель", "Жыныстық жетілгендер үлесі, модель"), "values": sm, "c": 0, "bold": True},
                 {"name": L(lang, "Доля половозрелых, по уловам", "Жыныстық жетілгендер үлесі, ауланым"), "values": sc, "c": 1}]
        y_title, y_max = "%", 100
    note = L(lang, f"Половозрелые — возрасты с {age_label(m0)} (m0). Доля — в численности возрастов 1–2 и старше; средний возраст — середина "
                   "интервала возраста (например, 4–5 лет → 4,5), взвешенная по численности. Описательная статистика, не расчёт методики.",
             f"Жыныстық жетілгендер — {age_label(m0)} бастап жастар (m0). Үлес — 1–2 және үлкен жастар санында; орташа жас — жас аралығының "
             "ортасы (мысалы, 4–5 жыл → 4,5), санмен өлшенген. Сипаттамалық статистика, әдістеме есебі емес.")
    if all_mature:
        note = L(lang, "Все учитываемые возрасты половозрелые (m0 — первый возраст), поэтому показан только средний возраст. ",
                 "Барлық есепке алынатын жастар жетілген (m0 — бірінші жас), сондықтан тек орташа жас көрсетілген. ") + note
    return {"chart": {"kind": "band", "x": years, "bands": [], "lines": lines, "points": [], "vrefs": [{"x": str(y), "label": str(y)}],
                      "pick_year": True, "x_title": L(lang, "Год", "Жыл"), "y_title": y_title, "y_max": y_max, "allowed": ["linear"], "default": "linear"},
            "tiles": tiles,
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("share_m", L(lang, "Доля половозрелых, модель, %", "Жетілгендер үлесі, модель, %"), "number"),
                        col("share_c", L(lang, "по уловам, %", "ауланым, %"), "number"), col("age_m", L(lang, "Средний возраст, модель", "Орташа жас, модель"), "number"),
                        col("age_c", L(lang, "по уловам", "ауланым"), "number")],
            "rows": rows, "row_action": "year", "notes": [note], **_bcommon(D, meta, years, y, code, R)}


VIEWS["by_structure"] = v_by_structure


# ------------------------------------------------------------------ Д. Запас в тоннах
def v_st_biomass(D, opt):
    pl, meta = _pdu(D)
    lang = D.lang
    code = opt.get("species")
    if not code:
        raise NoData(L(lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, {"fits": pl["species"]}, code)
    if key is None:
        raise NoData(L(lang, f"Вид «{D.sp_name(code)}» не входит в расчёт ПДУ НПЦ этого водоёма",
                       f"«{D.sp_name(code)}» түрі осы су айдынының ҒӨО ШРА есебіне кірмейді"))
    sp = pl["species"][key]
    years = [int(v) for v in pl["years"]]
    y, _ = _year({"years": years}, opt)
    yi = years.index(y)
    bio = [_r(v) for v in sp["biomass_t"]]
    quota = [_r(v) for v in sp["pdu_t"]]
    model = None
    try:
        fpl, _ = _fc(D)
        fk = _key_for(D, {"fits": fpl["species"]}, code)
        h = (fpl["species"].get(fk) or {}).get("hist") if fk else None
        if h and h.get("fishable_q"):
            fy = list(fpl["species"][fk].get("years_hist") or [])
            q = h["fishable_q"]
            model = [[_r(q[k][fy.index(yy)]) if yy in fy else None for yy in years] for k in range(5)]
    except NoData:
        model = None
    bands, lines, points = [], [], []
    if model:
        bands = _bands(model, L(lang, "Модель: 95 %", "Модель: 95 %"))
        lines.append({"name": L(lang, "Промысловая биомасса, модель (медиана)", "Кәсіптік биомасса, модель (медиана)"), "values": model[2], "c": 0, "bold": True})
    lines.append({"name": L(lang, "Промысловая биомасса по уловам", "Ауланым бойынша кәсіптік биомасса"), "values": bio, "c": 1, "bold": not model})
    points.append({"name": L(lang, "ПДУ НПЦ", "ҒӨО ШРА"), "values": quota, "c": 3, "symbol": "diamond"})
    share = [round(q / b * 100, 1) if (q is not None and b) else None for q, b in zip(quota, bio)]
    rows = [{"year": yy, "bio": bio[i], "model": model[2][i] if model else None, "lo": model[0][i] if model else None,
             "hi": model[4][i] if model else None, "quota": quota[i], "share": share[i], "_current": yy == y} for i, yy in enumerate(years)]
    ch = _ratio(bio[yi], bio[0]) if yi > 0 else None
    tiles = [{"label": L(lang, f"Биомасса по уловам, {y}", f"Ауланым бойынша биомасса, {y}"), "value": f"{nf(bio[yi], 0)} т",
              "hint": L(lang, f"{years[0]}: {nf(bio[0], 0)} т ({_x(ch)})", f"{years[0]}: {nf(bio[0], 0)} т ({_x(ch)})") if ch else None}]
    if model and model[2][yi] is not None:
        tiles.append({"label": L(lang, f"Биомасса по модели, {y}", f"Модель бойынша биомасса, {y}"), "value": f"{nf(model[2][yi], 0)} т",
                      "hint": f"95 %: {nf(model[0][yi], 0)} – {nf(model[4][yi], 0)} т"})
    tiles.append({"label": L(lang, f"ПДУ НПЦ, {y}", f"ҒӨО ШРА, {y}"), "value": f"{nf(quota[yi], 0)} т",
                  "hint": L(lang, f"{nf(share[yi], 1)} % биомассы по уловам", f"ауланым биомассасының {nf(share[yi], 1)} %-ы") if share[yi] is not None else None})
    cols = [col("year", L(lang, "Год", "Жыл"), "integer"), col("bio", L(lang, "Биомасса по уловам, т", "Ауланым биомассасы, т"), "number")]
    if model:
        cols += [col("model", L(lang, "Модель, медиана, т", "Модель, медиана, т"), "number"), col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number")]
    cols += [col("quota", L(lang, "ПДУ НПЦ, т", "ҒӨО ШРА, т"), "number"), col("share", L(lang, "ПДУ НПЦ ÷ биомасса, %", "ҒӨО ШРА ÷ биомасса, %"), "number")]
    m0 = sp.get("m0")
    notes = [L(lang, f"Промысловая биомасса — возрасты с {age_label(m0)} (m0) × средний вес, т: по уловам — из расчёта ПДУ НПЦ по возрастам; "
                     "по модели — из прогноза (история). Это те же числа, что во вкладке «ПДУ».",
               f"Кәсіптік биомасса — {age_label(m0)} бастап жастар (m0) × орташа салмақ, т: ауланым бойынша — жас бойынша ҒӨО ШРА есебінен; "
               "модель бойынша — болжамнан (тарих). Бұл «ШРА» қойындысындағы сандар.")]
    if not model:
        notes.append(L(lang, "Биомасса по модели появится после полного расчёта (этапы 1–5).", "Модель бойынша биомасса толық есептен кейін (1–5 кезеңдер) пайда болады."))
    return {"chart": {"kind": "band", "x": years, "bands": bands, "lines": lines, "points": points, "vrefs": [{"x": str(y), "label": str(y)}],
                      "pick_year": True, "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "тонн", "тонна"), "allowed": ["linear", "log"], "default": "linear"},
            "tiles": tiles, "columns": cols, "rows": rows, "row_action": "year", "notes": notes,
            "meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "method-pdu-age", "species_shown": code,
            "filter_label": f"{D.sp_name(code)} · {y}"}


VIEWS["st_biomass"] = v_st_biomass


# ------------------------------------------------------------------ Уловистость, идея 8: c по методике рядом с поправкой q модели
def v_ca_q(D, opt):
    """Два уже посчитанных числа рядом, без объединения: c невода и сети за год (этапы 1–2) и q модели (этап 4).
    Как толковать q вместе с c, решает математик (ТЗ catchability_trust.md, идея 8)."""
    from .calc_views import _payload
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    ages = R["model_ages"]
    q = R["q_bias_q"]
    n = min(len(ages), len(q[2]))
    frm = (R.get("config_used") or {}).get("likelihood_from") or 3
    cs, cn = {}, {}
    for g, out in (("seine", cs), ("net", cn)):
        try:
            part, _ = _payload(D, g)
        except NoData:
            continue
        key = _key_for(D, part, code)
        f = (part["fits"].get(key) or {}).get(str(y)) if key else None
        if f:
            out.update({int(j): c for j, c in zip(f["ages"], f["c"]) if c is not None})
    if not cs and not cn:
        raise NoData(L(lang, f"За {y} г. нет подгонок уловистости вида", f"{y} ж. түрдің аулағыштық сәйкестендірулері жоқ"))
    xs = [age_label(a) for a in ages[:n]]
    lines = []
    if cs:
        lines.append({"name": L(lang, "c невода (методика)", "сүзекі c (әдістеме)"), "values": [cs.get(a) for a in ages[:n]], "c": 1})
    if cn:
        lines.append({"name": L(lang, "c сети (методика)", "ау c (әдістеме)"), "values": [cn.get(a) for a in ages[:n]], "c": 2, "dash": True})
    rows = [{"age": xs[k], "c_s": cs.get(ages[k]), "c_n": cn.get(ages[k]), "q": q[2][k], "q_lo": q[0][k], "q_hi": q[4][k],
             "in_lik": ages[k] >= frm} for k in range(n)]
    for r in rows:
        r["in_lik"] = L(lang, "да", "иә") if r["in_lik"] else L(lang, "нет", "жоқ")
    return {"chart": {"kind": "band", "x": xs, "intervals": [{"name": L(lang, "q модели (95 %)", "модель q (95 %)"), "lo": q[0][:n],
                                                               "hi": q[4][:n], "mid": q[2][:n], "c": 0}],
                      "lines": lines, "hrefs": [{"y": 1, "label": "q = 1"}],
                      "vrefs": [{"x": age_label(frm), "label": L(lang, "q оценивается →", "q бағаланады →")}],
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "c и q", "c және q"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("c_s", L(lang, f"c невода, {y}", f"сүзекі c, {y}"), "number"),
                        col("c_n", L(lang, f"c сети, {y}", f"ау c, {y}"), "number"), col("q", L(lang, "q модели, медиана", "модель q, медиана"), "number"),
                        col("q_lo", "2,5 %", "number"), col("q_hi", "97,5 %", "number"),
                        col("in_lik", L(lang, "q оценивается по данным", "q деректермен бағаланады"))],
            "rows": rows,
            "notes": [L(lang, f"c — уловистость по методике за {y} г. (какая доля рыб возраста попадает в орудие). q — поправка модели: "
                              f"оценка по лову ≈ q · численность модели; q оценивается по данным с возраста {age_label(frm)}, для младших — по данным не оценивается. "
                              "Здесь числа только показаны рядом: как их объединять, решает математик.",
                        f"c — {y} ж. әдістеме бойынша аулағыштық (жас балығының қандай үлесі құралға түседі). q — модель түзетуі: "
                        f"аулау бағасы ≈ q · модель саны; q {age_label(frm)} жасынан деректермен бағаланады, кішілер үшін деректермен бағаланбайды. "
                        "Мұнда сандар тек қатар көрсетілген: оларды қалай біріктіру керектігін математик шешеді.")],
            "meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "catchability-trust", "species_shown": code,
            "filter_label": f"{D.sp_name(code)} · {y}"}


VIEWS["ca_q"] = v_ca_q
