"""
Представления результатов расчёта для мониторинга: уловистость невода и сети (этапы 1–2).

Повторяют страницы прежнего приложения (legacy/fish_stock_forecast: «Уловистость невода», «Уловистость сети»),
но разбиты на блоки-слайды: параметры года, улов по возрастам, коэффициент уловистости, таблица по возрастам,
тепловая карта «годы × возрасты», параметры по годам. Числа берутся из результата запуска (полезная нагрузка шага)
без пересчёта; формулы — в справке («Метод расчёта»).
"""
from __future__ import annotations

import re

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


def clean_status(s):
    """Примечание расчёта для интерфейса: без номеров формул методики, десятичная запятая."""
    if not s:
        return s
    s = re.sub(r"нарушено\s*\(\d+\)\s*:", "нарушено ограничение:", str(s))
    s = re.sub(r"\s*\((?:\d{2})\)", "", s)
    return re.sub(r"(\d)\.(\d)", r"\1,\2", s)


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
             "status": clean_status(f.get("status"))}
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
        cols = [sp, col("j50", "j50 " + L(lang, "МНК", "ЕКӘ"), "number"), col("j50_rule", L(lang, "j50 по правилу (возраст)", "Ереже бойынша j50 (жас)")),
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
             "hint": L(lang, f"номер возраста; по правилу «m0 + 1 или возраст наибольшего улова»: {nf(f.get('j50_rule'), 0)} (возраст {age_label(f.get('j50_rule'))})",
                       f"жас нөмірі; «m0 + 1 немесе ең көп ауланым жасы» ережесі бойынша: {nf(f.get('j50_rule'), 0)} (жасы {age_label(f.get('j50_rule'))})")},
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
        warn = [clean_status(f["status"])] if f.get("status") and f.get("status") != "ок" else []
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
            vrefs.append({"x": f.get("j50_rule"), "label": L(lang, "по правилу: ", "ереже бойынша: ") + age_label(f["j50_rule"]), "num": True, "dash": True})
        name = L(lang, "МНК (сигмоида)", "ЕКӘ (сигмоида)")
    else:
        vrefs.append({"x": f.get("peak"), "label": L(lang, "вершина ", "төбе ") + age_label(f.get("peak")), "num": True})
        name = L(lang, "Парабола", "Парабола")
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
HMODES = ("c", "dev", "gears", "growth")


def _htoggle(lang, mode):
    return [{"key": "hmode", "title": L(lang, "Показать", "Көрсету"), "value": mode,
             "options": [{"value": "c", "label": L(lang, "уловистость", "аулағыштық")},
                         {"value": "dev", "label": L(lang, "отклонение от средней", "орташадан ауытқу")},
                         {"value": "gears", "label": L(lang, "невод ÷ сеть", "сүзекі ÷ ау")},
                         {"value": "growth", "label": L(lang, "рост поколений", "ұрпақтардың өсуі")}]}]


