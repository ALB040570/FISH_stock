"""
Представления результатов расчёта для мониторинга: уловистость невода и сети (этапы 1–2).

Повторяют страницы прежнего приложения (legacy/fish_stock_forecast: «Уловистость невода», «Уловистость сети»),
но разбиты на блоки-слайды: параметры года, улов по возрастам, коэффициент уловистости, таблица по возрастам,
тепловая карта «годы × возрасты», параметры по годам. Числа берутся из результата запуска (полезная нагрузка шага)
без пересчёта; формулы — в справке («Метод расчёта»).
"""
from __future__ import annotations

from .insights import NoData, col

ALG = {"seine": "seine_catchability", "net": "stock_by_catch"}


def L(lang, ru, kk):
    return kk if lang == "kk" else ru


def nf(v, d=2):
    """Число с запятой и неразрывными пробелами в тысячах (как в интерфейсе)."""
    if v is None:
        return "—"
    s = f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


def age_label(j):
    """Возраст j — рыбы от j−1 до j лет."""
    try:
        j = float(j)
    except (TypeError, ValueError):
        return "—"
    if abs(j - round(j)) < 1e-9:
        return f"{int(round(j)) - 1}–{int(round(j))}"
    return nf(j, 1)


# ------------------------------------------------------------------ данные запуска
def _payload(D, gear):
    pl, meta = D.run_payload(ALG[gear])
    if pl is None:
        if meta is None:
            raise NoData(L(D.lang, "Для водоёма ещё нет расчёта уловистости — запустите расчёт в разделе «Расчёты»",
                           "Су айдыны үшін аулағыштық әлі есептелмеген — «Есептеулер» бөлімінде есептеуді іске қосыңыз"))
        raise NoData(L(D.lang, "В запуске нет результата этого шага", "Іске қосуда бұл қадамның нәтижесі жоқ"))
    part = pl.get("net") if gear == "net" else pl
    if not part or not part.get("fits"):
        raise NoData(L(D.lang, "В результате запуска нет параметров уловистости", "Іске қосу нәтижесінде аулағыштық параметрлері жоқ"))
    return part, meta


def _names(D):
    """{название вида в расчёте (рус., строчными): код справочника}."""
    out = {}
    for code, s in D.species.items():
        for n in (s.get("name_ru"), s.get("name_kk"), code):
            if n:
                out[str(n).strip().lower()] = code
    return out


def _key_for(D, part, code):
    names = _names(D)
    for k in part["fits"]:
        if names.get(k.strip().lower()) == code:
            return k
    return None


def _year(part, opt):
    years = [int(y) for y in part["years"]]
    y = opt.get("year")
    try:
        y = int(y) if y else None
    except (TypeError, ValueError):
        y = None
    return (y if y in years else years[-1]), years


def _species_fit(D, opt, gear):
    part, meta = _payload(D, gear)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, part, code)
    if key is None:
        raise NoData(L(D.lang, f"Вид «{D.sp_name(code)}» не входит в расчёт уловистости этого водоёма",
                       f"«{D.sp_name(code)}» түрі осы су айдынының аулағыштық есебіне кірмейді"))
    y, years = _year(part, opt)
    fit = part["fits"][key].get(str(y))
    if not fit:
        raise NoData(L(D.lang, f"Для {y} г. нет подгонки", f"{y} ж. үшін сәйкестендіру жоқ"))
    return part, meta, key, code, y, years, fit


def _common(D, meta, years, y, code, gear, help_id):
    gname = L(D.lang, "невод", "сүзекі") if gear == "seine" else L(D.lang, "сеть", "ау")
    return {"meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": help_id,
            "species_shown": code, "filter_label": f"{D.sp_name(code)} · {y} · {gname}" if code else f"{y} · {gname}"}


GEAR_HELP = {"seine": "method-seine", "net": "method-net"}