def v_ca_heat(D, opt, gear, rules=None):
    part, meta, key, code, y, years, f = _species_fit(D, opt, gear)
    lang = D.lang
    mode = opt.get("hmode") if opt.get("hmode") in HMODES else "c"
    tg = _htoggle(lang, mode)
    if mode in ("gears", "growth"):
        ctx, skey, sp, _ = _tsp(D, opt, rules)
        ch, rows, xs = (_gears_heat if mode == "gears" else _growth_heat)(ctx, sp, lang)
        note = (L(lang, "Во сколько раз запас по неводу больше, чем по сети, в каждом возрасте и году; рамка — расхождение больше порога правила.",
                     "Әр жас пен жылда сүзекі бойынша қор аудан неше есе көп; жиек — ереже шегінен артық алшақтық.") if mode == "gears" else
                L(lang, "Во сколько раз запас поколения изменился за год; рамка — рост больше допуска правила. Ожидается убыль (меньше ×1).",
                  "Ұрпақ қоры бір жылда неше есе өзгерді; жиек — ереже шегінен артық өсу. Азаю күтіледі (×1-ден аз)."))
        return {"chart": ch, "columns": _ratio_cols(lang, xs), "rows": rows, "row_action": "year", "toggles": tg, "hmode": mode, "notes": [note],
                **_common(D, meta, years, y, code, gear, "catchability-trust")}
    by = part["fits"][key]
    ages = sorted({a for yy in years for a in (by.get(str(yy)) or {}).get("ages", [])})
    means = {}
    for a in ages:
        vs = [dict(zip((by.get(str(yy)) or {}).get("ages") or [], (by.get(str(yy)) or {}).get("c") or [])).get(a) for yy in years]
        vs = [v for v in vs if v is not None]
        means[a] = sum(vs) / len(vs) if vs else None
    cells, rows = [], []
    for i, yy in enumerate(years):
        fy = by.get(str(yy)) or {}
        cmap = dict(zip(fy.get("ages") or [], fy.get("c") or []))
        row = {"year": yy, "_current": yy == y}
        for j, a in enumerate(ages):
            v = cmap.get(a)
            if mode == "dev":
                v = (v / means[a] - 1) * 100 if (v is not None and means.get(a)) else None
            row[f"a{a}"] = v
            if v is not None:
                cells.append([j, i, round(v, 3 if mode == "c" else 1)])
        rows.append(row)
    return {"chart": {"kind": "heatmap", "x": [age_label(a) for a in ages], "y": years, "cells": cells,
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "Год", "Жыл"),
                      "value_title": "c" if mode == "c" else L(lang, "Отклонение c от средней за годы, %", "c-ның жылдар орташасынан ауытқуы, %"),
                      "fmt": "coef" if mode == "c" else "dev", "y_is_year": True, "pick_year": True, "selected_y": y,
                      "max": part.get("c_upper") if mode == "c" else None},
            "toggles": tg, "hmode": mode,
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
        r = {"year": yy, "_current": yy == y, "n_sample": d.get("n_sample"), "total_catch": d.get("total_catch"), "status": clean_status(d.get("status"))}
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
        cols = [yr, col("a", "a", "number"), col("j50", "j50 " + L(lang, "МНК", "ЕКӘ"), "number"), col("j50_rule", L(lang, "j50 по правилу", "Ереже бойынша j50"), "integer"),
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
    def view(D, opt, rules=None):
        return fn(D, opt, gear, rules) if fn is v_ca_heat else fn(D, opt, gear)
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
    return {"net": L(lang, "Сети (балансовый)", "Аулар (баланс әдісі)"), "seine": L(lang, "Невод (метод площадей)", "Сүзекі (аудандар әдісі)"),
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
        else L(lang, "среднее", "орташа")
    tiles = [
        {"label": L(lang, f"Сети, {y}", f"Аулар, {y}"), "value": pieces(net, lang),
         "hint": L(lang, "балансовый метод", "баланс әдісі")},
        {"label": L(lang, f"Невод, {y}", f"Сүзекі, {y}"), "value": pieces(seine, lang), "hint": L(lang, "метод площадей", "аудандар әдісі")},
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


# ================================================================== Байесовская модель (этап 4)
def num(v):
    """Число для параметров модели: точность по величине."""
    if v is None:
        return "—"
    a = abs(v)
    d = 0 if a >= 100 else 1 if a >= 10 else 2 if a >= 1 else 3 if a >= 0.01 else 5
    return nf(v, d)


def hms(sec):
    if sec is None:
        return "—"
    sec = int(round(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h} ч {m:02d} мин" if h else f"{m} мин {s:02d} с"


def _bayes(D):
    pl, meta = D.run_payload("bayes_cohort")
    if pl is None or not pl.get("species"):
        if meta is None:
            raise NoData(L(D.lang, "Для водоёма ещё нет полного расчёта с байесовской моделью (этапы 1–5) — запустите его в разделе «Расчёты»",
                           "Су айдыны үшін байестік модельмен толық есеп (1–5 кезеңдер) әлі жоқ — «Есептеулер» бөлімінде іске қосыңыз"))
        raise NoData(L(D.lang, "В запуске нет шага «Байесовская когортная модель» — нужен полный расчёт (этапы 1–5)",
                       "Іске қосуда «Байестік когорттық модель» қадамы жоқ — толық есеп қажет (1–5 кезеңдер)"))
    return pl, meta


def _bayes_species(D, opt):
    pl, meta = _bayes(D)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, {"fits": pl["species"]}, code)
    if key is None:
        raise NoData(L(D.lang, f"Для вида «{D.sp_name(code)}» байесовская модель в этом запуске не считалась",
                       f"«{D.sp_name(code)}» түрі үшін байестік модель бұл іске қосуда есептелмеген"))
    R = pl["species"][key]
    y, years = _year({"years": R["years"]}, opt)
    return R, meta, code, y, years


def _btoggles(D, opt, ages=True, data=True):
    lang = D.lang
    a = opt.get("bages") if opt.get("bages") in ("obs", "all") else "obs"
    d = opt.get("bdata") if opt.get("bdata") in ("raw", "q") else "raw"
    t = []
    if ages:
        t.append({"key": "bages", "title": L(lang, "Возрасты", "Жастар"), "value": a,
                  "options": [{"value": "obs", "label": L(lang, "1–2 и старше", "1–2 және үлкен")},
                              {"value": "all", "label": L(lang, "с сеголетками", "шабақтармен")}]})
    if data:
        t.append({"key": "bdata", "title": L(lang, "Оценки по уловам", "Ауланым бойынша бағалар"), "value": d,
                  "options": [{"value": "raw", "label": L(lang, "как есть", "сол күйінде")},
                              {"value": "q", "label": L(lang, "оценки / q", "бағалар / q")}]})
    return a, d, t


def _bcommon(D, meta, years, y, code, R):
    m = R.get("meta") or {}
    lab = [D.sp_name(code) if code else None, str(y) if y else None,
           f"{m.get('chains')} × {m.get('draws_per_chain')} " + L(D.lang, "выборок", "таңдама") if m.get("chains") else None]
    return {"meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "method-bayes", "species_shown": code,
            "filter_label": " · ".join(x for x in lab if x)}


def _qage(R, j):
    """Поправка уловистости q для возраста j (медиана); 1, если не оценена."""
    q = R["q_bias_q"][2]
    k = j - 1
    v = q[k] if 0 <= k < len(q) else None
    return v if v and v > 0 else 1


def _data_total(R, by_age, mode):
    out = []
    for r in by_age:
        if not r:
            out.append(None)
            continue
        s, anyv = 0.0, False
        for k, v in enumerate(r):
            if v is not None:
                s += v / _qage(R, k + 2) if mode == "q" else v
                anyv = True
        out.append(s if anyv else None)
    return out


def v_by_species(D, opt):
    pl, meta = _bayes(D)
    names = _names(D)
    lang = D.lang
    rows = []
    year = None
    for key, R in pl["species"].items():
        if not R.get("available"):
            continue
        m = R.get("meta") or {}
        tot = R["total_obs_q"]
        last = len(R["years"]) - 1
        year = R["years"][last]
        beta = R["beta1d_q"][2]
        code = names.get(key.strip().lower(), key)
        rows.append({"_code": code, "species": D.sp_name(code), "median": tot[2][last], "lo": tot[0][last], "hi": tot[4][last],
                     "recruits": R["X_q"][2][last][0], "beta": sum(beta) / len(beta) if beta else None,
                     "div": m.get("divergences"), "rhat": m.get("rhat_X_max"), "time": hms(m.get("seconds")),
                     "status": L(lang, "есть замечания", "ескертулер бар") if (m.get("divergences") or (m.get("rhat_X_max") or 0) > 1.01)
                     else L(lang, "сошлась", "жинақталды")})
    rows.sort(key=lambda r: -(r["median"] or 0))
    cols = [col("species", L(lang, "Вид", "Түр")), col("median", L(lang, f"Численность {year}, медиана", f"Саны {year}, медиана"), "integer"),
            col("lo", "2,5 %", "integer"), col("hi", "97,5 %", "integer"), col("recruits", L(lang, "Пополнение 0–1", "Толықтыру 0–1"), "integer"),
            col("beta", L(lang, "β в среднем", "Орташа β"), "number"), col("div", L(lang, "Расходимостей", "Алшақтықтар"), "integer"),
            col("rhat", "R̂ max", "number"), col("time", L(lang, "Время", "Уақыт")), col("status", L(lang, "Сходимость", "Жинақталу"))]
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "species", "chart": None,
            "notes": [L(lang, "Численность возрастов 1–2 и старше, штук. Щелчок по строке — все данные по виду.",
                        "1–2 және үлкен жастардың саны, дана. Жолды басу — түр бойынша барлық деректер.")],
            "meta": meta, "help": "method-bayes", "filter_label": str(year) if year else ""}


def v_by_tiles(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    a, _, toggles = _btoggles(D, opt, data=False)
    lang = D.lang
    m = R.get("meta") or {}
    tot = R["total_all_q"] if a == "all" else R["total_obs_q"]
    last = len(years) - 1
    beta = R["beta1d_q"][2]
    tiles = [
        {"label": L(lang, f"Численность, {years[last]}", f"Саны, {years[last]}"), "value": pieces(tot[2][last], lang),
         "hint": f"95 %: {pieces(tot[0][last], lang)} – {pieces(tot[4][last], lang)}"},
        {"label": L(lang, f"Численность, {years[0]}", f"Саны, {years[0]}"), "value": pieces(tot[2][0], lang),
         "hint": f"95 %: {pieces(tot[0][0], lang)} – {pieces(tot[4][0], lang)}"},
        {"label": L(lang, f"Пополнение 0–1, {years[last]}", f"Толықтыру 0–1, {years[last]}"), "value": pieces(R["X_q"][2][last][0], lang), "hint": L(lang, "медиана", "медиана")},
        {"label": L(lang, "β в среднем", "Орташа β"), "value": nf(sum(beta) / len(beta), 2) if beta else "—",
         "hint": L(lang, f"по годам {nf(min(beta), 2)} – {nf(max(beta), 2)}", f"жылдар бойынша {nf(min(beta), 2)} – {nf(max(beta), 2)}") if beta else None},
        {"label": L(lang, "Расходимостей", "Алшақтықтар"), "value": nf(m.get("divergences"), 0) if m.get("divergences") is not None else "—",
         "hint": f"R̂ max: {nf(m.get('rhat_X_max'), 3)}", "level": "warning" if m.get("divergences") else None},
        {"label": L(lang, "Время расчёта", "Есептеу уақыты"), "value": hms(m.get("seconds")),
         "hint": L(lang, f"{m.get('chains')} цепи × {m.get('draws_per_chain')} выборок", f"{m.get('chains')} тізбек × {m.get('draws_per_chain')} таңдама")},
    ]
    warn = []
    if m.get("divergences"):
        warn.append(L(lang, f"{m['divergences']} расходимостей NUTS: результаты в этих областях ненадёжны; помогают больший target_accept или более узкие априорные распределения",
                      f"NUTS {m['divergences']} алшақтығы: бұл аймақтардағы нәтижелер сенімсіз; үлкенірек target_accept немесе тарлау априорлық үлестірімдер көмектеседі"))
    if (m.get("rhat_X_max") or 0) > 1.01:
        warn.append(L(lang, f"R̂ численности до {nf(m['rhat_X_max'], 3)} (> 1,01): цепи не сошлись, нужно больше выборок или шагов настройки",
                      f"Сан R̂ {nf(m['rhat_X_max'], 3)} дейін (> 1,01): тізбектер жинақталмады, көбірек таңдама немесе баптау қадамы қажет"))
    if m.get("numpy_check") is not None and m["numpy_check"] > 1e-6:
        warn.append(L(lang, f"численность из PyMC и пересчёт на numpy отличаются на {num(m['numpy_check'] * 100)} % — сообщите разработчику",
                      f"PyMC және numpy бойынша сан {num(m['numpy_check'] * 100)} %-ға ерекшеленеді — әзірлеушіге хабарлаңыз"))
    for n in m.get("notes") or []:
        warn.append(str(n))
    return {"tiles": tiles, "warnings": [{"level": "warning", "text": w} for w in warn], "default_view": "tiles", "chart": None,
            "toggles": toggles, "columns": [col("label", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні")), col("hint", L(lang, "Пояснение", "Түсініктеме"))],
            "rows": [{"label": t["label"], "value": t["value"], "hint": t.get("hint")} for t in tiles],
            "values": {"median": tot[2][last], "lo": tot[0][last], "hi": tot[4][last], "first": tot[2][0], "div": m.get("divergences"), "rhat": m.get("rhat_X_max")},
            **_bcommon(D, meta, years, y, code, R)}


def _bands(q, name95, name50=None):
    out = [{"name": name95, "lo": q[0], "hi": q[4], "op": 0.16}]
    if name50:
        out.append({"name": name50, "lo": q[1], "hi": q[3], "op": 0.32})
    return out


def v_by_total(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    a, dm, toggles = _btoggles(D, opt)
    lang = D.lang
    tot = R["total_all_q"] if a == "all" else R["total_obs_q"]
    d = R["data"]
    points = []
    fin = _data_total(R, d.get("final_by_age") or [], dm)
    if any(v is not None for v in fin):
        points.append({"name": L(lang, "Окончательный запас по уловам / q", "Ауланым бойынша түпкілікті қор / q") if dm == "q"
                       else L(lang, "Окончательный запас по уловам", "Ауланым бойынша түпкілікті қор"), "values": fin, "c": 1, "dx": -0.12})
    if d.get("npc_total") and any(v is not None for v in d["npc_total"]):
        points.append({"name": L(lang, "Оценка НПЦ", "ҒӨО бағасы"), "values": d["npc_total"], "c": 3, "symbol": "diamond", "dx": 0.12})
    rows = [{"year": yy, "median": tot[2][i], "lo95": tot[0][i], "hi95": tot[4][i], "lo50": tot[1][i], "hi50": tot[3][i],
             "by_catch": fin[i] if i < len(fin) else None, "npc": (d.get("npc_total") or [None] * len(years))[i], "_current": yy == y}
            for i, yy in enumerate(years)]
    return {"chart": {"kind": "band", "x": years, "bands": _bands(tot, L(lang, "95 % интервал", "95 % аралық"), L(lang, "50 % интервал", "50 % аралық")),
                      "lines": [{"name": L(lang, "Модель, медиана", "Модель, медиана"), "values": tot[2], "c": 0, "bold": True}], "points": points,
                      "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True,
                      "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("median", L(lang, "Медиана", "Медиана"), "integer"),
                        col("lo95", "2,5 %", "integer"), col("hi95", "97,5 %", "integer"), col("lo50", "25 %", "integer"), col("hi50", "75 %", "integer"),
                        col("by_catch", L(lang, "По уловам", "Ауланым бойынша"), "integer"), col("npc", L(lang, "НПЦ", "ҒӨО"), "integer")],
            "rows": rows, "toggles": toggles, "row_action": "year",
            "notes": [(L(lang, "Все возрасты, включая сеголетки 0–1.", "Барлық жастар, шабақтарды қоса.") if a == "all"
                       else L(lang, "Возрасты 1–2 и старше (как в уловах).", "1–2 және үлкен жастар (ауланымдағыдай).")) + " " +
                      L(lang, "Полосы — 50 % и 95 % интервалы модели.", "Жолақтар — модельдің 50 % және 95 % аралықтары.")],
            **_bcommon(D, meta, years, y, code, R)}


def _col_at(Xq, yi):
    return [q[yi] for q in Xq]


def v_by_ages(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    _, dm, toggles = _btoggles(D, opt, ages=False)
    lang = D.lang
    yi = years.index(y)
    ages = R["model_ages"]
    X = _col_at(R["X_q"], yi)
    fin = (R["data"].get("final_by_age") or [None] * len(years))[yi]
    fv = None
    if fin:
        full = [None] + list(fin)
        fv = [None if v is None else (v / _qage(R, ages[k]) if dm == "q" and k > 0 else v) for k, v in enumerate(full[:len(ages)])]
    points = [{"name": L(lang, "Оценки по уловам / q", "Ауланым бойынша бағалар / q") if dm == "q" else L(lang, "Оценки по уловам", "Ауланым бойынша бағалар"),
               "values": fv, "c": 1, "dx": 0.14}] if fv and any(v is not None for v in fv) else []
    rows = [{"age": age_label(a), "median": X[2][k], "lo": X[0][k], "hi": X[4][k], "by_catch": fv[k] if fv else None} for k, a in enumerate(ages)]
    return {"chart": {"kind": "band", "x": [age_label(a) for a in ages], "intervals": [{"name": L(lang, "Модель (95 %)", "Модель (95 %)"), "lo": X[0], "hi": X[4], "mid": X[2], "c": 0, "dx": -0.1}],
                      "points": points, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("median", L(lang, "Медиана", "Медиана"), "integer"), col("lo", "2,5 %", "integer"),
                        col("hi", "97,5 %", "integer"), col("by_catch", L(lang, "По уловам", "Ауланым бойынша"), "integer")],
            "rows": rows, "toggles": toggles,
            "notes": [L(lang, "Модель: медиана и 95 % интервал. Оценки по уловам — окончательный запас (сеть и невод).",
                        "Модель: медиана және 95 % аралық. Ауланым бойынша бағалар — түпкілікті қор (ау мен сүзекі).")],
            **_bcommon(D, meta, years, y, code, R)}


def _by_years_band(D, opt, q, title_y, note, hline=None, fmt_int=True):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    qq = q(R)
    rows = [{"year": yy, "median": qq[2][i], "lo": qq[0][i], "hi": qq[4][i], "_current": yy == y} for i, yy in enumerate(years)]
    t = "integer" if fmt_int else "number"
    return {"chart": {"kind": "band", "x": years, "bands": _bands(qq, "95 %", "50 %"), "lines": [{"name": L(lang, "Медиана", "Медиана"), "values": qq[2], "c": 0, "bold": True}],
                      "hrefs": [{"y": hline, "label": f"{title_y} = {nf(hline, 0)}"}] if hline is not None else [],
                      "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True, "x_title": L(lang, "Год", "Жыл"), "y_title": title_y,
                      **({"allowed": ["log", "linear"], "default": "log"} if fmt_int else {})},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("median", L(lang, "Медиана", "Медиана"), t), col("lo", "2,5 %", t), col("hi", "97,5 %", t)],
            "rows": rows, "row_action": "year", "notes": [note], **_bcommon(D, meta, years, y, code, R)}


def v_by_recruits(D, opt):
    lang = D.lang
    return _by_years_band(D, opt, lambda R: [[r[0] for r in q] for q in R["X_q"]], L(lang, "штук", "дана"),
                          L(lang, "Сеголетки: икра × выживаемость, ограниченная ёмкостью нерестилищ, × (1 − s)² / (1 + γ).",
                            "Шабақтар: уылдырық × тіршілік, уылдырық шашу орындарының сыйымдылығымен шектелген, × (1 − s)² / (1 + γ)."))


def v_by_beta(D, opt):
    lang = D.lang
    return _by_years_band(D, opt, lambda R: R["beta1d_q"], "β",
                          L(lang, "Фактический вылов / ПДУ: β > 1 — неучтённый вылов (браконьерство).",
                            "Нақты аулау / ШРА: β > 1 — есепке алынбаған аулау (браконьерлік)."), hline=1, fmt_int=False)


def _by_ages_band(D, opt, key, title_y, note, vref):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    yi = years.index(y)
    ages = R["model_ages"]
    qq = _col_at(R[key], yi)
    rows = [{"age": age_label(a), "median": qq[2][k], "lo": qq[0][k], "hi": qq[4][k]} for k, a in enumerate(ages)]
    return {"chart": {"kind": "band", "x": [age_label(a) for a in ages], "x_num": ages, "bands": _bands(qq, "95 %"),
                      "lines": [{"name": L(lang, "Медиана", "Медиана"), "values": qq[2], "c": 0, "bold": True}],
                      "vrefs": [v for v in [vref(R)] if v], "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": title_y},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("median", L(lang, "Медиана", "Медиана"), "number"),
                        col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number")],
            "rows": rows, "notes": [note], **_bcommon(D, meta, years, y, code, R)}


def v_by_s(D, opt):
    lang = D.lang

    def vr(R):
        m0 = (R.get("meta") or {}).get("m0")
        return {"x": age_label(m0 + 1), "label": "m0 + 1"} if m0 is not None else None
    return _by_ages_band(D, opt, "s_q", L(lang, "доля за год", "жылдағы үлес"),
                         L(lang, "Естественная смертность s — доля рыб возраста, погибающих за год. Медиана и 95 % интервал.",
                           "Табиғи өлім-жітім s — жыл ішінде өлетін жас балықтарының үлесі. Медиана және 95 % аралық."), vr)


def v_by_pred(D, opt):
    lang = D.lang

    def vr(R):
        m2 = (R.get("meta") or {}).get("m2")
        ages = R["model_ages"]
        return {"x": age_label(m2), "label": "m2"} if m2 is not None and m2 < ages[-1] else None
    return _by_ages_band(D, opt, "pred_q", "γ",
                         L(lang, "Давление хищников γ убывает как 1/j до возраста m2; численность возраста делится на 1 + γ.",
                           "Жыртқыштар қысымы γ m2 жасына дейін 1/j ретінде кемиді; жас саны 1 + γ-ға бөлінеді."), vr)


def v_by_q(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    ages = R["model_ages"]
    q = R["q_bias_q"]
    n = min(len(ages), len(q[2]))
    frm = (R.get("config_used") or {}).get("likelihood_from") or 3
    rows = [{"age": age_label(ages[k]), "median": q[2][k], "lo": q[0][k], "hi": q[4][k]} for k in range(n)]
    return {"chart": {"kind": "band", "x": [age_label(a) for a in ages[:n]], "intervals": [{"name": "q (95 %)", "lo": q[0][:n], "hi": q[4][:n], "mid": q[2][:n], "c": 0}],
                      "hrefs": [{"y": 1, "label": "q = 1"}], "vrefs": [{"x": age_label(frm), "label": L(lang, "в правдоподобии →", "шынайылықта →")}],
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": "q", "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("median", L(lang, "Медиана", "Медиана"), "number"),
                        col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number")],
            "rows": rows,
            "notes": [L(lang, f"Оценка по лову ≈ q · численность модели. В правдоподобии — возрасты с {age_label(frm)}; для младших q не оценивается по данным.",
                        f"Аулау бағасы ≈ q · модель саны. Шынайылықта — {age_label(frm)} бастап жастар; кішілер үшін q деректермен бағаланбайды.")],
            **_bcommon(D, meta, years, y, code, R)}


def v_by_deaths(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    dd = R["deaths"]
    poach = [v if v and v > 0 else None for v in dd["poaching"]]
    series = [{"name": L(lang, "Естественная гибель", "Табиғи өлім"), "values": dd["natural"], "type": "bar", "c": 0},
              {"name": L(lang, "Хищники", "Жыртқыштар"), "values": dd["predators"], "type": "bar", "c": 1},
              {"name": L(lang, "ПДУ", "ШРА"), "values": dd["catch"], "type": "bar", "c": 2},
              {"name": L(lang, "Браконьерство", "Браконьерлік"), "values": poach, "type": "bar", "c": 3}]
    rows = [{"year": yy, "natural": dd["natural"][i], "predators": dd["predators"][i], "catch": dd["catch"][i], "poaching": poach[i],
             "_current": yy == y} for i, yy in enumerate(years)]
    return {"chart": {"kind": "fit", "x": years, "series": series, "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "штук", "дана"),
                      "allowed": ["log", "linear"], "default": "log", "pick_year": True},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer")] + [col(k, s["name"], "integer") for k, s in zip(("natural", "predators", "catch", "poaching"), series)],
            "rows": rows, "row_action": "year",
            "notes": [L(lang, "Медианы, штук, сумма по возрастам: естественная гибель s·X, хищники γ·X, ПДУ, браконьерство (β − 1)·ПДУ.",
                        "Медианалар, дана, жастар бойынша қосынды: табиғи өлім s·X, жыртқыштар γ·X, ШРА, браконьерлік (β − 1)·ШРА.")],
            **_bcommon(D, meta, years, y, code, R)}


def v_by_params(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    detail = opt.get("bdetail") == "all"
    toggles = [{"key": "bdetail", "title": L(lang, "Строки", "Жолдар"), "value": "all" if detail else "groups",
                "options": [{"value": "groups", "label": L(lang, "сводно", "жиынтық")}, {"value": "all", "label": L(lang, "по годам и возрастам", "жылдар мен жастар бойынша")}]}]
    rows, groups = [], {}
    for r in R.get("param_rows") or []:
        q = r.get("q") or [None] * 5
        if r.get("index") is None:
            rows.append({"param": r.get("label"), "index": "—", "median": num(q[2]), "i95": f"{num(q[0])} – {num(q[4])}",
                         "i50": f"{num(q[1])} – {num(q[3])}", "rhat": r.get("rhat")})
            continue
        groups.setdefault(r.get("name"), []).append(r)
    for name, rr in groups.items():
        med = [r["q"][2] for r in rr if r["q"][2] is not None]
        lo = [r["q"][0] for r in rr if r["q"][0] is not None]
        hi = [r["q"][4] for r in rr if r["q"][4] is not None]
        rh = max([r.get("rhat") or 0 for r in rr]) or None
        rows.append({"param": rr[0].get("label"), "index": (L(lang, f"{len(rr)} возрастов", f"{len(rr)} жас") if name == "q_bias" else L(lang, f"{len(rr)} лет", f"{len(rr)} жыл")),
                     "median": f"{num(min(med))} – {num(max(med))}" if med else "—", "i95": f"{num(min(lo))} – {num(max(hi))}" if lo else "—", "i50": "", "rhat": rh})
        if detail:
            for r in rr:
                q = r["q"]
                rows.append({"param": "", "index": age_label(r["index"]) if name == "q_bias" else r["index"], "median": num(q[2]),
                             "i95": f"{num(q[0])} – {num(q[4])}", "i50": f"{num(q[1])} – {num(q[3])}", "rhat": r.get("rhat")})
    for r in rows:
        r["_bad"] = bool(r.get("rhat") and r["rhat"] > 1.01)
    return {"columns": [col("param", L(lang, "Параметр", "Параметр")), col("index", L(lang, "Год / возраст", "Жыл / жас")),
                        col("median", L(lang, "Медиана", "Медиана")), col("i95", L(lang, "95 % интервал", "95 % аралық")),
                        col("i50", L(lang, "50 % интервал", "50 % аралық")), col("rhat", "R̂", "number")],
            "rows": rows, "default_view": "table", "chart": None, "toggles": toggles,
            "notes": [L(lang, "Апостериорные медианы и интервалы; R̂ > 1,01 — цепи не сошлись.", "Апостериорлық медианалар мен аралықтар; R̂ > 1,01 — тізбектер жинақталмады.")],
            **_bcommon(D, meta, years, y, code, R)}


def v_by_diag(D, opt):
    R, meta, code, y, years = _bayes_species(D, opt)
    lang = D.lang
    m = R.get("meta") or {}
    dv = m.get("divergences")
    items = [
        (L(lang, "Режим", "Режим"), m.get("mode_title")), (L(lang, "Начало", "Басталуы"), m.get("started")),
        (L(lang, "Окончание", "Аяқталуы"), m.get("finished")), (L(lang, "Время", "Уақыт"), hms(m.get("seconds"))),
        (L(lang, "Цепей × выборок", "Тізбек × таңдама"), f"{m.get('chains')} × {m.get('draws_per_chain')}"),
        (L(lang, "Шагов настройки (tune)", "Баптау қадамдары (tune)"), m.get("tune")),
        (L(lang, "Расходимостей", "Алшақтықтар"), "—" if dv is None else f"{dv}" + (f" ({L(lang, 'по цепям', 'тізбектер бойынша')}: {', '.join(map(str, m['divergences_by_chain']))})" if m.get("divergences_by_chain") else "")),
        (L(lang, "Достигнута max_treedepth", "max_treedepth жеткен"), m.get("treedepth_hits")),
        (L(lang, "Средний шаг", "Орташа қадам"), num(m.get("step_size")) if m.get("step_size") else "—"),
        (L(lang, "Средняя доля принятия", "Орташа қабылдау үлесі"), nf(m.get("acceptance_rate"), 3) if m.get("acceptance_rate") else "—"),
        (L(lang, "R̂ численности, max", "Сан R̂, max"), nf(m.get("rhat_X_max"), 3) if m.get("rhat_X_max") else "—"),
        (L(lang, "Сверка уравнений PyMC и numpy", "PyMC және numpy теңдеулерін салыстыру"),
         "—" if m.get("numpy_check") is None else L(lang, f"отличие {m['numpy_check']:.1e}", f"айырма {m['numpy_check']:.1e}")),
        (L(lang, "Ловов в правдоподобии", "Шынайылықтағы аулаулар"), f"{m.get('n_obs')}" + (L(lang, f" (исключено {m['dropped']})", f" ({m['dropped']} алынып тасталды)") if m.get("dropped") else "")),
        ("m0 / m1 / m2", f"{m.get('m0')} / {m.get('m1')} / {m.get('m2')}"),
    ]
    rows = [{"key": k, "value": "—" if v is None else str(v)} for k, v in items]
    return {"columns": [col("key", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні"))], "rows": rows,
            "default_view": "table", "chart": None, "diag": {"divergences": dv, "rhat": m.get("rhat_X_max"), "n_obs": m.get("n_obs")},
            **_bcommon(D, meta, years, y, code, R)}


VIEWS.update({"by_species": v_by_species, "by_tiles": v_by_tiles, "by_total": v_by_total, "by_ages": v_by_ages,
              "by_recruits": v_by_recruits, "by_s": v_by_s, "by_pred": v_by_pred, "by_beta": v_by_beta, "by_q": v_by_q,
              "by_deaths": v_by_deaths, "by_params": v_by_params, "by_diag": v_by_diag})


# ================================================================== ПДУ НПЦ по возрастам (этап 3) — официальный
def tonnes(v):
    if v is None:
        return "—"
    if abs(v) < 0.005:
        return "0"
    a = abs(v)
    return nf(v, 0 if a >= 100 else 1 if a >= 1 else 2)


def pct(v):
    if v is None:
        return "—"
    return f"{nf(v * 100, 0 if v >= 0.1 else 1)} %"


def _pdu(D):
    pl, meta = D.run_payload("pdu_by_age")
    if pl is None or not pl.get("species"):
        if meta is None:
            raise NoData(L(D.lang, "Для водоёма ещё нет расчёта ПДУ НПЦ по возрастам — запустите расчёт в разделе «Расчёты»",
                           "Су айдыны үшін жас бойынша ҒӨО ШРА әлі есептелмеген — «Есептеулер» бөлімінде іске қосыңыз"))
        raise NoData(L(D.lang, "В запуске нет шага «ПДУ НПЦ по возрастам»", "Іске қосуда «Жас бойынша ҒӨО ШРА» қадамы жоқ"))
    return pl, meta


def _pdu_species(D, opt):
    pl, meta = _pdu(D)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, {"fits": pl["species"]}, code)
    if key is None:
        raise NoData(L(D.lang, f"Для вида «{D.sp_name(code)}» нет ПДУ НПЦ в этом запуске", f"«{D.sp_name(code)}» түрі үшін бұл іске қосуда ҒӨО ШРА жоқ"))
    y, years = _year(pl, opt)
    return pl, meta, pl["species"][key], code, y, years


def _pcommon(D, meta, years, y, code):
    return {"meta": meta, "year": y, "year_choices": years, "calc_year": True, "help": "method-pdu-age", "species_shown": code,
            "filter_label": " · ".join(x for x in [D.sp_name(code) if code else None, str(y), L(D.lang, "ПДУ НПЦ (официальный)", "ҒӨО ШРА (ресми)")] if x)}


def v_pn_species(D, opt):
    pl, meta = _pdu(D)
    y, years = _year(pl, opt)
    yi = years.index(y)
    names = _names(D)
    lang = D.lang
    rows = []
    for key, sp in pl["species"].items():
        code = names.get(key.strip().lower(), key)
        b = sp["biomass_t"][yi]
        rows.append({"_code": code, "species": D.sp_name(code), "pdu_t": sp["pdu_t"][yi], "dist_t": sp["distributed_t"][yi],
                     "left_t": sp["left_t"][yi], "pcs": sp["pieces_total"][yi], "biomass_t": b,
                     "share": (sp["pdu_t"][yi] / b * 100) if b else None, "stop": sp["stop_reason"][yi]})
    rows.sort(key=lambda r: -(r["pdu_t"] or 0))
    cols = [col("species", L(lang, "Вид", "Түр")), col("pdu_t", L(lang, "ПДУ НПЦ, т", "ҒӨО ШРА, т"), "number"),
            col("dist_t", L(lang, "Распределено, т", "Бөлінді, т"), "number"), col("left_t", L(lang, "Не распределено, т", "Бөлінбеді, т"), "number"),
            col("pcs", L(lang, "ПДУ, шт", "ШРА, дана"), "integer"), col("biomass_t", L(lang, "Промысловая биомасса, т", "Кәсіптік биомасса, т"), "number"),
            col("share", L(lang, "ПДУ / биомасса, %", "ШРА / биомасса, %"), "number"), col("stop", L(lang, "Остановка", "Тоқтау"))]
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "species", "chart": None,
            "notes": [L(lang, "Официальный ПДУ НПЦ, переведённый в штуки рыб по возрастам. Щелчок по строке — все данные по виду.",
                        "Жас бойынша балық данасына аударылған ресми ҒӨО ШРА. Жолды басу — түр бойынша барлық деректер.")],
            **_pcommon(D, meta, years, y, None)}


def v_pn_tiles(D, opt):
    pl, meta, sp, code, y, years = _pdu_species(D, opt)
    yi = years.index(y)
    lang = D.lang
    by = sp["by_year"][yi]
    share = sp["pdu_t"][yi] / sp["biomass_t"][yi] if sp["biomass_t"][yi] else None
    dist = sp["distributed_t"][yi] / sp["pdu_t"][yi] if sp["pdu_t"][yi] else None
    tiles = [
        {"label": L(lang, f"ПДУ НПЦ, {y}", f"ҒӨО ШРА, {y}"), "value": f"{tonnes(sp['pdu_t'][yi])} т", "hint": L(lang, "официальный", "ресми")},
        {"label": L(lang, "Распределено", "Бөлінді"), "value": f"{tonnes(sp['distributed_t'][yi])} т", "hint": L(lang, f"{pct(dist)} квоты", f"квотаның {pct(dist)}") if dist is not None else None},
        {"label": L(lang, "Не распределено", "Бөлінбеді"), "value": f"{tonnes(sp['left_t'][yi])} т", "hint": sp["stop_reason"][yi],
         "level": "warning" if (sp["left_t"][yi] or 0) > 1e-6 else None},
        {"label": L(lang, "ПДУ в штуках", "ШРА данамен"), "value": pieces(sp["pieces_total"][yi], lang),
         "hint": L(lang, f"возрасты от {age_label(sp['m0'])} (половозрелые)", f"{age_label(sp['m0'])} бастап жастар (жыныстық жетілген)")},
        {"label": L(lang, "Доля от промысловой биомассы", "Кәсіптік биомассадан үлес"), "value": pct(share),
         "hint": L(lang, f"биомасса {tonnes(sp['biomass_t'][yi])} т", f"биомасса {tonnes(sp['biomass_t'][yi])} т")},
        {"label": L(lang, "Итераций", "Итерациялар"), "value": nf(sp["iterations"][yi], 0), "hint": L(lang, "до исчерпания квоты или запаса", "квота немесе қор біткенге дейін")},
    ]
    warn = []
    if (sp["left_t"][yi] or 0) > 1e-6:
        warn.append(L(lang, f"не распределено {tonnes(sp['left_t'][yi])} т: {sp['stop_reason'][yi]}", f"{tonnes(sp['left_t'][yi])} т бөлінбеді: {sp['stop_reason'][yi]}"))
    capped = [age_label(a) for a, c in zip(sp["ages"], by.get("capped") or []) if c]
    if capped:
        warn.append(L(lang, "ограничение 75 % срабатывало для возрастов " + ", ".join(capped), "75 % шектеу мына жастар үшін іске қосылды: " + ", ".join(capped)))
    filled = [age_label(a) for a, f in zip(sp["ages"], sp.get("weight_filled") or []) if f]
    if filled:
        warn.append(L(lang, "средний вес возраста " + ", ".join(filled) + " взят от ближайшего младшего возраста",
                      ", ".join(filled) + " жасының орташа салмағы ең жақын кіші жастан алынды"))
    return {"tiles": tiles, "warnings": [{"level": "warning", "text": L(lang, "Обратите внимание: ", "Назар аударыңыз: ") + "; ".join(warn) + "."}] if warn else [],
            "default_view": "tiles", "chart": None,
            "columns": [col("label", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні")), col("hint", L(lang, "Пояснение", "Түсініктеме"))],
            "rows": [{"label": t["label"], "value": t["value"], "hint": t.get("hint")} for t in tiles],
            "values": {"pdu_t": sp["pdu_t"][yi], "share": share, "pcs": sp["pieces_total"][yi], "left_t": sp["left_t"][yi]},
            **_pcommon(D, meta, years, y, code)}


def v_pn_ages(D, opt):
    pl, meta, sp, code, y, years = _pdu_species(D, opt)
    yi = years.index(y)
    lang = D.lang
    by = sp["by_year"][yi]
    ages = sp["ages"]
    series = [{"name": L(lang, "Запас", "Қор"), "values": by["stock"], "type": "bar", "c": 0},
              {"name": L(lang, "ПДУ", "ШРА"), "values": [v if v and v > 0 else None for v in by["pieces"]], "type": "bar", "c": 1}]
    rows = [{"age": age_label(a) + (" *" if (sp.get("weight_filled") or [False] * len(ages))[i] else ""), "stock": by["stock"][i], "weight": by["weight"][i],
             "pcs": by["pieces"][i], "t": by["tonnes"][i], "expl": (by["exploitation"][i] * 100 if by["exploitation"][i] is not None else None) if a >= sp["m0"] else None,
             "capped": L(lang, "да", "иә") if (by.get("capped") or [False] * len(ages))[i] else "—"} for i, a in enumerate(ages)]
    return {"chart": {"kind": "fit", "x": [age_label(a) for a in ages], "series": series, "vrefs": [{"x": age_label(sp["m0"]), "label": L(lang, "половозрелые →", "жыныстық жетілгендер →")}],
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("stock", L(lang, "Запас, шт", "Қор, дана"), "integer"),
                        col("weight", L(lang, "Средний вес, г", "Орташа салмақ, г"), "integer"), col("pcs", L(lang, "ПДУ, шт", "ШРА, дана"), "integer"),
                        col("t", L(lang, "ПДУ, т", "ШРА, т"), "number"), col("expl", L(lang, "Доля изъятия, %", "Алу үлесі, %"), "number"),
                        col("capped", L(lang, "Ограничение 75 %", "75 % шектеу"))],
            "rows": rows,
            "notes": [L(lang, "Окончательный запас (сети и невод) и ПДУ НПЦ в штуках по возрастам; ловятся только половозрелые. * — вес взят от младшего возраста.",
                        "Жастар бойынша түпкілікті қор (аулар мен сүзекі) және ҒӨО ШРА данамен; тек жыныстық жетілгендер ауланады. * — салмақ кіші жастан алынған.")],
            **_pcommon(D, meta, years, y, code)}


def v_pn_expl(D, opt):
    pl, meta, sp, code, y, years = _pdu_species(D, opt)
    yi = years.index(y)
    lang = D.lang
    by = sp["by_year"][yi]
    ages = sp["ages"]
    vals = [(by["exploitation"][i] * 100 if by["exploitation"][i] is not None else None) if a >= sp["m0"] else None for i, a in enumerate(ages)]
    rows = [{"age": age_label(a), "expl": vals[i]} for i, a in enumerate(ages)]
    return {"chart": {"kind": "curve", "x": [age_label(a) for a in ages], "x_num": ages, "series": [{"name": L(lang, "Доля изъятия, %", "Алу үлесі, %"), "values": vals}],
                      "hrefs": [{"y": (pl.get("cap") or 0.75) * 100, "label": L(lang, f"предел за итерацию {nf((pl.get('cap') or 0.75) * 100, 0)} %", f"итерациядағы шек {nf((pl.get('cap') or 0.75) * 100, 0)} %")}],
                      "vrefs": [], "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": "%", "y_max": 100},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("expl", L(lang, "Доля изъятия, %", "Алу үлесі, %"), "number")], "rows": rows,
            "notes": [L(lang, "Доля запаса возраста, изымаемая по ПДУ НПЦ; молодь до m0 не ловится.", "ҒӨО ШРА бойынша алынатын жас қорының үлесі; m0-ге дейінгі жас балық ауланбайды.")],
            **_pcommon(D, meta, years, y, code)}


def v_pn_years(D, opt):
    pl, meta, sp, code, y, years = _pdu_species(D, opt)
    lang = D.lang
    series = [{"name": L(lang, "Промысловая биомасса, т", "Кәсіптік биомасса, т"), "values": sp["biomass_t"], "type": "line", "c": 0},
              {"name": L(lang, "ПДУ НПЦ, т", "ҒӨО ШРА, т"), "values": sp["pdu_t"], "type": "line", "c": 1, "bold": True}]
    if any((v or 0) > 1e-6 for v in sp["left_t"]):
        series.append({"name": L(lang, "Распределено, т", "Бөлінді, т"), "values": sp["distributed_t"], "type": "line", "c": 2, "dash": True})
    rows = [{"year": yy, "pdu_t": sp["pdu_t"][i], "dist_t": sp["distributed_t"][i], "left_t": sp["left_t"][i], "pcs": sp["pieces_total"][i],
             "biomass_t": sp["biomass_t"][i], "share": (sp["pdu_t"][i] / sp["biomass_t"][i] * 100) if sp["biomass_t"][i] else None,
             "iter": sp["iterations"][i], "stop": sp["stop_reason"][i], "_current": yy == y} for i, yy in enumerate(years)]
    return {"chart": {"kind": "fit", "x": years, "series": series, "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True,
                      "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "тонн", "тонна"), "allowed": ["log", "linear"], "default": "linear"},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("pdu_t", L(lang, "ПДУ НПЦ, т", "ҒӨО ШРА, т"), "number"),
                        col("dist_t", L(lang, "Распределено, т", "Бөлінді, т"), "number"), col("left_t", L(lang, "Не распределено, т", "Бөлінбеді, т"), "number"),
                        col("pcs", L(lang, "ПДУ, шт", "ШРА, дана"), "integer"), col("biomass_t", L(lang, "Промысловая биомасса, т", "Кәсіптік биомасса, т"), "number"),
                        col("share", L(lang, "ПДУ / биомасса, %", "ШРА / биомасса, %"), "number"), col("iter", L(lang, "Итераций", "Итерациялар"), "integer"),
                        col("stop", L(lang, "Остановка", "Тоқтау"))],
            "rows": rows, "row_action": "year",
            "notes": [L(lang, "Щелчок по точке или строке выбирает год.", "Нүктені немесе жолды басу жылды таңдайды.")],
            **_pcommon(D, meta, years, y, code)}


def v_pn_table(D, opt):
    res = v_pn_years(D, opt)
    return {**res, "chart": None, "default_view": "table"}


VIEWS.update({"pn_species": v_pn_species, "pn_tiles": v_pn_tiles, "pn_ages": v_pn_ages, "pn_expl": v_pn_expl,
              "pn_years": v_pn_years, "pn_table": v_pn_table})


# ================================================================== ПДУ, рассчитанный в приложении (этап 5: F = k·M, прогноз)
SCEN = ("baranov", "fixed", "none")


def _scen_title(sc, lang):
    return {"baranov": "F = k·M", "fixed": L(lang, "фиксированный ПДУ", "тіркелген ШРА"), "none": L(lang, "без промысла", "кәсіпшіліксіз")}[sc]


def _fc(D):
    pl, meta = D.run_payload("forecast_pdu")
    if pl is None or not pl.get("species"):
        if meta is None:
            raise NoData(L(D.lang, "Для водоёма ещё нет полного расчёта (этапы 1–5): ПДУ приложения считается по байесовской модели",
                           "Су айдыны үшін толық есеп (1–5 кезеңдер) әлі жоқ: қосымша ШРА байестік модель бойынша есептеледі"))
        raise NoData(L(D.lang, "В запуске нет шага «Прогноз и ПДУ» — нужен полный расчёт (этапы 1–5)",
                       "Іске қосуда «Болжам және ШРА» қадамы жоқ — толық есеп қажет (1–5 кезеңдер)"))
    return pl, meta


def _fc_species(D, opt):
    pl, meta = _fc(D)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    key = _key_for(D, {"fits": pl["species"]}, code)
    if key is None:
        raise NoData(L(D.lang, f"Для вида «{D.sp_name(code)}» прогноз в этом запуске не считался", f"«{D.sp_name(code)}» түрі үшін болжам бұл іске қосуда есептелмеген"))
    return pl, meta, pl["species"][key], code


def _ftoggle(D, opt):
    lang = D.lang
    sc = opt.get("scenario") if opt.get("scenario") in SCEN else "baranov"
    return sc, [{"key": "scenario", "title": L(lang, "Интервалы для сценария", "Сценарий аралықтары"), "value": sc,
                 "options": [{"value": s, "label": _scen_title(s, lang)} for s in SCEN]}]


def _fcommon(D, meta, code, extra=None):
    return {"meta": meta, "calc_year": False, "help": "method-forecast", "species_shown": code,
            "filter_label": " · ".join(x for x in [D.sp_name(code) if code else None, L(D.lang, "ПДУ, рассчитанный в приложении (F = k·M)", "Қосымшада есептелген ШРА (F = k·M)"), extra] if x)}


def v_fc_species(D, opt):
    pl, meta = _fc(D)
    lang = D.lang
    names = _names(D)
    rows = []
    y1 = ye = yl = None
    for r in pl.get("summary") or []:
        code = r.get("code") or names.get(str(r.get("species")).strip().lower())
        y1, ye, yl = r.get("year_first_fc"), r.get("year_last_fc"), r.get("year_last")
        rows.append({"_code": code, "species": D.sp_name(code), "pdu": r.get("pdu_next_t"), "lo": r.get("pdu_next_t_q025"), "hi": r.get("pdu_next_t_q975"),
                     "npc": r.get("npc_last_t"), "ratio": (r["pdu_next_t"] / r["npc_last_t"]) if r.get("npc_last_t") else None,
                     "total": r.get("total_last"), "end_b": r.get("total_end_baranov"), "end_f": r.get("total_end_fixed"), "end_n": r.get("total_end_none"),
                     "p_dec": (r.get("p_decline_baranov") or 0) * 100 if r.get("p_decline_baranov") is not None else None})
    rows.sort(key=lambda r: -(r["pdu"] or 0))
    cols = [col("species", L(lang, "Вид", "Түр")), col("pdu", L(lang, f"ПДУ {y1}, F = k·M, т", f"ШРА {y1}, F = k·M, т"), "number"),
            col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number"), col("npc", L(lang, f"ПДУ НПЦ {yl}, т (для сравнения)", f"ҒӨО ШРА {yl}, т (салыстыру үшін)"), "number"),
            col("ratio", L(lang, "F = k·M / НПЦ, раз", "F = k·M / ҒӨО, есе"), "number"), col("total", L(lang, f"Численность {yl}", f"Саны {yl}"), "integer"),
            col("end_b", f"{ye}: F = k·M", "integer"), col("end_f", L(lang, f"{ye}: фикс. ПДУ", f"{ye}: тіркелген ШРА"), "integer"),
            col("end_n", L(lang, f"{ye}: без промысла", f"{ye}: кәсіпшіліксіз"), "integer"), col("p_dec", L(lang, "Вероятность снижения, F = k·M, %", "Төмендеу ықтималдығы, F = k·M, %"), "number")]
    return {"columns": cols, "rows": rows, "default_view": "table", "row_action": "species", "chart": None,
            "notes": [L(lang, f"ПДУ, рассчитанный в приложении по байесовской модели (k = {nf(pl.get('k'), 2)}); ПДУ НПЦ — только для сравнения. Щелчок по строке — все данные по виду.",
                        f"Байестік модель бойынша қосымшада есептелген ШРА (k = {nf(pl.get('k'), 2)}); ҒӨО ШРА — тек салыстыру үшін. Жолды басу — түр бойынша барлық деректер.")],
            **_fcommon(D, meta, None, f"k = {nf(pl.get('k'), 2)}")}


def v_fc_tiles(D, opt):
    pl, meta, R, code = _fc_species(D, opt)
    sc, toggles = _ftoggle(D, opt)
    lang = D.lang
    S = R["scenarios"]
    y1, ye, yl = R["years_fc"][0], R["years_fc"][-1], R["years_hist"][-1]
    b, F, M = S["baranov"]["pdu_t_q"], R["F_q"], R["Mbar_q"]
    f = S[sc]
    st = R.get("settings") or {}
    tiles = [
        {"label": L(lang, f"ПДУ {y1}, F = k·M", f"ШРА {y1}, F = k·M"), "value": f"{tonnes(b[2][0])} т", "hint": f"95 %: {tonnes(b[0][0])} – {tonnes(b[4][0])} т"},
        {"label": L(lang, f"ПДУ НПЦ {yl} (для сравнения)", f"ҒӨО ШРА {yl} (салыстыру үшін)"), "value": f"{tonnes(st.get('npc_last'))} т",
         "hint": L(lang, f"фиксированный в прогнозе: {tonnes(st.get('pdu_fixed_t'))} т", f"болжамда тіркелген: {tonnes(st.get('pdu_fixed_t'))} т")},
        {"label": f"F {y1}", "value": nf(F[2][0], 3), "hint": f"M̄ = {nf(M[2][0], 3)}, k = {nf(st.get('k'), 2)}"},
        {"label": L(lang, f"Численность {yl}", f"Саны {yl}"), "value": pieces(R["hist"]["total_q"][2][-1], lang), "hint": L(lang, "возрасты 1–2 и старше", "1–2 және үлкен жастар")},
        {"label": L(lang, f"Численность {ye}", f"Саны {ye}"), "value": pieces(f["total_q"][2][-1], lang), "hint": _scen_title(sc, lang)},
        {"label": L(lang, "Вероятность снижения", "Төмендеу ықтималдығы"), "value": pct(f.get("p_decline")),
         "hint": L(lang, f"{ye} ниже {yl}, {_scen_title(sc, lang)}", f"{ye} {yl}-ден төмен, {_scen_title(sc, lang)}")},
    ]
    notes = [str(n) for n in (R.get("notes") or [])]
    setm = [f"{R['years_fc'][i]}: {nf(v, 3)}" for i, v in enumerate(st.get("mortality") or []) if v is not None]
    if setm:
        notes.append(L(lang, "смертность задана: " + ", ".join(setm) + "; в остальные годы — из истории", "өлім-жітім берілген: " + ", ".join(setm) + "; басқа жылдары — тарихтан"))
    return {"tiles": tiles, "warnings": [{"level": "warning", "text": n} for n in notes], "default_view": "tiles", "chart": None, "toggles": toggles,
            "columns": [col("label", L(lang, "Показатель", "Көрсеткіш")), col("value", L(lang, "Значение", "Мәні")), col("hint", L(lang, "Пояснение", "Түсініктеме"))],
            "rows": [{"label": t["label"], "value": t["value"], "hint": t.get("hint")} for t in tiles],
            "values": {"pdu": b[2][0], "lo": b[0][0], "hi": b[4][0], "npc": st.get("npc_last"), "p_dec": f.get("p_decline"), "y1": y1, "ye": ye, "sc": _scen_title(sc, lang)},
            **_fcommon(D, meta, code)}


def _joined(R, hist, fc_arr, join=None):
    nh = len(R["years_hist"])
    h = list(hist) + [None] * len(R["years_fc"])
    f = [None] * nh + list(fc_arr)
    if join is not None and nh:
        f[nh - 1] = join
    return h, f


def _scen_chart(D, opt, hist_q, key, y_title, last_q=None):
    pl, meta, R, code = _fc_species(D, opt)
    sc, toggles = _ftoggle(D, opt)
    lang = D.lang
    x = R["years_hist"] + R["years_fc"]
    nh = len(R["years_hist"])
    hq = hist_q(R)
    lq = last_q(R) if last_q else [q[nh - 1] for q in hq]
    bands = [{"name": L(lang, "История, 95 %", "Тарих, 95 %"), "lo": _joined(R, hq[0], [])[0], "hi": _joined(R, hq[4], [])[0], "op": 0.16, "c": 0}]
    lines = [{"name": L(lang, "История, медиана", "Тарих, медиана"), "values": _joined(R, hq[2], [])[0], "c": 0, "bold": True}]
    cmap = {"baranov": 1, "fixed": 3, "none": 2}
    for s in SCEN:
        qd = R["scenarios"][s][key]
        lines.append({"name": _scen_title(s, lang), "values": _joined(R, [], qd[2], lq[2])[1], "c": cmap[s], "bold": s == sc})
    fq = R["scenarios"][sc][key]
    bands.append({"name": L(lang, f"{_scen_title(sc, lang)}, 95 %", f"{_scen_title(sc, lang)}, 95 %"), "lo": _joined(R, [], fq[0], lq[0])[1], "hi": _joined(R, [], fq[4], lq[4])[1], "op": 0.14, "c": cmap[sc]})
    bands.append({"name": L(lang, f"{_scen_title(sc, lang)}, 50 %", f"{_scen_title(sc, lang)}, 50 %"), "lo": _joined(R, [], fq[1], lq[1])[1], "hi": _joined(R, [], fq[3], lq[3])[1], "op": 0.28, "c": cmap[sc]})
    rows = []
    for i, yy in enumerate(x):
        r = {"year": yy, "kind": L(lang, "история", "тарих") if i < nh else L(lang, "прогноз", "болжам")}
        if i < nh:
            r.update({"median": hq[2][i], "lo": hq[0][i], "hi": hq[4][i]})
        else:
            h = i - nh
            r.update({"median": fq[2][h], "lo": fq[0][h], "hi": fq[4][h]})
        rows.append(r)
    return {"chart": {"kind": "band", "x": x, "bands": bands, "lines": lines, "vrefs": [{"x": str(R["years_fc"][0]), "label": L(lang, "прогноз →", "болжам →")}],
                      "x_title": L(lang, "Год", "Жыл"), "y_title": y_title, "allowed": ["linear", "log"], "default": "linear"},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("kind", L(lang, "Период", "Кезең")), col("median", L(lang, "Медиана", "Медиана"), "number"),
                        col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number")],
            "rows": rows, "toggles": toggles, **_fcommon(D, meta, code, _scen_title(sc, lang))}


def v_fc_total(D, opt):
    lang = D.lang
    r = _scen_chart(D, opt, lambda R: R["hist"]["total_q"], "total_q", L(lang, "штук", "дана"), lambda R: R["hist"]["total_last_draws_q"])
    r["notes"] = [L(lang, "Возрасты 1–2 и старше. История — байесовская модель; прогноз — медианы сценариев, полосы 50 % и 95 % — для выбранного сценария.",
                    "1–2 және үлкен жастар. Тарих — байестік модель; болжам — сценарийлер медианалары, 50 % және 95 % жолақтары — таңдалған сценарий үшін.")]
    return r


def v_fc_biomass(D, opt):
    lang = D.lang
    r = _scen_chart(D, opt, lambda R: R["hist"]["fishable_q"], "fishable_q", L(lang, "тонн", "тонна"))
    r["notes"] = [L(lang, "Промысловая биомасса: возрасты от m0 × средний вес последнего года истории, тонн.",
                    "Кәсіптік биомасса: m0-ден бастап жастар × тарихтың соңғы жылының орташа салмағы, тонна.")]
    return r


def v_fc_pdu(D, opt):
    pl, meta, R, code = _fc_species(D, opt)
    lang = D.lang
    x = R["years_hist"] + R["years_fc"]
    b, fx = R["scenarios"]["baranov"]["pdu_t_q"], R["scenarios"]["fixed"]["pdu_t_q"]
    npc = R["hist"]["npc_pdu_t"]
    last = npc[-1] if npc else None
    bands = [{"name": "F = k·M, 95 %", "lo": _joined(R, [], b[0])[1], "hi": _joined(R, [], b[4])[1], "op": 0.16, "c": 1},
             {"name": "F = k·M, 50 %", "lo": _joined(R, [], b[1])[1], "hi": _joined(R, [], b[3])[1], "op": 0.3, "c": 1}]
    lines = [{"name": L(lang, "ПДУ НПЦ (история)", "ҒӨО ШРА (тарих)"), "values": _joined(R, npc, [])[0], "c": 3},
             {"name": L(lang, "F = k·M, медиана", "F = k·M, медиана"), "values": _joined(R, [], b[2])[1], "c": 1, "bold": True},
             {"name": L(lang, "Фиксированный ПДУ", "Тіркелген ШРА"), "values": _joined(R, [], fx[2], last)[1], "c": 3, "dash": True}]
    rows = [{"year": yy, "npc": npc[i] if i < len(npc) else None} for i, yy in enumerate(R["years_hist"])]
    rows += [{"year": yy, "pdu": b[2][h], "lo": b[0][h], "hi": b[4][h], "fixed": fx[2][h]} for h, yy in enumerate(R["years_fc"])]
    return {"chart": {"kind": "band", "x": x, "bands": bands, "lines": lines, "vrefs": [{"x": str(R["years_fc"][0]), "label": L(lang, "прогноз →", "болжам →")}],
                      "x_title": L(lang, "Год", "Жыл"), "y_title": L(lang, "тонн", "тонна"), "allowed": ["linear", "log"], "default": "linear"},
            "columns": [col("year", L(lang, "Год", "Жыл"), "integer"), col("npc", L(lang, "ПДУ НПЦ, т", "ҒӨО ШРА, т"), "number"),
                        col("pdu", L(lang, "F = k·M, медиана, т", "F = k·M, медиана, т"), "number"), col("lo", "2,5 %", "number"), col("hi", "97,5 %", "number"),
                        col("fixed", L(lang, "Фиксированный ПДУ, т", "Тіркелген ШРА, т"), "number")],
            "rows": rows,
            "notes": [L(lang, "История — ПДУ НПЦ (для сравнения); прогноз — ПДУ приложения F = k·M (медиана и интервалы) и фиксированный ПДУ.",
                        "Тарих — ҒӨО ШРА (салыстыру үшін); болжам — қосымша ШРА F = k·M (медиана және аралықтар) және тіркелген ШРА.")],
            **_fcommon(D, meta, code)}


def v_fc_ages(D, opt):
    pl, meta, R, code = _fc_species(D, opt)
    sc, toggles = _ftoggle(D, opt)
    lang = D.lang
    yl, ye = R["years_hist"][-1], R["years_fc"][-1]
    ages = R["ages"]
    a1, a2 = R["hist"]["X_last_q"][2], R["scenarios"][sc]["X_last_q"][2]
    series = [{"name": L(lang, f"{yl} (модель)", f"{yl} (модель)"), "values": a1, "type": "bar", "c": 0},
              {"name": f"{ye}: {_scen_title(sc, lang)}", "values": a2, "type": "bar", "c": {"baranov": 1, "fixed": 3, "none": 2}[sc]}]
    rows = [{"age": age_label(a), "last": a1[i], "end": a2[i]} for i, a in enumerate(ages)]
    return {"chart": {"kind": "fit", "x": [age_label(a) for a in ages], "series": series, "vrefs": [{"x": age_label(R["m0"]), "label": L(lang, "промысловые →", "кәсіптік →")}],
                      "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "штук", "дана"), "allowed": ["log", "linear"], "default": "log"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл")), col("last", str(yl), "integer"), col("end", f"{ye}: {_scen_title(sc, lang)}", "integer")],
            "rows": rows, "toggles": toggles, "notes": [L(lang, "Медианы, штук.", "Медианалар, дана.")], **_fcommon(D, meta, code, _scen_title(sc, lang))}


def v_fc_pdu_ages(D, opt):
    pl, meta, R, code = _fc_species(D, opt)
    lang = D.lang
    med = R["scenarios"]["baranov"]["pdu_pcs_median"]
    ages = R["ages"]
    idx = [i for i, a in enumerate(ages) if a >= R["m0"]]
    pick = sorted({0, len(med) - 1})
    series = [{"name": str(R["years_fc"][h]), "values": [med[h][i] for i in idx], "type": "bar", "c": 1 + n} for n, h in enumerate(pick)]
    rows = [{"age": age_label(ages[i]), **{f"y{R['years_fc'][h]}": med[h][i] for h in pick}} for i in idx]
    return {"chart": {"kind": "fit", "x": [age_label(ages[i]) for i in idx], "series": series, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"),
                      "y_title": L(lang, "штук", "дана"), "allowed": ["linear", "log"], "default": "linear"},
            "columns": [col("age", L(lang, "Возраст, лет", "Жасы, жыл"))] + [col(f"y{R['years_fc'][h]}", str(R["years_fc"][h]), "integer") for h in pick],
            "rows": rows, "notes": [L(lang, "Медианы, штук, сценарий F = k·M.", "Медианалар, дана, F = k·M сценарийі.")], **_fcommon(D, meta, code)}


def v_fc_table(D, opt):
    pl, meta, R, code = _fc_species(D, opt)
    sc, toggles = _ftoggle(D, opt)
    lang = D.lang
    S = R["scenarios"][sc]
    st = R.get("settings") or {}
    rows = []
    for h, yy in enumerate(R["years_fc"]):
        r = {"year": yy, "area": st.get("areas", [None] * 99)[h], "s_mat": R["s_mature_q"][2][h], "beta": R["beta_q"][2][h],
             "total": S["total_q"][2][h], "total_lo": S["total_q"][0][h], "total_hi": S["total_q"][4][h], "fish_t": S["fishable_q"][2][h],
             "pdu_t": S["pdu_t_q"][2][h], "pdu_lo": S["pdu_t_q"][0][h] if sc != "none" else None, "pdu_hi": S["pdu_t_q"][4][h] if sc != "none" else None,
             "pdu_pcs": S["pdu_pcs_total_q"][2][h], "removal": S["removal_t_q"][2][h]}
        if sc == "baranov":
            r.update({"F": R["F_q"][2][h], "M": R["Mbar_q"][2][h]})
        rows.append(r)
    cols = [col("year", L(lang, "Год", "Жыл"), "integer"), col("area", L(lang, "Площадь, км²", "Аудан, км²"), "number"),
            col("s_mat", L(lang, "s половозрелых", "жетілгендер s"), "number"), col("beta", "β", "number"),
            col("total", L(lang, "Численность", "Саны"), "integer"), col("total_lo", "2,5 %", "integer"), col("total_hi", "97,5 %", "integer"),
            col("fish_t", L(lang, "Промысловая биомасса, т", "Кәсіптік биомасса, т"), "number"), col("pdu_t", L(lang, "ПДУ, т", "ШРА, т"), "number"),
            col("pdu_lo", "ПДУ 2,5 %", "number"), col("pdu_hi", "ПДУ 97,5 %", "number"), col("pdu_pcs", L(lang, "ПДУ, штук", "ШРА, дана"), "integer"),
            col("removal", L(lang, "Изъятие β·ПДУ, т", "Алу β·ШРА, т"), "number")]
    if sc == "baranov":
        cols += [col("F", "F", "number"), col("M", "M̄", "number")]
    return {"columns": cols, "rows": rows, "default_view": "table", "chart": None, "toggles": toggles,
            "notes": [L(lang, f"Медиана и 95 % интервал по {R.get('n_draws')} траекториям.", f"{R.get('n_draws')} траектория бойынша медиана және 95 % аралық.")],
            **_fcommon(D, meta, code, _scen_title(sc, lang))}


VIEWS.update({"fc_species": v_fc_species, "fc_tiles": v_fc_tiles, "fc_total": v_fc_total, "fc_biomass": v_fc_biomass, "fc_pdu": v_fc_pdu,
              "fc_ages": v_fc_ages, "fc_pdu_ages": v_fc_pdu_ages, "fc_table": v_fc_table})


# ================================================================== «Можно ли верить запасу» (сводка уловистости)
# Только сравнения чисел, уже посчитанных запуском (этапы 1–2); пороги — «Правила замечаний» (группа «Уловистость»).
def _plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _at_bound(c, lo, hi, tol_lo, tol_hi=1e-3):
    if c is None:
        return False
    return abs(c - lo) <= tol_lo or abs(c - hi) <= tol_hi


_INTERNAL = ("_flagged", "_N", "_Np", "_ages", "_fs", "_fn")


def _trust_ctx(D, opt, rules=None):
    """Данные и пороги для проверок уловистости (сводка, паспорт, подробные слайды)."""
    from .insights import rule_params, RULES_BY
    rules = rules or {}
    lang = D.lang
    seine, meta = _payload(D, "seine")
    net, _ = _payload(D, "net")
    st, _ = _stock(D)
    G = st["gears"]
    y, years = _year(st, opt)
    yi = years.index(y)
    names = _names(D)
    en_b, p_b = rule_params(rules, "catch_bounds_share")
    en_g, p_g = rule_params(rules, "gears_disagree")
    en_c, p_c = rule_params(rules, "cohort_growth")
    en_r, p_r = rule_params(rules, "fit_r2_low")
    en_s, p_s = rule_params(rules, "small_sample")
    R = float(p_g["ratio"])
    grow = float(p_c["growth"])
    grow_words = (L(lang, "больше чем вдвое", "екі еседен артық") if abs(grow - 100) < 1e-9
                  else L(lang, f"больше чем на {nf(grow, 0)} %", f"{nf(grow, 0)} %-дан артық"))
    gear_w = {"seine": L(lang, "невод", "сүзекі"), "net": L(lang, "сеть", "ау")}
    return dict(locals())


def _trust_row(ctx, key, sp, y, yi):
    """Проверки вида за год: строка сводки и плоская строка для Excel; None — нет запаса за год."""
    from .insights import RULES_BY
    D, lang, seine, net, G, names = ctx["D"], ctx["lang"], ctx["seine"], ctx["net"], ctx["G"], ctx["names"]
    en_b, p_b, en_g, p_g, en_c, p_c = ctx["en_b"], ctx["p_b"], ctx["en_g"], ctx["p_g"], ctx["en_c"], ctx["p_c"]
    en_r, p_r, en_s, p_s = ctx["en_r"], ctx["p_r"], ctx["en_s"], ctx["p_s"]
    R, grow, grow_words, gear_w = ctx["R"], ctx["grow"], ctx["grow_words"], ctx["gear_w"]
    code = names.get(key.strip().lower(), key)
    ages = sp["ages"]
    mb = sp["variants"]["with_ages"]["on_stock"]
    stock_y = mb["by_age"][G["mean"]][yi] if yi < len(mb["by_age"][G["mean"]]) else None
    if not stock_y:
        return None
    N = dict(zip(ages, stock_y))
    Np = dict(zip(ages, mb["by_age"][G["mean"]][yi - 1])) if yi > 0 else None
    fs = (seine["fits"].get(key) or {}).get(str(y))
    fn = (net["fits"].get(key) or {}).get(str(y))
    # 1. запас на границах уловистости
    flagged, gears_f, fl_s, fl_n = [], set(), set(), set()
    if fs:
        for i, (j, c) in enumerate(zip(fs["ages"], fs["c"])):
            lo = seine.get("c_lower_first") if i == 0 else seine.get("c_lower")
            if _at_bound(c, lo, seine.get("c_upper"), 1e-4 if i == 0 else 1e-3):
                flagged.append(j)
                fl_s.add(j)
                gears_f.add("seine")
    if fn:
        for j, c in zip(fn["ages"], fn["c"]):
            if _at_bound(c, net.get("c_lower"), net.get("c_upper"), 1e-3):
                if j not in flagged:
                    flagged.append(j)
                fl_n.add(j)
                gears_f.add("net")
    flagged.sort()
    tot = sum(v for v in stock_y if v)
    b_pct = sum(N.get(j) or 0 for j in flagged) / tot * 100 if tot else None
    b_hit = en_b and b_pct is not None and b_pct > p_b["pct"]
    b_ages = ", ".join(age_label(j) for j in flagged)
    b_gear = ", ".join(gear_w[g] for g in ("seine", "net") if g in gears_f)
    # 2. согласие орудий
    tn, ts = mb["totals"][G["net"]], mb["totals"][G["seine"]]
    vn, vs = tn[yi], ts[yi]
    one_gear = not any(v for v in tn) or not any(v for v in ts)
    ratio = (vs / vn) if (not one_gear and vn and vs is not None) else None
    rs = sorted(s_ / n_ for s_, n_ in zip(ts, tn) if n_ and s_)
    r_med = (rs[len(rs) // 2] if len(rs) % 2 else (rs[len(rs) // 2 - 1] + rs[len(rs) // 2]) / 2) if rs else None
    g_hit = en_g and ratio is not None and (ratio > R or ratio < 1 / R)
    # 3. проверка поколений
    coh, best = [], None
    if Np is not None:
        for j in ages:
            prev, cur = Np.get(j - 1), N.get(j)
            if prev and prev > 0 and cur is not None:
                grew = cur > prev * (1 + grow / 100)
                coh.append(grew)
                x = cur / prev
                if best is None or x > best[0]:
                    best = (x, j)
    k, n = sum(coh), len(coh)
    c_hit = en_c and n > 0 and k / n * 100 > p_c["share"]
    # 4. качество проб
    n_s = fs.get("n_sample") if fs else None
    r2 = fs.get("r2") if fs else None
    pooled = bool(fs and "проба за все годы" in str(fs.get("status") or ""))
    small = en_s and not pooled and n_s is not None and n_s < p_s["min_fish"]
    r2low = en_r and r2 is not None and r2 < p_r["r2"]
    n_net = fn.get("n_sample") if fn else None
    # 5. вывод
    items, short = [], []
    if pooled:
        items.append(L(lang, "проба за все годы — параметры года взяты из сводной пробы", "барлық жылдардың сынамасы — жыл параметрлері жиынтық сынамадан алынды"))
        short.append(("all", L(lang, "проба за все годы", "барлық жылдар сынамасы")))
    if b_hit:
        gw = L(lang, "невода" if gears_f == {"seine"} else "сети" if gears_f == {"net"} else "невода и сети",
               "сүзекінің" if gears_f == {"seine"} else "аудың" if gears_f == {"net"} else "сүзекі мен аудың")
        items.append(L(lang, f"{nf(b_pct, 0)} % запаса — возрасты {b_ages}, где уловистость {gw} на границе",
                       f"қордың {nf(b_pct, 0)} %-ы — {gw} аулағыштығы шекте тұрған {b_ages} жастары"))
        short.append(("bounds", L(lang, "границы", "шектер")))
    if g_hit:
        items.append(L(lang, f"невод даёт в {nf(ratio, 1)} раза больше сети", f"сүзекі аудан {nf(ratio, 1)} есе көп береді") if ratio >= 1
                     else L(lang, f"сеть даёт в {nf(1 / ratio, 1)} раза больше невода", f"ау сүзекіден {nf(1 / ratio, 1)} есе көп береді"))
        short.append(("gears", L(lang, "орудия", "құралдар")))
    if c_hit:
        items.append(L(lang, f"{k} из {n} поколений выросли за год {grow_words} (наибольший рост ×{nf(best[0], 1)})",
                       f"{n} ұрпақтың {k}-і бір жылда {grow_words} өсті (ең үлкен өсу ×{nf(best[0], 1)})"))
        short.append(("cohorts", L(lang, "поколения", "ұрпақтар")))
    if small:
        items.append(L(lang, f"в пробе {nf(n_s, 0)} рыб", f"сынамада {nf(n_s, 0)} балық"))
        short.append(("small", L(lang, "мало рыб", "балық аз")))
    if r2low:
        items.append(L(lang, f"R² подгонки {nf(r2, 2)}", f"сәйкестендіру R² {nf(r2, 2)}"))
        short.append(("r2", L(lang, "R² низкий", "R² төмен")))
    off = [RULES_BY[c]["title_ru"] if lang != "kk" else RULES_BY[c]["title_kk"]
           for c, e in (("catch_bounds_share", en_b), ("gears_disagree", en_g), ("cohort_growth", en_c), ("small_sample", en_s), ("fit_r2_low", en_r)) if not e]
    checkable = any([b_pct is not None, ratio is not None, n > 0, n_s is not None])
    level = "warning" if items else ("ok" if checkable else None)
    if items:
        phrase = L(lang, "Есть вопросы: ", "Сұрақтар бар: ") + "; ".join(items) + "."
        if len(short) >= 4:
            label = f"{len(short)} " + L(lang, _plural(len(short), "вопрос", "вопроса", "вопросов"), "сұрақ")
        elif len(short) == 1:
            label = {"all": L(lang, "Проба за все годы", "Барлық жылдар сынамасы"), "bounds": L(lang, "Границы", "Шектер"),
                     "gears": L(lang, "Орудия", "Құралдар"), "cohorts": L(lang, "Поколения растут", "Ұрпақтар өседі"),
                     "small": L(lang, "Мало рыб", "Балық аз"), "r2": L(lang, "R² низкий", "R² төмен")}[short[0][0]]
        else:
            txt = ", ".join(w for _, w in short)
            label = txt[0].upper() + txt[1:]
    elif checkable:
        phrase = L(lang, "Проверки пройдены: уловистость определена данными, невод и сеть согласуются, поколения не растут.",
                   "Тексерулер өтті: аулағыштық деректермен анықталған, сүзекі мен ау үйлеседі, ұрпақтар өспейді.")
        label = L(lang, "Проверки пройдены", "Тексерулер өтті")
    else:
        phrase, label = L(lang, "Нет данных для проверки.", "Тексеру үшін деректер жоқ."), "—"
    if off:
        phrase += " " + L(lang, "Не проверялось (правило отключено): ", "Тексерілмеді (ереже өшірулі): ") + ", ".join(f"«{o}»" for o in off) + "."
    stock_tot = tot
    row = {
        "_code": code, "species": D.sp_name(code), "_stock": stock_tot, "_level": level, "_reasons": [c for c, _ in short],
        "_flagged": {j: [g for g, fl in (("seine", fl_s), ("net", fl_n)) if j in fl] for j in flagged},
        "_N": N, "_Np": Np, "_ages": ages, "_fs": fs, "_fn": fn,
        "bounds": {"pct": b_pct, "ages": b_ages, "gear": b_gear, "hit": b_hit, "thr": p_b["pct"], "on": en_b,
                   "to": "k_n_curve" if gears_f == {"net"} else "k_s_curve"},
        "gears": {"ratio": ratio, "median": r_med, "one": one_gear, "hit": g_hit, "thr": R, "on": en_g, "to": "st_yearly"},
        "cohorts": {"k": k, "n": n, "flags": coh, "hit": c_hit, "on": en_c, "to": "st_ages",
                    "best": {"x": best[0], "from": age_label(best[1] - 1), "to_age": age_label(best[1]), "y0": y - 1, "y1": y} if best else None},
        "sample": {"n": n_s, "r2": r2, "pooled": pooled, "small": small, "r2low": r2low, "n_net": n_net if n_net != n_s else None, "to": "k_s_tiles"},
        "verdict": {"level": level, "label": label, "phrase": phrase},
    }
    return row, {"species": row["species"], "b_pct": b_pct, "b_ages": (b_ages + (" · " + b_gear if b_gear else "")) if b_ages else "—",
                 "ratio": ratio, "r_med": r_med, "coh": f"{k} / {n}" if n else "—", "best": best[0] if best else None,
                 "n_s": n_s, "r2": r2, "pooled": L(lang, "да", "иә") if pooled else "—", "verdict": label, "phrase": phrase, "_code": code}


def v_ca_trust(D, opt, rules=None):
    ctx = _trust_ctx(D, opt, rules)
    lang, st, meta, y, years, yi = ctx["lang"], ctx["st"], ctx["meta"], ctx["y"], ctx["years"], ctx["yi"]
    p_b, R, p_c, p_r, p_s, grow_words = ctx["p_b"], ctx["R"], ctx["p_c"], ctx["p_r"], ctx["p_s"], ctx["grow_words"]
    rows, flat = [], []
    for key, sp in st["species"].items():
        res = _trust_row(ctx, key, sp, y, yi)
        if res:
            rows.append({k: v for k, v in res[0].items() if k not in _INTERNAL})
            flat.append(res[1])
    if not rows:
        raise NoData(L(lang, f"За {y} г. нет запаса по видам", f"{y} ж. түрлер бойынша қор жоқ"))
    order = sorted(range(len(rows)), key=lambda i: -(rows[i]["_stock"] or 0))
    rows = [rows[i] for i in order]
    flat = [flat[i] for i in order]
    ok = sum(1 for r in rows if r["_level"] == "ok")
    cnt = {}
    for r in rows:
        for c in r["_reasons"]:
            cnt[c] = cnt.get(c, 0) + 1
    reason_w = {"bounds": L(lang, "запас на границах уловистости", "қор аулағыштық шектерінде"), "gears": L(lang, "расходятся невод и сеть", "сүзекі мен ау алшақ"),
                "cohorts": L(lang, "растут поколения", "ұрпақтар өседі"), "all": L(lang, "проба за все годы", "барлық жылдар сынамасы"),
                "small": L(lang, "мало рыб в пробе", "сынамада балық аз"), "r2": L(lang, "слабая подгонка", "әлсіз сәйкестендіру")}
    imp = ["all", "bounds", "gears", "cohorts", "small", "r2"]          # при равенстве — более важная причина
    top = max(cnt, key=lambda c: (cnt[c], -imp.index(c))) if cnt else None
    head = L(lang, f"Проверки пройдены у {ok} из {len(rows)} видов", f"{len(rows)} түрдің {ok}-інде тексерулер өтті") + \
        (f" · {L(lang, 'чаще всего', 'жиі')} {reason_w[top]}" if top else "")
    thr = L(lang, "Пороги: ", "Шектер: ") + " · ".join([
        f"{nf(p_b['pct'], 0)} %", f"{nf(R, 1).rstrip('0').rstrip(',')}×",
        L(lang, f"рост {grow_words} у {nf(p_c['share'], 0)} % поколений", f"ұрпақтардың {nf(p_c['share'], 0)} %-ында {grow_words} өсу"),
        f"R² {nf(p_r['r2'], 2).rstrip('0').rstrip(',')}", L(lang, f"{nf(p_s['min_fish'], 0)} рыб", f"{nf(p_s['min_fish'], 0)} балық")])
    cols = [col("species", L(lang, "Вид", "Түр")), col("b_pct", L(lang, "Запас на границах, %", "Шектердегі қор, %"), "number"),
            col("b_ages", L(lang, "Возрасты на границе", "Шектегі жастар")), col("ratio", L(lang, "Невод ÷ сеть, раз", "Сүзекі ÷ ау, есе"), "number"),
            col("r_med", L(lang, "Обычно (медиана по годам), раз", "Әдетте (жылдар медианасы), есе"), "number"),
            col("coh", L(lang, "Поколения выросли", "Өскен ұрпақтар")), col("best", L(lang, "Наибольший рост, раз", "Ең үлкен өсу, есе"), "number"),
            col("n_s", L(lang, "Рыб в пробе", "Сынамадағы балық"), "integer"), col("r2", "R²", "number"),
            col("pooled", L(lang, "Проба за все годы", "Барлық жылдар сынамасы")), col("verdict", L(lang, "Вывод", "Қорытынды")),
            col("phrase", L(lang, "Пояснение", "Түсініктеме"))]
    return {"trust": {"rows": rows, "head": head, "thresholds": thr, "year": y}, "columns": cols, "rows": flat,
            "default_view": "trust", "chart": None, "row_action": "species",
            "notes": [L(lang, "Запас — вариант, по которому распределяется ПДУ (уловистость по возрастам, по запасам); переключатели вкладки «Запасы» сводку не меняют.",
                        "Қор — ШРА бөлінетін нұсқа (жастар бойынша аулағыштық, қорлар бойынша); «Қорлар» қойындысының ауыстырғыштары жиынтықты өзгертпейді.")],
            **_common(D, meta, years, y, None, "seine", "catchability-trust")}


VIEWS["ca_trust"] = v_ca_trust



# ================================================================== Проверки уловистости подробно (часть Б)
# Те же сравнения, что в сводке, — по годам и по возрастам одного вида. Новых формул нет.
def _tsp(D, opt, rules):
    ctx = _trust_ctx(D, opt, rules)
    code = opt.get("species")
    if not code:
        raise NoData(L(D.lang, "Выберите вид кнопкой под шапкой", "Тақырыптың астындағы түймемен түрді таңдаңыз"))
    st = ctx["st"]
    key = _key_for(D, {"fits": st["species"]}, code)
    if key is None:
        raise NoData(L(D.lang, f"Вид «{D.sp_name(code)}» не входит в расчёт запаса этого водоёма",
                       f"«{D.sp_name(code)}» түрі осы су айдынының қор есебіне кірмейді"))
    return ctx, key, st["species"][key], code


def _by_year(ctx, key, sp):
    out = {}
    for i, yy in enumerate(ctx["years"]):
        r = _trust_row(ctx, key, sp, yy, i)
        if r:
            out[yy] = r[0]
    return out


def _tcommon(D, ctx, code):
    y = ctx["y"]
    return {"meta": ctx["meta"], "year": y, "year_choices": ctx["years"], "calc_year": True, "help": "catchability-trust",
            "species_shown": code, "filter_label": f"{D.sp_name(code)} · {y}" if code else str(y)}


def _yr(lang):
    return L(lang, "Год", "Жыл")


def _gw(lang, gears):
    w = {"seine": L(lang, "невод", "сүзекі"), "net": L(lang, "сеть", "ау")}
    return ", ".join(w[g] for g in gears) if gears else "—"


# ---- 1. на чём держится запас: по годам
def v_ca_bounds_years(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang, years, y = ctx["lang"], ctx["years"], ctx["y"]
    R = _by_year(ctx, key, sp)
    thr = ctx["p_b"]["pct"]
    vals = [None if yy not in R or R[yy]["bounds"]["pct"] is None else round(R[yy]["bounds"]["pct"], 1) for yy in years]
    series = [{"name": L(lang, "Запас на границах уловистости, %", "Аулағыштық шектеріндегі қор, %"), "values": vals, "type": "line", "c": 0, "bold": True}]
    if ctx["en_b"]:
        series.append({"name": L(lang, f"Порог правила — {nf(thr, 0)} %", f"Ереже шегі — {nf(thr, 0)} %"), "values": [thr] * len(years),
                       "type": "line", "c": 3, "dash": True})
    rows = []
    for yy in years:
        b = (R.get(yy) or {}).get("bounds") or {}
        rows.append({"year": yy, "_current": yy == y, "pct": b.get("pct"), "ages": b.get("ages") or "—", "gear": b.get("gear") or "—",
                     "_level": "warning" if b.get("hit") else None})
    hit = [yy for yy in years if ((R.get(yy) or {}).get("bounds") or {}).get("hit")]
    return {"chart": {"kind": "fit", "x": years, "series": series, "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True,
                      "x_title": _yr(lang), "y_title": L(lang, "% запаса", "қордың %-ы")},
            "columns": [col("year", _yr(lang), "integer"), col("pct", L(lang, "Запас на границах, %", "Шектердегі қор, %"), "number"),
                        col("ages", L(lang, "Возрасты на границе", "Шектегі жастар")), col("gear", L(lang, "Орудие", "Құрал"))],
            "rows": rows, "row_action": "year", "hit_years": hit, "threshold": thr,
            "notes": [L(lang, "Доля окончательного запаса вида в возрастах, где уловистость невода или сети равна своей границе. Щелчок по точке или строке выбирает год.",
                        "Сүзекі не ау аулағыштығы өз шегіне тең жастардағы түрдің түпкілікті қор үлесі. Нүктені не жолды басу жылды таңдайды.")],
            **_tcommon(D, ctx, code)}


# ---- 1. на чём держится запас: по возрастам выбранного года
def v_ca_bounds_ages(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang, y, yi = ctx["lang"], ctx["y"], ctx["yi"]
    r = _trust_row(ctx, key, sp, y, yi)
    if not r:
        raise NoData(L(lang, f"За {y} г. нет запаса вида", f"{y} ж. түр қоры жоқ"))
    r = r[0]
    ages, N, fl = r["_ages"], r["_N"], r["_flagged"]
    cs = dict(zip((r["_fs"] or {}).get("ages") or [], (r["_fs"] or {}).get("c") or []))
    cn = dict(zip((r["_fn"] or {}).get("ages") or [], (r["_fn"] or {}).get("c") or []))
    x = [age_label(j) for j in ages]
    data = [None if j in fl else N.get(j) for j in ages]
    bnd = [N.get(j) if j in fl else None for j in ages]
    series = [{"name": L(lang, "уловистость по данным", "деректер бойынша аулағыштық"), "values": data, "type": "bar", "c": 0, "stack": "s"},
              {"name": L(lang, "уловистость на границе", "аулағыштық шекте"), "values": bnd, "type": "bar", "warn": True, "stack": "s"}]
    rows = [{"age": age_label(j), "stock": N.get(j), "c_s": cs.get(j), "c_n": cn.get(j), "bound": _gw(lang, fl.get(j)),
             "_level": "warning" if j in fl else None} for j in ages]
    return {"chart": {"kind": "fit", "x": x, "series": series, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": L(lang, "Запас, шт", "Қор, дана")},
            "columns": [col("age", L(lang, "Возраст", "Жас")), col("stock", L(lang, "Окончательный запас, шт", "Түпкілікті қор, дана"), "integer"),
                        col("c_s", L(lang, "c невода", "сүзекі c"), "number"), col("c_n", L(lang, "c сети", "ау c"), "number"),
                        col("bound", L(lang, "На границе", "Шекте"))],
            "rows": rows, "bounds": r["bounds"],
            "notes": [L(lang, "Окончательный запас по возрастам (уловистость по возрастам, по запасам); жёлтым — возрасты, где уловистость задана ограничением, а не данными.",
                        "Жастар бойынша түпкілікті қор (жастар бойынша аулағыштық, қорлар бойынша); сарымен — аулағыштықты деректер емес, шектеу берген жастар.")],
            **_tcommon(D, ctx, code)}


# ---- тепловые карты отношений (рост поколений, невод ÷ сеть): цвет — по логарифму отношения, 1 — середина шкалы
def _lg(x):
    import math
    return max(-1.0, min(1.0, math.log10(x))) if x and x > 0 else None


def _growth_heat(ctx, sp, lang):
    years, G = ctx["years"], ctx["G"]
    ages = sp["ages"]
    byA = sp["variants"]["with_ages"]["on_stock"]["by_age"][G["mean"]]
    lim = 1 + ctx["grow"] / 100
    xs = ages[1:]
    cells, rows = [], []
    for i in range(1, len(years)):
        prev, cur = dict(zip(ages, byA[i - 1])), dict(zip(ages, byA[i]))
        row = {"year": years[i], "_current": years[i] == ctx["y"]}
        for xi, j in enumerate(xs):
            a, b = prev.get(j - 1), cur.get(j)
            if a and a > 0 and b is not None:
                x = b / a
                tip = (L(lang, f"{age_label(j - 1)} в {years[i - 1]}: {pieces(a)} → {age_label(j)} в {years[i]}: {pieces(b)}",
                         f"{years[i - 1]} ж. {age_label(j - 1)}: {pieces(a, 'kk')} → {years[i]} ж. {age_label(j)}: {pieces(b, 'kk')}"))
                cells.append([xi, i - 1, _lg(x), "×" + nf(x, 1), tip, bool(ctx["en_c"] and x > lim)])
                row[f"a{j}"] = round(x, 3)
        rows.append(row)
    return {"kind": "heatmap", "x": [age_label(j) for j in xs], "y": years[1:], "cells": cells, "fmt": "ratio",
            "x_title": L(lang, "Возраст в этом году, лет", "Осы жылғы жасы, жыл"), "y_title": _yr(lang),
            "value_title": L(lang, "Запас поколения к прошлому году", "Ұрпақ қорының өткен жылға қатынасы"),
            "y_is_year": True, "pick_year": True, "selected_y": ctx["y"]}, rows, xs


def _gears_heat(ctx, sp, lang):
    years, G = ctx["years"], ctx["G"]
    ages = sp["ages"]
    mb = sp["variants"]["with_ages"]["on_stock"]["by_age"]
    S, Nn = mb[G["seine"]], mb[G["net"]]
    R = ctx["R"]
    cells, rows = [], []
    for i, yy in enumerate(years):
        row = {"year": yy, "_current": yy == ctx["y"]}
        for xi, j in enumerate(ages):
            a, b = (S[i][xi] if i < len(S) else None), (Nn[i][xi] if i < len(Nn) else None)
            if a and b and a > 0 and b > 0:
                x = a / b
                tip = L(lang, f"невод {pieces(a)}, сеть {pieces(b)}", f"сүзекі {pieces(a, 'kk')}, ау {pieces(b, 'kk')}")
                cells.append([xi, i, _lg(x), ("×" + nf(x, 1)) if x >= 1 else L(lang, "сеть ×", "ау ×") + nf(1 / x, 1), tip,
                              bool(ctx["en_g"] and (x > R or x < 1 / R))])
                row[f"a{j}"] = round(x, 3)
        rows.append(row)
    return {"kind": "heatmap", "x": [age_label(j) for j in ages], "y": years, "cells": cells, "fmt": "ratio",
            "x_title": L(lang, "Возраст, лет", "Жасы, жыл"), "y_title": _yr(lang),
            "value_title": L(lang, "Запас по неводу ÷ по сети", "Сүзекі ÷ ау бойынша қор"),
            "y_is_year": True, "pick_year": True, "selected_y": ctx["y"]}, rows, ages


def _ratio_cols(lang, ages):
    return [col("year", _yr(lang), "integer")] + [col(f"a{a}", age_label(a), "number") for a in ages]


# ---- 2. проверка поколений
def v_ca_cohorts(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang = ctx["lang"]
    ch, rows, xs = _growth_heat(ctx, sp, lang)
    if not ch["cells"]:
        raise NoData(L(lang, "Нет двух соседних лет запаса — поколения сравнить не с чем", "Көрші екі жылдың қоры жоқ — ұрпақтарды салыстыратын ештеңе жоқ"))
    n = len(ch["cells"])
    k = sum(1 for c in ch["cells"] if c[5])
    return {"chart": ch, "columns": _ratio_cols(lang, xs), "rows": rows, "row_action": "year", "cohorts_total": n, "cohorts_grew": k,
            "notes": [L(lang, f"Клетка — во сколько раз запас поколения изменился за год (поколение на диагонали: возраст +1, год +1). Рамка — рост больше допуска правила ({ctx['grow_words']}). Ожидается убыль, то есть меньше ×1.",
                        f"Ұяшық — ұрпақ қоры бір жылда неше есе өзгерді (ұрпақ диагональда: жас +1, жыл +1). Жиек — ереже шегінен артық өсу ({ctx['grow_words']}). Азаю күтіледі, яғни ×1-ден аз.")],
            **_tcommon(D, ctx, code)}


# ---- 3. согласие орудий по возрастам
def v_ca_gears_age(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang = ctx["lang"]
    ch, rows, ages = _gears_heat(ctx, sp, lang)
    if not ch["cells"]:
        raise NoData(L(lang, "Нет возрастов, где запас посчитан и по неводу, и по сети", "Қор сүзекі бойынша да, ау бойынша да есептелген жастар жоқ"))
    return {"chart": ch, "columns": _ratio_cols(lang, ages), "rows": rows, "row_action": "year",
            "notes": [L(lang, f"Клетка — во сколько раз запас по неводу больше запаса по сети в этом возрасте («сеть ×» — больше сеть). Рамка — расхождение больше порога правила ({nf(ctx['R'], 1)} раза).",
                        f"Ұяшық — осы жаста сүзекі бойынша қор ау бойынша қордан неше есе көп («ау ×» — ау көп). Жиек — ереже шегінен ({nf(ctx['R'], 1)} есе) артық алшақтық.")],
            **_tcommon(D, ctx, code)}


# ---- 4. паспорт достоверности: виды × годы
def _sample_issues(r, lang):
    b, s = r["bounds"], r["sample"]
    out = []
    if s["pooled"]:
        out.append(L(lang, "проба за все годы", "барлық жылдар сынамасы"))
    if s["small"]:
        out.append(L(lang, f"мало рыб ({nf(s['n'], 0)})", f"балық аз ({nf(s['n'], 0)})"))
    if s["r2low"]:
        out.append(L(lang, f"R² {nf(s['r2'], 2)}", f"R² {nf(s['r2'], 2)}"))
    if b["hit"]:
        out.append(L(lang, f"на границах {nf(b['pct'], 0)} % запаса", f"шектерде қордың {nf(b['pct'], 0)} %-ы"))
    return out


def v_ca_passport(D, opt, rules=None):
    ctx = _trust_ctx(D, opt, rules)
    lang, years, st, y = ctx["lang"], ctx["years"], ctx["st"], ctx["y"]
    per = []
    for key, sp in st["species"].items():
        R = _by_year(ctx, key, sp)
        if R:
            last = R.get(y) or R[max(R)]
            per.append((last["_stock"] or 0, key, R))
    if not per:
        raise NoData(L(lang, "Нет запаса по видам", "Түрлер бойынша қор жоқ"))
    per.sort(key=lambda t: -t[0])
    cells, flat, ylab, codes = [], [], [], []
    for si, (_, key, R) in enumerate(per):
        any_r = next(iter(R.values()))
        ylab.append(any_r["species"])
        codes.append(any_r["_code"])
        for xi, yy in enumerate(years):
            r = R.get(yy)
            if not r:
                continue
            iss = _sample_issues(r, lang)
            s = r["sample"]
            tip = (L(lang, f"проба {nf(s['n'], 0)} рыб", f"сынама {nf(s['n'], 0)} балық") if s["n"] is not None else "") + \
                  (f"; R² {nf(s['r2'], 2)}" if s["r2"] is not None else "") + \
                  (L(lang, f"; на границах {nf(r['bounds']['pct'], 0)} %", f"; шектерде {nf(r['bounds']['pct'], 0)} %") if r["bounds"]["pct"] is not None else "")
            if iss:
                tip += "<br>" + L(lang, "Вопросы: ", "Сұрақтар: ") + ", ".join(iss)
            cells.append([xi, si, len(iss), nf(s["n"], 0) if s["n"] is not None else "—", tip, False])
            flat.append({"species": r["species"], "year": yy, "n": s["n"], "r2": s["r2"], "pooled": L(lang, "да", "иә") if s["pooled"] else "—",
                         "b_pct": r["bounds"]["pct"], "issues": ", ".join(iss) or "—", "_code": r["_code"], "_level": "warning" if iss else None})
    return {"chart": {"kind": "heatmap", "x": years, "y": ylab, "y_codes": codes, "cells": cells, "fmt": "level",
                      "x_title": _yr(lang), "y_title": L(lang, "Вид", "Түр"), "value_title": L(lang, "Вопросов", "Сұрақтар"),
                      "x_is_year": True, "pick_year": True, "selected_y": y},
            "columns": [col("species", L(lang, "Вид", "Түр")), col("year", _yr(lang), "integer"), col("n", L(lang, "Рыб в пробе", "Сынамадағы балық"), "integer"),
                        col("r2", "R²", "number"), col("pooled", L(lang, "Проба за все годы", "Барлық жылдар сынамасы")),
                        col("b_pct", L(lang, "Запас на границах, %", "Шектердегі қор, %"), "number"), col("issues", L(lang, "Вопросы", "Сұрақтар"))],
            "rows": flat, "row_action": "species",
            "notes": [L(lang, "Клетка — вид и год; число — рыб в пробе невода. Жёлтая клетка — есть вопросы к пробе: проба за все годы, мало рыб, низкий R² или запас на границах уловистости. Щелчок — все данные по виду за этот год.",
                        "Ұяшық — түр мен жыл; сан — сүзекі сынамасындағы балық. Сары ұяшық — сынамаға сұрақтар бар: барлық жылдар сынамасы, балық аз, R² төмен немесе қор аулағыштық шектерінде. Басу — осы жылғы түр бойынша барлық деректер.")],
            **_tcommon(D, ctx, None)}


# ---- 5. смертность Z по годам
def _unreliable(r):
    s = r["sample"]
    return bool(s["pooled"] or s["small"] or s["r2low"])


def v_ca_z(D, opt, rules=None):
    ctx = _trust_ctx(D, opt, rules)
    lang, years, st, y, seine = ctx["lang"], ctx["years"], ctx["st"], ctx["y"], ctx["seine"]
    code = opt.get("species")
    if code:
        _, key, sp, code = _tsp(D, opt, rules)
        R = _by_year(ctx, key, sp)
        fits = seine["fits"].get(key) or {}
        z = [(fits.get(str(yy)) or {}).get("Z") for yy in years]
        bad = [z[i] if yy in R and _unreliable(R[yy]) else None for i, yy in enumerate(years)]
        series = [{"name": "Z", "values": z, "type": "line", "c": 0, "bold": True},
                  {"name": L(lang, "ненадёжный год", "сенімсіз жыл"), "values": bad, "type": "scatter", "warn": True}]
        rows = [{"year": yy, "_current": yy == y, "Z": z[i], "n": (R.get(yy) or {}).get("sample", {}).get("n"),
                 "r2": (R.get(yy) or {}).get("sample", {}).get("r2"),
                 "why": ", ".join(_sample_issues(R[yy], lang)[:3]) if yy in R and _unreliable(R[yy]) else "—",
                 "_level": "warning" if bad[i] is not None else None} for i, yy in enumerate(years)]
        cols = [col("year", _yr(lang), "integer"), col("Z", "Z", "number"), col("n", L(lang, "Рыб в пробе", "Сынамадағы балық"), "integer"),
                col("r2", "R²", "number"), col("why", L(lang, "Почему ненадёжен", "Неге сенімсіз"))]
        notes = [L(lang, "Общая смертность Z — наклон кривой улова невода. Жёлтые точки — годы, где проба за все годы, мало рыб или низкий R²: там Z не опирается на данные года.",
                   "Жалпы өлім-жітім Z — сүзекі ауланым қисығының көлбеулігі. Сары нүктелер — барлық жылдар сынамасы, балық аз немесе R² төмен жылдар: онда Z жыл деректеріне сүйенбейді.")]
        extra = {"z_bad": [yy for i, yy in enumerate(years) if bad[i] is not None]}
    else:
        per = []
        for key, sp in st["species"].items():
            R = _by_year(ctx, key, sp)
            if not R:
                continue
            fits = seine["fits"].get(key) or {}
            last = R.get(y) or R[max(R)]
            per.append((last["_stock"] or 0, last["species"], [(fits.get(str(yy)) or {}).get("Z") for yy in years]))
        if not per:
            raise NoData(L(lang, "Нет подгонки невода по видам", "Түрлер бойынша сүзекі сәйкестендіруі жоқ"))
        per.sort(key=lambda t: -t[0])
        series = [{"name": nm, "values": zz, "type": "line", "c": i} for i, (_, nm, zz) in enumerate(per)]
        rows = [{"year": yy, "_current": yy == y, **{f"s{i}": zz[k] for i, (_, nm, zz) in enumerate(per)}} for k, yy in enumerate(years)]
        cols = [col("year", _yr(lang), "integer")] + [col(f"s{i}", nm, "number") for i, (_, nm, zz) in enumerate(per)]
        notes = [L(lang, "Общая смертность Z по видам — наклон кривой улова невода. Ненадёжные годы вида видны на его слайде в разделе «Проверки».",
                   "Түрлер бойынша жалпы өлім-жітім Z — сүзекі ауланым қисығының көлбеулігі. Түрдің сенімсіз жылдары оның «Тексерулер» бөліміндегі слайдында көрінеді.")]
        extra = {}
    return {"chart": {"kind": "fit", "x": years, "series": series, "vrefs": [{"x": str(y), "label": str(y)}], "pick_year": True,
                      "x_title": _yr(lang), "y_title": "Z"},
            "columns": cols, "rows": rows, "row_action": "year", "notes": notes, **extra, **_tcommon(D, ctx, code)}


# ---- 6. кого не видит орудие
def v_ca_blind(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang, y, yi, seine, net = ctx["lang"], ctx["y"], ctx["yi"], ctx["seine"], ctx["net"]
    r = _trust_row(ctx, key, sp, y, yi)
    fs, fn = (r[0]["_fs"], r[0]["_fn"]) if r else (None, None)
    if not fs and not fn:
        raise NoData(L(lang, f"За {y} г. нет уловистости вида", f"{y} ж. түр аулағыштығы жоқ"))
    cs = dict(zip((fs or {}).get("ages") or [], (fs or {}).get("c") or []))
    cn = dict(zip((fn or {}).get("ages") or [], (fn or {}).get("c") or []))
    ages = sorted(set(cs) | set(cn))
    series = []
    if cs:
        series.append({"name": L(lang, "невод", "сүзекі"), "values": [round(cs[j] * 100, 1) if j in cs else None for j in ages], "type": "bar", "c": 0})
    if cn:
        series.append({"name": L(lang, "сеть", "ау"), "values": [round(cn[j] * 100, 1) if j in cn else None for j in ages], "type": "bar", "c": 1})
    phrases = []
    for g, f, part in (("seine", fs, seine), ("net", fn, net)):
        if not f:
            continue
        low = {}
        for i, (j, c) in enumerate(zip(f["ages"], f["c"])):
            lo = part.get("c_lower_first") if (g == "seine" and i == 0) else part.get("c_lower")
            if c is not None and lo is not None and abs(c - lo) <= (1e-4 if lo < 0.05 else 1e-3):
                low.setdefault(round(lo, 4), []).append(j)
        gname = L(lang, "Невод", "Сүзекі") if g == "seine" else L(lang, "Сеть", "Ау")
        for lo, js in sorted(low.items()):
            ages_t = ", ".join(age_label(j) for j in js)
            per100 = nf(lo * 100, 0)
            mult = nf(1 / lo, 0)
            phrases.append(L(lang, f"{gname} почти не ловит рыбу этого вида в возрасте {ages_t}: из 100 рыб попадается {per100}; запас этого возраста — улов, умноженный на {mult}.",
                             f"{gname} осы түрдің {ages_t} жасындағы балығын іс жүзінде ауламайды: 100 балықтан {per100} түседі; осы жастың қоры — {mult}-ге көбейтілген ауланым."))
    rows = [{"age": age_label(j), "s": round(cs[j] * 100, 1) if j in cs else None, "n": round(cn[j] * 100, 1) if j in cn else None,
             "ms": (1 / cs[j]) if cs.get(j) else None, "mn": (1 / cn[j]) if cn.get(j) else None} for j in ages]
    return {"chart": {"kind": "fit", "x": [age_label(j) for j in ages], "series": series, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"),
                      "y_title": L(lang, "Из 100 рыб попадает в орудие", "100 балықтан құралға түседі")},
            "columns": [col("age", L(lang, "Возраст", "Жас")), col("s", L(lang, "Невод: из 100 рыб", "Сүзекі: 100 балықтан"), "number"),
                        col("n", L(lang, "Сеть: из 100 рыб", "Ау: 100 балықтан"), "number"),
                        col("ms", L(lang, "Невод: улов умножается на", "Сүзекі: ауланым көбейтіледі"), "number"),
                        col("mn", L(lang, "Сеть: улов умножается на", "Ау: ауланым көбейтіледі"), "number")],
            "rows": rows, "blind": phrases,
            "notes": [L(lang, "Уловистость c, показанная как «из 100 рыб возраста в зоне облова попадает в орудие». Запас возраста = улов ÷ c: чем меньше рыб попадает, тем больше множитель улова.",
                        "Аулағыштық c «аулау аймағындағы жастың 100 балығынан құралға түседі» түрінде. Жас қоры = ауланым ÷ c: аз түссе, ауланым көбейткіші көп.")],
            **_tcommon(D, ctx, code)}


# ---- 7. сильное поколение или артефакт
def v_ca_strong(D, opt, rules=None):
    ctx, key, sp, code = _tsp(D, opt, rules)
    lang, y, yi, years, G = ctx["lang"], ctx["y"], ctx["yi"], ctx["years"], ctx["G"]
    r = _trust_row(ctx, key, sp, y, yi)
    if not r:
        raise NoData(L(lang, f"За {y} г. нет запаса вида", f"{y} ж. түр қоры жоқ"))
    r = r[0]
    ages, N, Np, fl = r["_ages"], r["_N"], r["_Np"] or {}, r["_flagged"]
    byA = sp["variants"]["with_ages"]["on_stock"]["by_age"][G["mean"]]
    lim = 1 + ctx["grow"] / 100
    rows, mx, mean = [], [], []
    for xi, j in enumerate(ages):
        cur = N.get(j)
        allv = [byA[i][xi] for i in range(len(years)) if i < len(byA) and byA[i][xi]]
        other = [byA[i][xi] for i in range(len(years)) if i != yi and i < len(byA) and byA[i][xi]]
        mx.append(max(other) if other else None)
        mean.append(sum(allv) / len(allv) if allv else None)
        top = bool(cur and other and cur > max(other))
        a = Np.get(j - 1)
        gx = cur / a if (cur and a and a > 0) else None
        grew = bool(ctx["en_c"] and gx is not None and gx > lim)
        bnd = bool(ctx["en_b"] and j in fl)
        why = []
        if bnd:
            why.append(L(lang, f"уловистость на границе ({_gw(lang, fl[j])})", f"аулағыштық шекте ({_gw(lang, fl[j])})"))
        if grew:
            why.append(L(lang, f"поколение выросло за год ×{nf(gx, 1)}", f"ұрпақ бір жылда ×{nf(gx, 1)} өсті"))
        if top:
            full = (L(lang, f"максимум за {len(allv)} лет — проверить: ", f"{len(allv)} жылдағы ең көп — тексеру: ") + "; ".join(why)) if why else \
                L(lang, f"максимум за {len(allv)} лет, проверки пройдены", f"{len(allv)} жылдағы ең көп, тексерулер өтті")
            verdict = L(lang, "максимум — проверить", "ең көп — тексеру") if why else L(lang, "максимум, проверки пройдены", "ең көп, тексерулер өтті")
        else:
            full, verdict = None, "—"
        rank = 1 + sum(1 for v in other if cur is not None and v > cur) if cur else None
        rows.append({"age": age_label(j), "stock": cur, "rank": f"{rank} / {len(allv)}" if rank else "—",
                     "to_mean": (cur / mean[-1]) if (cur and mean[-1]) else None, "bound": _gw(lang, fl.get(j)),
                     "growth": gx, "verdict": verdict, "_full": full, "_level": "warning" if (top and why) else None, "_top": top})
    series = [{"name": L(lang, f"запас {y} г.", f"{y} ж. қоры"), "values": [N.get(j) for j in ages], "type": "bar", "c": 0},
              {"name": L(lang, "максимум за другие годы", "басқа жылдардағы ең көп"), "values": mx, "type": "line", "c": 2, "dash": True},
              {"name": L(lang, "средняя за годы", "жылдар бойынша орташа"), "values": mean, "type": "line", "c": 3, "dash": True}]
    return {"chart": {"kind": "fit", "x": [age_label(j) for j in ages], "series": series, "x_title": L(lang, "Возраст, лет", "Жасы, жыл"),
                      "y_title": L(lang, "Запас, шт", "Қор, дана"), "default": "log"},
            "columns": [col("age", L(lang, "Возраст", "Жас")), col("stock", L(lang, "Запас, шт", "Қор, дана"), "integer"),
                        col("rank", L(lang, "Место среди лет", "Жылдар арасындағы орны")), col("to_mean", L(lang, "К средней, раз", "Орташаға, есе"), "number"),
                        col("bound", L(lang, "Уловистость на границе", "Аулағыштық шекте")), col("growth", L(lang, "Поколение за год, раз", "Ұрпақ бір жылда, есе"), "number"),
                        col("verdict", L(lang, "Вывод", "Қорытынды"))],
            "rows": rows, "default_view": "table",
            "notes": [L(lang, "Возраст, где запас года больше, чем в любом другом году, — сильное поколение или ошибка оценки. Оценке можно верить больше, если уловистость этого возраста определена данными и поколение не «выросло» за год.",
                        "Жылдың қоры кез келген басқа жылдан көп жас — күшті ұрпақ немесе бағалау қатесі. Осы жастың аулағыштығы деректермен анықталса және ұрпақ бір жылда «өспесе», бағаға көбірек сенуге болады.")],
            **_tcommon(D, ctx, code)}


VIEWS.update({"ca_bounds_years": v_ca_bounds_years, "ca_bounds_ages": v_ca_bounds_ages, "ca_cohorts": v_ca_cohorts,
              "ca_gears_age": v_ca_gears_age, "ca_passport": v_ca_passport, "ca_z": v_ca_z, "ca_blind": v_ca_blind,
              "ca_strong": v_ca_strong})