# ------------------------------------------------------------------ 1. все виды за год
def v_ca_species(D, opt, gear):
    part, meta = _payload(D, gear)
    y, years = _year(part, opt)
    names = _names(D)
    lang = D.lang
    rows = []
    for key, by in part["fits"].items():
        f = by.get(str(y))
        if not f:
            continue
        c = f.get("c") or [None]
        code = names.get(key.strip().lower(), key)
        r = {"_code": code, "species": D.sp_name(code), "n_sample": f.get("n_sample"), "total_catch": f.get("total_catch"),
             "status": f.get("status")}
        if gear == "seine":
            r.update({"j50": f.get("j50"), "j50_rule": age_label(f.get("j50_rule")), "a": f.get("a"), "c_first": c[0],
                      "c_last": c[-1], "Z": f.get("Z"), "r2": f.get("r2")})
        else:
            sig = f.get("sigma") or []
            ages = f.get("ages") or []
            ip = ages.index(f["peak"]) if f.get("peak") in ages else None
            r.update({"peak": age_label(f.get("peak")), "c0": f.get("c0"), "a1": f.get("a1"), "a2": f.get("a2"),
                      "c_first": c[0], "c_last": c[-1], "sigma_peak": sig[ip] if ip is not None and ip < len(sig) else None})
        rows.append(r)
    if not rows:
        raise NoData(L(lang, f"Для {y} г. нет подгонок", f"{y} ж. үшін сәйкестендірулер жоқ"))
    sp = col("species", L(lang, "Вид", "Түр"))
    tail = [col("n_sample", L(lang, "Рыб в пробе", "Сынамадағы балық"), "integer"),
            col("total_catch", L(lang, "Улов неводом, шт", "Сүзекімен ауланым, дана") if gear == "seine"
                else L(lang, "Улов сетью, шт", "Аумен ауланым, дана"), "integer"),
            col("status", L(lang, "Примечание", "Ескертпе"))]
    if gear == "seine":
        cols = [sp, col("j50", "j50 " + L(lang, "МНК", "ЕКӘ"), "number"), col("j50_rule", L(lang, "j50 по статье (возраст)", "Мақала бойынша j50 (жас)")),
                col("a", L(lang, "Крутизна a", "Тіктік a"), "number"), col("c_first", "c(1–2)", "number"),
                col("c_last", "c(m1)", "number"), col("Z", "Z", "number"), col("r2", "R²", "number")] + tail
    else:
        cols = [sp, col("peak", L(lang, "Вершина c¹ (возраст)", "Төбе c¹ (жас)")), col("c0", "c⁰", "number"),
                col("a1", "a1", "number"), col("a2", "a2", "number"), col("c_first", L(lang, "c первого возраста", "Бірінші жастың c"), "number"),
                col("c_last", "c(m1)", "number"), col("sigma_peak", L(lang, "σ в вершине", "Төбедегі σ"), "number")] + tail
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "species", "chart": None,
            "notes": [L(lang, "Щелчок по строке — все данные по виду.", "Жолды басу — түр бойынша барлық деректер.")],
            **_common(D, meta, years, y, None, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 2. параметры года (плитки и предупреждения)
def v_ca_tiles(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    c = f.get("c") or []
    data_tile = {"label": L(lang, "Данные года", "Жыл деректері"), "value": f"{nf(f.get('n_sample'), 0)} " + L(lang, "рыб", "балық"),
                 "hint": L(lang, f"в пробе; {'неводом' if gear == 'seine' else 'сетью'} {nf(f.get('total_catch'), 0)} шт за {f.get('n_hauls')} уловов",
                           f"сынамада; {'сүзекімен' if gear == 'seine' else 'аумен'} {nf(f.get('total_catch'), 0)} дана, {f.get('n_hauls')} аулау")}
    if gear == "seine":
        tiles = [
            {"label": L(lang, "Точка перегиба j50", "Иілу нүктесі j50"), "value": nf(f.get("j50"), 1),
             "hint": L(lang, f"номер возраста; по правилу статьи: {nf(f.get('j50_rule'), 0)} (возраст {age_label(f.get('j50_rule'))})",
                       f"жас нөмірі; мақала ережесі бойынша: {nf(f.get('j50_rule'), 0)} (жасы {age_label(f.get('j50_rule'))})")},
            {"label": L(lang, "Крутизна a", "Тіктік a"), "value": nf(f.get("a"), 2), "hint": L(lang, "1/год", "1/жыл")},
            {"label": L(lang, "Уловистость по возрастам", "Жастар бойынша аулағыштық"),
             "value": f"{nf(c[0], 2)} … {nf(c[-1], 2)}" if c else "—",
             "hint": L(lang, f"средняя {nf(f.get('c_mean'), 2)} (задана)", f"орташа {nf(f.get('c_mean'), 2)} (берілген)")},
            {"label": L(lang, "Общая смертность Z", "Жалпы өлім-жітім Z"), "value": nf(f.get("Z"), 2),
             "hint": L(lang, "из кривой улова, 1/год", "ауланым қисығынан, 1/жыл")},
            {"label": L(lang, "Качество подгонки R²", "Сәйкестендіру сапасы R²"), "value": nf(f.get("r2"), 2),
             "hint": L(lang, "в логарифмах, взвешенно", "логарифмдерде, салмақталған")},
            data_tile,
        ]
        warn = []
        if f.get("first_lower_active"):
            warn.append(L(lang, f"уловистость двухлеток (возраст 1–2) упёрлась в нижнюю границу {nf(part.get('c_lower_first'), 2)}",
                          f"екі жасарлардың (1–2 жас) аулағыштығы төменгі шекке {nf(part.get('c_lower_first'), 2)} тірелді"))
        if f.get("lower_active"):
            warn.append(L(lang, f"уловистость возраста 2–3 упёрлась в нижнюю границу {nf(part.get('c_lower'), 1)}",
                          f"2–3 жастың аулағыштығы төменгі шекке {nf(part.get('c_lower'), 1)} тірелді"))
        if f.get("first_lower_active") or f.get("lower_active"):
            warn.append(L(lang, "без ограничения МНК дал бы меньшее значение", "шектеусіз ЕКӘ кішірек мән берер еді"))
        if f.get("upper_active"):
            warn.append(L(lang, f"уловистость в {f.get('m1')} лет упёрлась в верхнюю границу {nf(part.get('c_upper'), 1)}",
                          f"{f.get('m1')} жастағы аулағыштық жоғарғы шекке {nf(part.get('c_upper'), 1)} тірелді"))
        if not f.get("observed_is_catch"):
            warn.append(L(lang, f"данные: {f.get('source')}", f"деректер: {f.get('source')}"))
        if "ступенька" in str(f.get("status") or ""):
            warn.append(L(lang, "сигмоида почти ступенька (a на верхней границе)", "сигмоида сатыға жақын (a жоғарғы шекте)"))
    else:
        ages = f.get("ages") or []
        sig = f.get("sigma") or []
        ip = ages.index(f["peak"]) if f.get("peak") in ages else None
        tiles = [
            {"label": L(lang, "Вершина параболы c¹", "Парабола төбесі c¹"), "value": L(lang, "возраст ", "жасы ") + age_label(f.get("peak")),
             "hint": L(lang, f"номер возраста j = {nf(f.get('peak'), 0)}", f"жас нөмірі j = {nf(f.get('peak'), 0)}")},
            {"label": L(lang, "Уловистость в вершине c⁰", "Төбедегі аулағыштық c⁰"), "value": nf(f.get("c0"), 3),
             "hint": L(lang, f"средняя {nf(f.get('c_mean'), 2)} (задана)", f"орташа {nf(f.get('c_mean'), 2)} (берілген)")},
            {"label": L(lang, "Уловистость по возрастам", "Жастар бойынша аулағыштық"),
             "value": f"{nf(min(c), 2)} – {nf(max(c), 2)}" if c else "—",
             "hint": f"c({age_label(ages[0])}) = {nf(c[0], 2)}, c({age_label(f.get('m1'))}) = {nf(c[-1], 2)}" if c and ages else None},
            {"label": L(lang, "Ветви a1 / a2", "Тармақтар a1 / a2"), "value": f"{nf(f.get('a1'), 3)} / {nf(f.get('a2'), 3)}",
             "hint": L(lang, "левая / правая", "сол / оң")},
            {"label": L(lang, "Доля в сети σ (вершина)", "Аудағы үлес σ (төбе)"), "value": nf(sig[ip], 3) if ip is not None and ip < len(sig) else "—",
             "hint": L(lang, f"{nf(f.get('hours'), 0)} ч, сеть {nf(f.get('net_length'), 0)} м, {nf(f.get('speed'), 0)} м/ч",
                       f"{nf(f.get('hours'), 0)} сағ, ау {nf(f.get('net_length'), 0)} м, {nf(f.get('speed'), 0)} м/сағ")},
            data_tile,
        ]
        warn = [str(f["status"])] if f.get("status") and f.get("status") != "ок" else []
    signals = []
    if warn:
        signals.append({"level": "warning", "text": L(lang, "Обратите внимание: ", "Назар аударыңыз: ") + "; ".join(warn) + "."})
    return {"tiles": tiles, "warnings": signals, "default_view": "tiles", "chart": None,
            "columns": [col("label", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні")), col("hint", L(lang, "Пояснение", "Түсініктеме"))],
            "rows": [{"label": t["label"], "value": t["value"], "hint": t.get("hint")} for t in tiles],
            "notes": [], "fit": f, **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 3. улов по возрастам
def v_ca_catch(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    ages = f.get("ages") or []
    is_catch = f.get("observed_is_catch")
    obs = L(lang, "Факт: улов, шт", "Нақты: ауланым, дана") if is_catch else L(lang, "Факт: доля в пробе", "Нақты: сынамадағы үлес")
    series = [{"name": obs, "values": f.get("observed"), "type": "bar"}]
    if gear == "seine" and f.get("fitted"):
        series.append({"name": L(lang, "МНК-модель", "ЕКӘ-модель"), "values": f.get("fitted"), "type": "line"})
    vrefs = []
    if gear == "net" and f.get("peak") in ages:
        vrefs.append({"x": age_label(f["peak"]), "label": L(lang, "вершина ", "төбе ") + age_label(f["peak"])})
    rows = [{"age": age_label(a), "observed": o, **({"fitted": fi} if gear == "seine" else {})}
            for a, o, fi in zip(ages, f.get("observed") or [], f.get("fitted") or [None] * len(ages))]
    cols = [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("observed", obs, "number")]
    if gear == "seine":
        cols.append(col("fitted", L(lang, "Модель", "Модель"), "number"))
    sub = (L(lang, "Модель: c·N0·exp(−Z·j); в логарифмической шкале кривая улова почти прямая справа от перегиба.",
             "Модель: c·N0·exp(−Z·j); логарифмдік шкалада ауланым қисығы иілуден оңға қарай түзу дерлік.")
           if gear == "seine" else L(lang, "Вертикальная линия — вершина параболы c¹.", "Тік сызық — парабола төбесі c¹."))
    return {"chart": {"kind": "fit", "x": [age_label(a) for a in ages], "series": series, "vrefs": vrefs,
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "штук", "дана") if is_catch else L(lang, "доля", "үлес"),
                      "allowed": ["linear", "log"], "default": "linear"},
            "columns": cols, "rows": rows, "notes": [sub], **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 4. коэффициент уловистости
def v_ca_curve(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    ages = f.get("ages") or []
    lo, hi = part.get("c_lower"), part.get("c_upper")
    hrefs = [{"y": lo, "label": L(lang, f"мин {nf(lo, 1)}" + (" (с возраста 2–3)" if gear == "seine" else ""),
                                  f"мин {nf(lo, 1)}" + (" (2–3 жастан)" if gear == "seine" else ""))},
             {"y": hi, "label": L(lang, f"макс {nf(hi, 1)}", f"макс {nf(hi, 1)}")}]
    vrefs = []
    if gear == "seine":
        vrefs.append({"x": f.get("j50"), "label": f"j50 = {nf(f.get('j50'), 1)}", "num": True})
        if f.get("j50_rule") is not None and f.get("j50") is not None and abs(f["j50_rule"] - f["j50"]) > 0.05:
            vrefs.append({"x": f.get("j50_rule"), "label": L(lang, "по статье: ", "мақала бойынша: ") + age_label(f["j50_rule"]), "num": True, "dash": True})
        name = L(lang, "МНК (сигмоида)", "ЕКӘ (сигмоида)")
    else:
        vrefs.append({"x": f.get("peak"), "label": L(lang, "вершина ", "төбе ") + age_label(f.get("peak")), "num": True})
        name = L(lang, "Парабола (22)–(24)", "Парабола (22)–(24)")
    series = [{"name": name, "values": f.get("c")}]
    old = f.get("c_old")
    if isinstance(old, list) and any(v is not None for v in old):
        series.append({"name": L(lang, "Прежний расчёт", "Бұрынғы есеп"), "values": old, "dash": True})
    rows = [{"age": age_label(a), "c": cv} for a, cv in zip(ages, f.get("c") or [])]
    return {"chart": {"kind": "curve", "x": [age_label(a) for a in ages], "x_num": ages, "series": series, "hrefs": hrefs, "vrefs": vrefs,
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "коэффициент", "коэффициент"), "y_max": 0.9},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("c", "c", "number")], "rows": rows,
            "notes": [L(lang, "Прежние коэффициенты (байес) не загружены — показывается только новый расчёт.",
                        "Бұрынғы коэффициенттер жүктелмеген — тек жаңа есеп көрсетіледі.")] if len(series) == 1 else [],
            **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 5. таблица по возрастам
def v_ca_ages(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    ages = f.get("ages") or []
    n = len(ages)
    get = lambda k: (f.get(k) or [None] * n) + [None] * max(0, n - len(f.get(k) or []))  # noqa: E731
    is_catch = f.get("observed_is_catch")
    old = f.get("c_old") if isinstance(f.get("c_old"), list) and any(v is not None for v in f.get("c_old")) else None
    rows = []
    for i, a in enumerate(ages):
        r = {"age": age_label(a), "observed": get("observed")[i], "c": get("c")[i]}
        if gear == "seine":
            r.update({"fitted": get("fitted")[i], "weight": get("weights")[i]})
        else:
            r["sigma"] = get("sigma")[i]
        if old:
            r["c_old"] = old[i] if i < len(old) else None
        rows.append(r)
    obs = (L(lang, "Улов факт, шт", "Нақты ауланым, дана") if is_catch else L(lang, "Доля в пробе", "Сынамадағы үлес"))
    cols = [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("observed", obs, "number")]
    if gear == "seine":
        cols += [col("fitted", L(lang, "Улов модель", "Модель ауланымы"), "number"), col("weight", L(lang, "Вес МНК", "ЕКӘ салмағы"), "number"),
                 col("c", "c " + L(lang, "МНК", "ЕКӘ"), "number")]
    else:
        cols += [col("c", L(lang, "c парабола", "c парабола"), "number"), col("sigma", L(lang, "σ (доля в сети)", "σ (аудағы үлес)"), "number")]
    if old:
        cols.append(col("c_old", L(lang, "c прежний", "c бұрынғы"), "number"))
    return {"columns": cols, "rows": rows, "default_view": "table", "chart": None,
            "notes": [L(lang, "Колонка «c прежний» появляется, только если прежние коэффициенты загружены.",
                        "«c бұрынғы» бағаны бұрынғы коэффициенттер жүктелгенде ғана шығады.")] if not old else [],
            **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 6. тепловая карта годы × возрасты
def v_ca_heat(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    by = part["fits"][key]
    ages = sorted({a for yy in years for a in (by.get(str(yy)) or {}).get("ages", [])})
    cells, rows = [], []
    for i, yy in enumerate(years):
        fy = by.get(str(yy)) or {}
        cmap = dict(zip(fy.get("ages") or [], fy.get("c") or []))
        row = {"year": yy, "_current": yy == y}
        for j, a in enumerate(ages):
            v = cmap.get(a)
            row[f"a{a}"] = v
            if v is not None:
                cells.append([j, i, round(v, 3)])
        rows.append(row)
    return {"chart": {"kind": "heatmap", "x": [age_label(a) for a in ages], "y": years, "cells": cells,
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "Год", "Жыл"), "value_title": "c",
                      "fmt": "coef", "y_is_year": True, "pick_year": True, "selected_y": y, "max": part.get("c_upper")},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer")] + [col(f"a{a}", age_label(a), "number") for a in ages],
            "rows": rows, "row_action": "year",
            "notes": [L(lang, "Каждая строка — отдельная кривая года. Щелчок по строке выбирает год.",
                        "Әр жол — жылдың жеке қисығы. Жолды басу жылды таңдайды.")],
            **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


# ------------------------------------------------------------------ 7. параметры по годам
def v_ca_params(D, opt, gear):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    by = part["fits"][key]
    rows = []
    for yy in years:
        d = by.get(str(yy))
        if not d:
            continue
        c = d.get("c") or [None]
        r = {"year": yy, "_current": yy == y, "n_sample": d.get("n_sample"), "total_catch": d.get("total_catch"), "status": d.get("status")}
        if gear == "seine":
            r.update({"a": d.get("a"), "j50": d.get("j50"), "j50_rule": d.get("j50_rule"), "Z": d.get("Z"), "b": d.get("b"),
                      "c_first": c[0], "c_last": c[-1], "r2": d.get("r2")})
        else:
            r.update({"peak": age_label(d.get("peak")), "c0": d.get("c0"), "a1": d.get("a1"), "a2": d.get("a2"),
                      "c_first": c[0], "c_last": c[-1], "n_hauls": d.get("n_hauls")})
        rows.append(r)
    yr = col("year", L(lang, "Год", "Жыл"), "integer")
    tail = [col("n_sample", L(lang, "Рыб в пробе", "Сынамадағы балық"), "integer"),
            col("total_catch", L(lang, "Улов неводом, шт", "Сүзекімен ауланым, дана") if gear == "seine" else L(lang, "Улов сетью, шт", "Аумен ауланым, дана"), "integer")]
    if gear == "seine":
        cols = [yr, col("a", "a", "number"), col("j50", "j50 " + L(lang, "МНК", "ЕКӘ"), "number"), col("j50_rule", L(lang, "j50 статья", "j50 мақала"), "integer"),
                col("Z", "Z", "number"), col("b", "b", "number"), col("c_first", "c(2)", "number"), col("c_last", "c(m1)", "number"),
                col("r2", "R²", "number")] + tail
    else:
        cols = [yr, col("peak", L(lang, "Вершина (возраст)", "Төбе (жас)")), col("c0", "c⁰", "number"), col("a1", "a1", "number"),
                col("a2", "a2", "number"), col("c_first", L(lang, "c первого возраста", "Бірінші жастың c"), "number"),
                col("c_last", "c(m1)", "number")] + tail + [col("n_hauls", L(lang, "Уловов", "Аулаулар"), "integer")]
    cols.append(col("status", L(lang, "Примечание", "Ескертпе")))
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "year", "chart": None,
            "notes": [L(lang, "Строка выбранного года выделена. Щелчок по строке выбирает год.",
                        "Таңдалған жыл жолы белгіленген. Жолды басу жылды таңдайды.")],
            **_common(D, meta, years, y, code, gear, GEAR_HELP[gear])}


def _bind(fn, gear):
    def view(D, opt):
        return fn(D, opt, gear)
    view.__name__ = f"{fn.__name__}_{gear}"
    return view


VIEWS = {}
for _g in ("seine", "net"):
    for _n, _fn in (("species", v_ca_species), ("tiles", v_ca_tiles), ("catch", v_ca_catch), ("curve", v_ca_curve),
                    ("ages", v_ca_ages), ("heat", v_ca_heat), ("params", v_ca_params)):
        VIEWS[f"ca_{_g}_{_n}"] = _bind(_fn, _g)


# ================================================================== Запас по уловам (этап 2)
def pieces(v, lang="ru"):
    """Штуки компактно: 1,2 млн / 350 тыс / 820."""
    if v is None:
        return "—"
    a = abs(v)
    th = "мың" if lang == "kk" else "тыс"
    if a >= 1e9:
        return f"{nf(v / 1e9, 0 if a >= 1e10 else 1)} млрд"
    if a >= 1e6:
        return f"{nf(v / 1e6, 0 if a >= 1e8 else 1 if a >= 1e7 else 2)} млн"
    if a >= 1e3:
        return f"{nf(v / 1e3, 0 if a >= 1e5 else 1)} {th}"
    return nf(v, 0)


def _stock(D):
    pl, meta = D.run_payload("stock_by_catch")
    if pl is None or not (pl.get("stock") or {}).get("species"):
        if meta is None:
            raise NoData(L(D.lang, "Для водоёма ещё нет расчёта запаса по уловам — запустите расчёт в разделе «Расчёты»",
                           "Су айдыны үшін ауланым бойынша қор әлі есептелмеген — «Есептеулер» бөлімінде есептеуді іске қосыңыз"))
        raise NoData(L(D.lang, "В запуске нет результата расчёта запаса", "Іске қосуда қор есебінің нәтижесі жоқ"))
    return pl["stock"], meta


def _toggles(D, opt, hauls_only=False):
    lang = D.lang
    variant = opt.get("variant") if opt.get("variant") in ("with_ages", "out_ages") else "with_ages"
    method = opt.get("method") if opt.get("method") in ("on_stock", "on_catch") else "on_stock"
    t = [{"key": "variant", "title": L(lang, "Уловистость", "Аулағыштық"), "value": variant,
          "options": [{"value": "with_ages", "label": L(lang, "по возрастам", "жастар бойынша")},
                      {"value": "out_ages", "label": L(lang, "средняя по виду", "түр бойынша орташа")}]}]
    if not hauls_only:
        t.append({"key": "method", "title": L(lang, "Годовой запас", "Жылдық қор"), "value": method,
                  "options": [{"value": "on_stock", "label": L(lang, "по запасам", "қорлар бойынша")},
                              {"value": "on_catch", "label": L(lang, "по улову", "ауланым бойынша")}]})
    return variant, method, t


def _stock_species(D, opt):
    st, meta = _stock(D)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, {"fits": st["species"]}, code)
    if key is None:
        raise NoData(L(D.lang, f"Вид «{D.sp_name(code)}» не входит в расчёт запаса этого водоёма",
                       f"«{D.sp_name(code)}» түрі осы су айдынының қор есебіне кірмейді"))
    y, years = _year(st, opt)
    return st, meta, st["species"][key], code, y, years


def _stock_common(D, meta, years, y, code, variant=None, method=None, st=None):
    lang = D.lang
    parts = [D.sp_name(code) if code else None, str(y)]
    if st and variant:
        parts.append(L(lang, "уловистость по возрастам", "жастар бойынша аулағыштық") if variant == "with_ages"
                     else L(lang, "уловистость средняя по виду", "түр бойынша орташа аулағыштық"))
    if st and method:
        parts.append(L(lang, "по запасам", "қорлар бойынша") if method == "on_stock" else L(lang, "по улову", "ауланым бойынша"))
    return {"meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "method-stock",
            "species_shown": code, "filter_label": " · ".join(p for p in parts if p)}


def _gear_names(lang):
    return {"net": L(lang, "Сети (балансовый)", "Аулар (баланс әдісі)"), "seine": L(lang, "Невод (27)", "Сүзекі (27)"),
            "mean": L(lang, "Сети и невод (окончательный)", "Аулар мен сүзекі (түпкілікті)"), "npc": L(lang, "НПЦ", "ҒӨО")}


def v_st_species(D, opt):
    st, meta = _stock(D)
    y, years = _year(st, opt)
    variant, method, toggles = _toggles(D, opt)
    G = st["gears"]
    yi = years.index(y)
    names = _names(D)
    lang = D.lang
    rows = []
    for key, sp in st["species"].items():
        mb = sp["variants"][variant][method]["totals"]
        net, seine, mean = mb[G["net"]][yi], mb[G["seine"]][yi], mb[G["mean"]][yi]
        npc = (sp.get("npc") or [None] * len(years))[yi]
        code = names.get(key.strip().lower(), key)
        rows.append({"_code": code, "species": D.sp_name(code), "net": net, "seine": seine, "mean": mean, "npc": npc,
                     "ratio": (seine / net) if net and seine else None,
                     "n_net": sp["n_hauls"][G["net"]][yi], "n_seine": sp["n_hauls"][G["seine"]][yi]})
    rows.sort(key=lambda r: -(r["mean"] or 0))
    gn = _gear_names(lang)
    cols = [col("species", L(lang, "Вид", "Түр")), col("net", gn["net"], "integer"), col("seine", gn["seine"], "integer"),
            col("mean", L(lang, "Окончательный", "Түпкілікті"), "integer"), col("npc", L(lang, "Оценка НПЦ", "ҒӨО бағасы"), "integer"),
            col("ratio", L(lang, "Невод / сети, раз", "Сүзекі / аулар, есе"), "number"),
            col("n_net", L(lang, "Ловов сетью", "Аумен аулау"), "integer"), col("n_seine", L(lang, "Ловов неводом", "Сүзекімен аулау"), "integer")]
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "species", "chart": None, "toggles": toggles,
            "notes": [L(lang, "Штук рыб, возрасты от 1–2 до m1. Каждый вид — отдельно; суммировать виды нельзя. Щелчок по строке — все данные по виду.",
                        "Балық дана, 1–2-ден m1-ге дейінгі жастар. Әр түр бөлек; түрлерді қосуға болмайды. Жолды басу — түр бойынша барлық деректер.")],
            **_stock_common(D, meta, years, y, None, variant, method, st)}


def v_st_tiles(D, opt):
    st, meta, sp, code, y, years = _stock_species(D, opt)
    variant, method, toggles = _toggles(D, opt)
    G = st["gears"]
    yi = years.index(y)
    lang = D.lang
    mb = sp["variants"][variant][method]["totals"]
    net, seine, mean = mb[G["net"]][yi], mb[G["seine"]][yi], mb[G["mean"]][yi]
    npc = (sp.get("npc") or [None] * len(years))[yi]
    ratio = seine / net if net and seine else None
    how = L(lang, "средневзвешенное по числу ловов", "аулау саны бойынша орташа салмақталған") if st.get("combine_how") == "hauls" \
        else L(lang, "среднее (29)", "орташа (29)")
    tiles = [
        {"label": L(lang, f"Сети, {y}", f"Аулар, {y}"), "value": pieces(net, lang),
         "hint": L(lang, "балансовый метод (как в старом коде)", "баланс әдісі (ескі кодтағыдай)") if st.get("net_formula") != "article"
         else L(lang, "балансовый метод, формула (28)", "баланс әдісі, (28) формула")},
        {"label": L(lang, f"Невод, {y}", f"Сүзекі, {y}"), "value": pieces(seine, lang), "hint": L(lang, "метод площадей (27)", "аудандар әдісі (27)")},
        {"label": L(lang, "Окончательный запас", "Түпкілікті қор"), "value": pieces(mean, lang), "hint": L(lang, f"сети и невод: {how}", f"аулар мен сүзекі: {how}")},
        {"label": L(lang, "Оценка НПЦ", "ҒӨО бағасы"), "value": pieces(npc, lang), "hint": L(lang, "из набора «Оценка запаса НПЦ»", "«ҒӨО қор бағасы» жиынтығынан")},
        {"label": L(lang, "Невод / сети", "Сүзекі / аулар"), "value": f"{nf(ratio, 1)}×" if ratio else "—", "hint": L(lang, "во сколько раз больше", "неше есе көп")},
        {"label": L(lang, "Ловов за год", "Жылдағы аулау"), "value": f"{nf(sp['n_hauls'][G['net']][yi], 0)} / {nf(sp['n_hauls'][G['seine']][yi], 0)}",
         "hint": L(lang, "сетью / неводом", "аумен / сүзекімен")},
    ]
    return {"tiles": tiles, "default_view": "tiles", "chart": None, "toggles": toggles,
            "columns": [col("label", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні")), col("hint", L(lang, "Пояснение", "Түсініктеме"))],
            "rows": [{"label": t["label"], "value": t["value"], "hint": t["hint"]} for t in tiles],
            "values": {"net": net, "seine": seine, "mean": mean, "npc": npc, "ratio": ratio},
            **_stock_common(D, meta, years, y, code, variant, method, st)}


def v_st_yearly(D, opt):
    st, meta, sp, code, y, years = _stock_species(D, opt)
    variant, method, toggles = _toggles(D, opt)
    G = st["gears"]
    lang = D.lang
    mb = sp["variants"][variant][method]["totals"]
    gn = _gear_names(lang)
    series = [{"name": gn["net"], "values": mb[G["net"]], "type": "line", "c": 0},
              {"name": gn["seine"], "values": mb[G["seine"]], "type": "line", "c": 1},
              {"name": gn["mean"], "values": mb[G["mean"]], "type": "line", "c": 2, "bold": True}]
    if sp.get("npc"):
        series.append({"name": gn["npc"], "values": sp["npc"], "type": "line", "c": 3, "dash": True})
    rows = [{"year": yy, "net": mb[G["net"]][i], "seine": mb[G["seine"]][i], "mean": mb[G["mean"]][i],
             "npc": (sp.get("npc") or [None] * len(years))[i], "_current": yy == y} for i, yy in enumerate(years)]
    return {"chart": {"kind": "fit", "x": years, "series": series, "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True,
                      "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("net", gn["net"], "integer"), col("seine", gn["seine"], "integer"),
                        col("mean", gn["mean"], "integer"), col("npc", gn["npc"], "integer")],
            "rows": rows, "toggles": toggles, "row_action": "year",
            "notes": [L(lang, "Штук рыб, все возрасты от 1–2 до m1 (без сеголеток). Вертикальная линия — выбранный год; щелчок по точке выбирает год.",
                        "Балық дана, 1–2-ден m1-ге дейінгі барлық жастар (шабақсыз). Тік сызық — таңдалған жыл; нүктені басу жылды таңдайды.")],
            **_stock_common(D, meta, years, y, code, variant, method, st)}


def v_st_hauls(D, opt):
    st, meta, sp, code, y, years = _stock_species(D, opt)
    variant, _, toggles = _toggles(D, opt, hauls_only=True)
    G = st["gears"]
    lang = D.lang
    vb = sp["variants"][variant]
    H = st["hauls"]
    gn = _gear_names(lang)
    dots, rows = [], []
    for k, g in enumerate(("net", "seine")):
        gk = G[g]
        pts = []
        for h, v in enumerate(vb["hauls"][gk]):
            yy = H[gk]["year"][h]
            if v is None or yy not in years:
                continue
            lab = f"{H[gk]['date'][h]}, {H[gk]['place'][h]} ({H[gk]['type'][h]})"
            pts.append([years.index(yy), v, lab])
            rows.append({"gear": L(lang, "сеть", "ау") if g == "net" else L(lang, "невод", "сүзекі"), "year": yy, "date": H[gk]["date"][h],
                         "place": H[gk]["place"][h], "type": H[gk]["type"][h], "stock": v})
        dots.append({"name": L(lang, "Сети, лов", "Аулар, аулау") if g == "net" else L(lang, "Невод, лов", "Сүзекі, аулау"), "points": pts, "c": k})
    lines = [{"name": L(lang, "Сети, год", "Аулар, жыл"), "values": vb["on_stock"]["totals"][G["net"]], "c": 0},
             {"name": L(lang, "Невод, год", "Сүзекі, жыл"), "values": vb["on_stock"]["totals"][G["seine"]], "c": 1}]
    return {"chart": {"kind": "dots", "x": years, "dots": dots, "lines": lines, "x_title": L(lang, "Год", "Жыл"),
                      "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("gear", L(lang, "Орудие", "Құрал")), col("year", L(lang, "Год", "Жыл"), "integer"), col("date", L(lang, "Дата", "Күні")),
                        col("place", L(lang, "Место лова", "Аулау орны")), col("type", L(lang, "Тип лова", "Аулау түрі")),
                        col("stock", L(lang, "Запас по лову, шт", "Аулау бойынша қор, дана"), "integer")],
            "rows": rows, "toggles": toggles,
            "notes": [L(lang, "Каждая точка — запас, оценённый по одному лову; линии — годовой запас по каждому орудию (среднее оценок по ловам).",
                        "Әр нүкте — бір аулау бойынша бағаланған қор; сызықтар — әр құрал бойынша жылдық қор (аулаулар бағаларының орташасы).")],
            **_stock_common(D, meta, years, y, code, variant, None, st)}


def v_st_ages(D, opt):
    st, meta, sp, code, y, years = _stock_species(D, opt)
    variant, method, toggles = _toggles(D, opt)
    G = st["gears"]
    yi = years.index(y)
    lang = D.lang
    ba = sp["variants"][variant][method]["by_age"]
    ages = sp["ages"]
    net, seine, mean = ba[G["net"]][yi], ba[G["seine"]][yi], ba[G["mean"]][yi]
    series = [{"name": L(lang, "Сети", "Аулар"), "values": net, "type": "bar", "c": 0},
              {"name": L(lang, "Невод", "Сүзекі"), "values": seine, "type": "bar", "c": 1},
              {"name": L(lang, "Окончательный (по нему распределяется ПДУ)", "Түпкілікті (ШРА осы бойынша бөлінеді)"), "values": mean, "type": "line", "c": 2, "bold": True}]
    rows = [{"age": age_label(a), "net": net[i], "seine": seine[i], "mean": mean[i]} for i, a in enumerate(ages)]
    return {"chart": {"kind": "fit", "x": [age_label(a) for a in ages], "series": series, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"),
                      "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("net", L(lang, "Сети", "Аулар"), "integer"),
                        col("seine", L(lang, "Невод", "Сүзекі"), "integer"), col("mean", L(lang, "Окончательный", "Түпкілікті"), "integer")],
            "rows": rows, "toggles": toggles,
            "notes": [L(lang, "Возрасты по порядку от 1–2 до m1; запас каждого вида — отдельно.", "Жастар 1–2-ден m1-ге дейін ретімен; әр түрдің қоры бөлек.")],
            **_stock_common(D, meta, years, y, code, variant, method, st)}


def v_st_table(D, opt):
    st, meta, sp, code, y, years = _stock_species(D, opt)
    variant, method, toggles = _toggles(D, opt)
    G = st["gears"]
    lang = D.lang
    mb = sp["variants"][variant][method]["totals"]
    npc = sp.get("npc") or [None] * len(years)
    rows = []
    for i, yy in enumerate(years):
        n, s_ = mb[G["net"]][i], mb[G["seine"]][i]
        rows.append({"year": yy, "_current": yy == y, "net": n, "seine": s_, "mean": mb[G["mean"]][i], "npc": npc[i],
                     "ratio": s_ / n if n and s_ else None, "n_net": sp["n_hauls"][G["net"]][i], "n_seine": sp["n_hauls"][G["seine"]][i]})
    gn = _gear_names(lang)
    cols = [col("year", L(lang, "Год", "Жыл"), "integer"), col("net", gn["net"], "integer"), col("seine", gn["seine"], "integer"),
            col("mean", L(lang, "Окончательный", "Түпкілікті"), "integer"), col("npc", gn["npc"], "integer"),
            col("ratio", L(lang, "Невод / сети, раз", "Сүзекі / аулар, есе"), "number"),
            col("n_net", L(lang, "Ловов сетью", "Аумен аулау"), "integer"), col("n_seine", L(lang, "Ловов неводом", "Сүзекімен аулау"), "integer")]
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "year", "chart": None, "toggles": toggles,
            "notes": [L(lang, "Штук рыб. Строка выбранного года выделена; щелчок по строке выбирает год.",
                        "Балық дана. Таңдалған жыл жолы белгіленген; жолды басу жылды таңдайды.")],
            **_stock_common(D, meta, years, y, code, variant, method, st)}


VIEWS.update({"st_species": v_st_species, "st_tiles": v_st_tiles, "st_yearly": v_st_yearly, "st_hauls": v_st_hauls,
              "st_ages": v_st_ages, "st_table": v_st_table})
