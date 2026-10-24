"""
Представления исходных данных водоёма для мониторинга (вкладка «Исходные данные»).

Каждое представление — функция view(D, opt) → результат:
    {"columns": [...], "rows": [...]}       — таблица (вид «Таблица», выгрузка в Excel)
    "chart": {...}                          — описание графика (см. ниже)
    "tiles": [...]                          — плитки (вид «Плитки»), если уместны
    "sources": [{"dataset_type", "title", "dataset_id", "version"}] — откуда данные
    "notes": [...]                          — пояснения (что исключено из расчёта и почему)
    "drill": {"dataset_type", "x", "series", "y"} — как перейти к строкам по щелчку
Графики: series (x, series[{key, name, values, lo?, hi?}]), heatmap (x, y, cells), box, lifecycle, dual.

Ничего из этого не входит в расчёт ПДУ: это описательная статистика исходных данных
(сумма, доля, среднее, медиана, квартили, 95 % интервал среднего = среднее ± 1,96·σ/√n).
"""
from __future__ import annotations

import math
import re
import statistics as st
from collections import Counter, OrderedDict, defaultdict

MONTHS = {"ru": ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
          "kk": ["қаң", "ақп", "нау", "сәу", "мам", "мау", "шіл", "там", "қыр", "қаз", "қар", "жел"]}

T = {  # подписи RU / KK
    "year": ("Год", "Жыл"), "hauls": ("Ловов", "Аулау"), "cpue_net": ("Улов на 100 м сети за постановку, шт",
                                                                       "Бір қоюға 100 м ауға ауланым, дана"),
    "cpue_seine": ("Улов на 1 га облова, шт/га", "1 га ауланған аудан бойынша ауланым, дана/га"),
    "mean": ("Среднее", "Орташа"), "lo": ("95 % интервал: от", "95 % аралық: бастап"), "hi": ("до", "дейін"),
    "median": ("Медиана", "Медиана"), "n": ("Число ловов", "Аулаулар саны"), "share": ("Доля, %", "Үлесі, %"),
    "species": ("Вид", "Түр"), "place": ("Место лова", "Аулау орны"), "month": ("Месяц", "Ай"),
    "age": ("Возраст j", "Жас j"), "count": ("Число рыб", "Балық саны"), "weight": ("Средний вес, г", "Орташа салмақ, г"),
    "dev": ("Отклонение от многолетнего среднего, %", "Көпжылдық орташадан ауытқу, %"),
    "all_species": ("все виды", "барлық түрлер"), "predators": ("Хищные", "Жыртқыштар"), "peaceful": ("Мирные", "Бейбіт"),
    "scientific": ("научный лов", "ғылыми аулау"), "commercial": ("промысловый лов", "кәсіпшілік аулау"),
    "all_types": ("все типы лова", "барлық аулау түрлері"), "net": ("сеть", "ау"), "seine": ("невод", "сүзекі"),
    "quota": ("ПДУ НПЦ, т", "ҒӨО ШРА, т"), "stock_npc": ("Запас НПЦ, тыс. шт", "ҒӨО қоры, мың дана"),
    "total": ("Всего", "Барлығы"), "change": ("Изменение к прошлому году, %", "Өткен жылға өзгеріс, %"),
}


def tt(key, lang):
    v = T.get(key, (key, key))
    return v[1] if lang == "kk" else v[0]


def place_key(s) -> str:
    """Как в сервисе «Входные данные»: без регистра, пробелов, точек, дефисов и кавычек; ё = е."""
    return re.sub(r"[\s.\-–—,«»\"'()]+", "", str(s or "").lower().replace("ё", "е"))


def _r(v, d=3):
    return None if v is None else round(v, d)


# ------------------------------------------------------------------ данные водоёма
class Data:
    """Текущие версии наборов водоёма и справочники (загрузка один раз на запрос)."""

    def __init__(self, wb: str, svc: dict, lang: str = "ru"):
        self.wb, self.svc, self.lang = wb, svc, lang
        self._t, self._d = {}, {}
        self.bundle = svc["data_admin"].get(f"/bundle/{wb}") or {}

    def table(self, dtype):
        if dtype not in self._t:
            src = self.bundle.get(dtype)
            if not src:
                self._t[dtype] = (None, None)
            else:
                data = self.svc["data_admin"].get(f"/datasets/{src['dataset_id']}/data", version=src["version"])
                t = (data or {}).get("table") or {}
                self._t[dtype] = (t.get("rows") or [], {"dataset_type": dtype, "dataset_id": src["dataset_id"],
                                                         "version": src["version"], "species": t.get("species") or []})
        return self._t[dtype]

    def records(self, entity):
        if entity not in self._d:
            recs = self.svc["data_model"].get(f"/entities/{entity}/records") or []
            self._d[entity] = [r["values"] for r in recs if not r.get("deleted")]
        return self._d[entity]

    def name(self, rec):
        return (self.lang == "kk" and rec.get("name_kk")) or rec.get("name_ru") or rec.get("code")

    @property
    def species(self):
        return {s["code"]: s for s in self.records("species")}

    def sp_name(self, code):
        s = self.species.get(code)
        return self.name(s) if s else code

    @property
    def gear_kind(self):
        return {g["code"]: g.get("kind") for g in self.records("gears")}

    def gear_name(self, code):
        g = next((x for x in self.records("gears") if x["code"] == code), None)
        return self.name(g) if g else code

    def catch_type_name(self, code):
        g = next((x for x in self.records("catch_types") if x["code"] == code), None)
        return self.name(g) if g else str(code)

    @property
    def places(self):
        """{ключ написания: название места} — справочник «Места лова» водоёма."""
        if "_places" not in self._d:
            m = {}
            for r in self.records("fishing_places"):
                if r.get("water_body") != self.wb:
                    continue
                for c in (r.get("name_ru"), r.get("name_kk"), *str(r.get("aliases") or "").splitlines()):
                    if c and c.strip():
                        m.setdefault(place_key(c), r["name_ru"])
            self._d["_places"] = m
        return self._d["_places"]

    def place(self, v):
        return self.places.get(place_key(v), str(v).strip()) if v not in (None, "") else None

    def run_result(self, algorithm):
        """Результат шага из запуска для мониторинга (основной, иначе последний успешный): (результат, сведения о запуске).
        (None, None) — запуска нет; (None, сведения) — в запуске нет выполненного шага."""
        key = f"_runres:{algorithm}"
        if key not in self._d:
            info = self.svc["algo_admin"].get(f"/water-bodies/{self.wb}/monitoring-run?algorithm={algorithm}") or {}
            run = info.get("run")
            out = (None, None)
            if run:
                meta = {"run_id": run["id"], "is_main": info.get("is_main"), "calculation_title": run.get("calculation_title"),
                        "run_finished_at": run.get("finished_at")}
                i = next((k for k, st_ in enumerate(run["steps"]) if st_["algorithm"] == algorithm
                          and st_.get("status") in ("done", "reused")), None)
                res = (self.svc["algo_admin"].get(f"/runs/{run['id']}/steps/{i}/result") or {}) if i is not None else None
                out = (res, meta)
            self._d[key] = out
        return self._d[key]

    def run_table(self, algorithm, table):
        """Таблица результата шага из запуска для мониторинга (основной, иначе последний успешный)."""
        res, meta = self.run_result(algorithm)
        if meta is None:
            return None, None
        t = ((res or {}).get("tables") or {}).get(table)
        return (t["rows"] if t else None), meta

    def run_payload(self, algorithm):
        """Полное представление шага (payload) из того же запуска."""
        res, meta = self.run_result(algorithm)
        if meta is None:
            return None, None
        return (res or {}).get("payload"), meta

    def source(self, dtype, titles):
        _, meta = self.table(dtype)
        if not meta:
            return None
        return {**{k: meta[k] for k in ("dataset_type", "dataset_id", "version")}, "title": titles.get(dtype, dtype)}


DTYPE_TITLES = {"catches": ("Уловы по ловам", "Аулаулар бойынша ауланым"),
                "age_samples": ("Рыбы, подвергнутые биологической обработке", "Биологиялық өңдеуден өткен балықтар"),
                "mean_weights": ("Средний вес по возрастам", "Жас бойынша орташа салмақ"),
                "species_props": ("Биологические параметры видов", "Түрлердің биологиялық параметрлері"),
                "yearly_conditions": ("Условия по годам", "Жылдар бойынша жағдайлар"),
                "npc_stock": ("Оценка запаса НПЦ", "ҒӨО қор бағасы"), "npc_pdu": ("ПДУ НПЦ", "ҒӨО ШРА")}


def _sources(D, *dtypes):
    titles = {k: (v[1] if D.lang == "kk" else v[0]) for k, v in DTYPE_TITLES.items()}
    return [s for s in (D.source(t, titles) for t in dtypes) if s]


class NoData(Exception):
    def __init__(self, message):
        self.message = message


def need(D, dtype):
    rows, meta = D.table(dtype)
    if not rows:
        titles = DTYPE_TITLES.get(dtype, (dtype, dtype))
        raise NoData(f"Нет набора «{titles[0]}» для этого водоёма")
    return rows, meta


# ------------------------------------------------------------------ уловы: общие правила
def haul_rows(D, opt):
    """Ловы с учётом фильтров: тип лова (по умолчанию научный), орудие."""
    rows, meta = need(D, "catches")
    ct = opt.get("catch_type", "scientific")
    gear = opt.get("gear")
    kinds = D.gear_kind
    out = []
    for r in rows:
        if ct not in (None, "", "all") and r.get("catch_type") != ct:
            continue
        if gear and kinds.get(r.get("gear")) != gear and r.get("gear") != gear:
            continue
        out.append(r)
    return out, meta


def haul_value(r, species, sp_codes):
    """Улов лова: выбранный вид или сумма всех учтённых видов; None — вид не учитывался."""
    if species:
        return r.get(species)
    vals = [r.get(s) for s in sp_codes if r.get(s) is not None]
    return sum(vals) if vals else None


def effort(r, kind):
    """Усилие лова: сеть — длина / 100 м (одна постановка); невод — обловленная площадь, га."""
    if kind == "net":
        L = r.get("gear_size_m")
        return L / 100.0 if L else None
    a = r.get("area_ha")
    return a if a else None


def mean_ci(vals):
    n = len(vals)
    if not n:
        return None, None, None, 0, None
    m = sum(vals) / n
    if n < 2:
        return m, None, None, n, st.median(vals)
    se = st.stdev(vals) / math.sqrt(n)
    return m, max(0.0, m - 1.96 * se), m + 1.96 * se, n, st.median(vals)


def _years(rows):
    return sorted({r["year"] for r in rows if isinstance(r.get("year"), int)})


def _filter_note(D, opt):
    ct = opt.get("catch_type", "scientific")
    label = tt("all_types", D.lang) if ct in (None, "", "all") else D.catch_type_name(ct)
    return label


# ------------------------------------------------------------------ 1. Уловы
def v_cpue(D, opt):
    kind = opt.get("gear_kind", "net")
    rows, meta = haul_rows(D, {**opt, "gear": kind})
    sp = opt.get("species")
    spc = meta["species"]
    years = _years(rows)
    per_year = defaultdict(list)
    skipped_effort = skipped_missing = 0
    for r in rows:
        v = haul_value(r, sp, spc)
        if v is None:
            skipped_missing += 1
            continue
        e = effort(r, kind)
        if not e:
            skipped_effort += 1
            continue
        per_year[r["year"]].append(v / e)
    lang = D.lang
    out_rows = []
    m_, lo_, hi_ = [], [], []
    for y in years:
        m, lo, hi, n, med = mean_ci(per_year.get(y, []))
        out_rows.append({"year": y, "mean": _r(m), "lo": _r(lo), "hi": _r(hi), "median": _r(med), "n": n})
        m_.append(_r(m)), lo_.append(_r(lo)), hi_.append(_r(hi))
    unit = tt("cpue_net" if kind == "net" else "cpue_seine", lang)
    notes = []
    if skipped_effort:
        notes.append(f"Без {'длины сети' if kind == 'net' else 'площади облова'} — не учтено ловов: {skipped_effort}")
    if skipped_missing:
        notes.append(f"Вид не учитывался — не учтено ловов: {skipped_missing}")
    name = D.sp_name(sp) if sp else tt("all_species", lang)
    return {
        "columns": [col("year", tt("year", lang), "integer"), col("mean", tt("mean", lang), "number", unit),
                    col("lo", tt("lo", lang), "number"), col("hi", tt("hi", lang), "number"),
                    col("median", tt("median", lang), "number"), col("n", tt("n", lang), "integer")],
        "rows": out_rows,
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": unit, "default": "line",
                  "allowed": ["line", "bar"],
                  "series": [{"key": "mean", "name": name, "values": m_, "lo": lo_, "hi": hi_}]},
        "tiles": _last_tiles(years, m_, unit, lang),
        "notes": notes, "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "fixed": {"gear_kind": kind}},
        "filter_label": f"{_filter_note(D, opt)} · {tt(kind, lang)}",
    }


def _last_tiles(years, values, unit, lang):
    pts = [(y, v) for y, v in zip(years, values) if v is not None]
    if not pts:
        return []
    (y1, v1) = pts[-1]
    tiles = [{"label": str(y1), "value": v1, "unit": unit}]
    prev = [v for _, v in pts[:-1]][-5:]
    if prev:
        avg = sum(prev) / len(prev)
        tiles.append({"label": "среднее за предыдущие 5 лет" if lang != "kk" else "алдыңғы 5 жылдың орташасы",
                      "value": _r(avg), "unit": unit})
        if avg:
            tiles.append({"label": "к среднему" if lang != "kk" else "орташаға", "value": _r((v1 / avg - 1) * 100, 1),
                          "unit": "%", "signed": True})
    tiles.append({"label": "минимум ряда" if lang != "kk" else "қатардың ең азы",
                  "value": min(v for _, v in pts), "unit": unit})
    tiles.append({"label": "максимум ряда" if lang != "kk" else "қатардың ең көбі",
                  "value": max(v for _, v in pts), "unit": unit})
    return tiles


def col(code, title, type_="string", unit=None):
    return {"code": code, "title": title, "type": type_, "unit": unit}


def v_composition(D, opt):
    rows, meta = haul_rows(D, opt)
    spc = meta["species"]
    years = _years(rows)
    tot = defaultdict(lambda: defaultdict(float))
    for r in rows:
        for s in spc:
            if r.get(s) is not None:
                tot[r["year"]][s] += r[s]
    present = [s for s in spc if any(tot[y][s] for y in years)]
    series, out_rows = [], []
    for s in present:
        vals = []
        for y in years:
            t = sum(tot[y].values())
            vals.append(_r(tot[y][s] / t * 100, 2) if t else None)
        series.append({"key": s, "name": D.sp_name(s), "values": vals})
    for y in years:
        t = sum(tot[y].values())
        out_rows.append({"year": y, **{s: (_r(tot[y][s] / t * 100, 2) if t else None) for s in present}})
    pred = D.species
    pred_share = []
    for y in years:
        t = sum(tot[y].values())
        p = sum(v for s, v in tot[y].items() if (pred.get(s) or {}).get("is_predator"))
        pred_share.append(_r(p / t * 100, 1) if t else None)
    for r, p in zip(out_rows, pred_share):
        r["_pred"] = p
    lang = D.lang
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(s, D.sp_name(s), "number", "%") for s in present]
                   + [col("_pred", tt("predators", lang) + ", %", "number")],
        "rows": out_rows,
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": tt("share", lang), "default": "stack100",
                  "allowed": ["stack100", "bar", "line"], "series": series,
                  "extra_line": {"name": tt("predators", lang) + ", %", "values": pred_share}},
        "tiles": [{"label": f"{tt('predators', lang)}, {years[-1]}", "value": pred_share[-1], "unit": "%"}] if years else [],
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "series": "species"},
        "filter_label": _filter_note(D, opt) + (f" · {tt(opt['gear'], lang)}" if opt.get("gear") else ""),
    }


def _heat(x, y, cells, x_title, y_title, v_title, fmt="int", x_is_year=False, y_is_year=False):
    return {"kind": "heatmap", "x": x, "y": y, "cells": cells, "x_title": x_title, "y_title": y_title,
            "value_title": v_title, "fmt": fmt, "x_is_year": x_is_year, "y_is_year": y_is_year}


def v_coverage_places(D, opt):
    rows, _ = haul_rows(D, opt)
    years = _years(rows)
    cnt = Counter((r["year"], D.place(r.get("place"))) for r in rows if r.get("place"))
    places = sorted({p for _, p in cnt}, key=lambda p: (-sum(c for (y, q), c in cnt.items() if q == p), p))
    cells = [[i, j, cnt[(y, p)]] for i, y in enumerate(years) for j, p in enumerate(places) if cnt.get((y, p))]
    lang = D.lang
    out_rows = [{"place": p, **{str(y): cnt.get((y, p), 0) for y in years},
                 "_years": sum(1 for y in years if cnt.get((y, p)))} for p in places]
    regular = [p for p in places if sum(1 for y in years if cnt.get((y, p))) >= max(2, len(years) / 2)]
    return {
        "columns": [col("place", tt("place", lang))] + [col(str(y), str(y), "integer") for y in years]
                   + [col("_years", "Лет с ловами" if lang != "kk" else "Аулау болған жылдар", "integer")],
        "rows": out_rows,
        "chart": _heat(years, places, cells, tt("year", lang), tt("place", lang), tt("hauls", lang), x_is_year=True),
        "tiles": [{"label": "мест лова" if lang != "kk" else "аулау орны", "value": len(places)},
                  {"label": "постоянных (не меньше половины лет)" if lang != "kk" else "тұрақты (жылдардың жартысынан кем емес)",
                   "value": len(regular)}],
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "y": "place"},
        "filter_label": _filter_note(D, opt),
        "notes": ["Написания мест приведены к справочнику «Места лова»"] if D.places else [],
    }


def v_coverage_months(D, opt):
    rows, _ = haul_rows(D, opt)
    years = _years(rows)
    cnt = Counter((r["year"], int(r["date"][5:7])) for r in rows if r.get("date"))
    months = sorted({m for _, m in cnt})
    names = MONTHS["kk" if D.lang == "kk" else "ru"]
    cells = [[i, j, cnt[(y, m)]] for i, y in enumerate(years) for j, m in enumerate(months) if cnt.get((y, m))]
    lang = D.lang
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(f"m{m}", names[m - 1], "integer") for m in months],
        "rows": [{"year": y, **{f"m{m}": cnt.get((y, m), 0) for m in months}} for y in years],
        "chart": _heat(years, [names[m - 1] for m in months], cells, tt("year", lang), tt("month", lang),
                       tt("hauls", lang), x_is_year=True),
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "y": "month", "y_values": months},
        "filter_label": _filter_note(D, opt),
    }


def _quartiles(v):
    v = sorted(v)
    if len(v) == 1:
        return v[0], v[0], v[0]
    q = st.quantiles(v, n=4, method="inclusive")
    return q[0], q[1], q[2]


def v_haul_box(D, opt):
    rows, meta = haul_rows(D, opt)
    sp = opt.get("species")
    years = _years(rows)
    per = defaultdict(list)
    for r in rows:
        v = haul_value(r, sp, meta["species"])
        if v is not None:
            per[r["year"]].append(v)
    boxes, outliers, out_rows = [], [], []
    for i, y in enumerate(years):
        v = per.get(y, [])
        if not v:
            boxes.append(None)
            out_rows.append({"year": y, "n": 0})
            continue
        q1, med, q3 = _quartiles(v)
        iqr = q3 - q1
        lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        inside = [x for x in v if lo_f <= x <= hi_f] or v
        boxes.append([min(inside), q1, med, q3, max(inside)])
        outs = [x for x in v if x < lo_f or x > hi_f]
        outliers += [[i, x] for x in outs]
        s = sum(v)
        out_rows.append({"year": y, "n": len(v), "min": min(v), "q1": _r(q1, 1), "median": _r(med, 1), "q3": _r(q3, 1),
                         "max": max(v), "outliers": len(outs), "max_share": _r(max(v) / s * 100, 1) if s else None})
    lang = D.lang
    unit = "шт" if lang != "kk" else "дана"
    return {
        "columns": [col("year", tt("year", lang), "integer"), col("n", tt("n", lang), "integer"),
                    col("min", "Мин.", "number", unit), col("q1", "25 %", "number"), col("median", tt("median", lang), "number"),
                    col("q3", "75 %", "number"), col("max", "Макс.", "number"),
                    col("outliers", "Выбросов" if lang != "kk" else "Шығарындылар", "integer"),
                    col("max_share", "Доля самого большого лова в сумме года, %" if lang != "kk"
                        else "Ең үлкен аулаудың жыл қосындысындағы үлесі, %", "number")],
        "rows": out_rows,
        "chart": {"kind": "box", "x": years, "x_is_year": True, "boxes": boxes, "outliers": outliers,
                  "y_title": ("Улов за лов, шт" if lang != "kk" else "Бір аулаудағы ауланым, дана")
                  + f" · {D.sp_name(sp) if sp else tt('all_species', lang)}"},
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year"},
        "filter_label": _filter_note(D, opt) + (f" · {tt(opt['gear'], lang)}" if opt.get("gear") else ""),
    }


def v_type_compare(D, opt):
    """Научный и промысловый лов: улов на усилие (сеть) и доля хищных."""
    lang = D.lang
    series, out_rows, years_all = [], {}, set()
    for ct in ("scientific", "commercial"):
        try:
            r = v_cpue(D, {**opt, "catch_type": ct, "gear_kind": opt.get("gear_kind", "net")})
        except NoData:
            continue
        years_all |= set(r["chart"]["x"])
        series.append((ct, {row["year"]: row["mean"] for row in r["rows"]}))
    years = sorted(years_all)
    out = [{"year": y, **{ct: m.get(y) for ct, m in series}} for y in years]
    unit = tt("cpue_net" if opt.get("gear_kind", "net") == "net" else "cpue_seine", lang)
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(ct, D.catch_type_name(ct), "number", unit) for ct, _ in series],
        "rows": out,
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": unit, "default": "line", "allowed": ["line", "bar"],
                  "series": [{"key": ct, "name": D.catch_type_name(ct), "values": [m.get(y) for y in years]} for ct, m in series]},
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "series": "catch_type"},
        "filter_label": tt(opt.get("gear_kind", "net"), lang),
    }


def v_hauls_count(D, opt):
    rows, _ = haul_rows(D, {**opt, "catch_type": opt.get("catch_type", "all")})
    years = _years(rows)
    cnt = Counter((r["year"], D.gear_kind.get(r.get("gear")), r.get("catch_type")) for r in rows)
    keys = sorted({(g, c) for _, g, c in cnt}, key=lambda k: (str(k[0]), str(k[1])))
    lang = D.lang
    series = [{"key": f"{g}|{c}", "name": f"{tt(g, lang)} · {D.catch_type_name(c)}",
               "values": [cnt.get((y, g, c), 0) for y in years]} for g, c in keys]
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(s["key"], s["name"], "integer") for s in series],
        "rows": [{"year": y, **{s["key"]: s["values"][i] for s in series}} for i, y in enumerate(years)],
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": tt("hauls", lang), "default": "stack",
                  "allowed": ["stack", "bar", "line"], "series": series},
        "sources": _sources(D, "catches"),
        "drill": {"dataset_type": "catches", "x": "year", "series": "gear_kind|catch_type"},
    }


# ------------------------------------------------------------------ 2. Рыбы, подвергнутые биологической обработке
def _pick_species(D, rows, spc, opt):
    sp = opt.get("species")
    if sp:
        return sp, None
    sample, meta = D.table("age_samples")          # «самая большая проба» — по возрастным пробам
    if sample:
        rows, spc = sample, meta["species"]
    tot = {s: sum(r.get(s) or 0 for r in rows) for s in spc}
    if not tot or not any(tot.values()):
        raise NoData("Нет рыб, подвергнутых биологической обработке")
    best = max(tot, key=tot.get)
    return best, f"Вид не выбран — показан вид, у которого больше всего рыб подвергнуто биологической обработке: {D.sp_name(best)}"


def v_age_heatmap(D, opt):
    rows, meta = need(D, "age_samples")
    sp, note = _pick_species(D, rows, meta["species"], opt)
    years, ages = _years(rows), sorted({r["age"] for r in rows})
    val = {(r["year"], r["age"]): r.get(sp) for r in rows}
    share = opt.get("mode", "share") == "share"
    tot = {y: sum(val.get((y, a)) or 0 for a in ages) for y in years}
    cells, out_rows = [], []
    for i, y in enumerate(years):
        row = {"year": y, "_n": tot[y]}
        for j, a in enumerate(ages):
            v = val.get((y, a))
            if v is None:
                row[str(a)] = None
                continue
            x = _r(v / tot[y] * 100, 1) if share and tot[y] else v
            cells.append([j, i, x])
            row[str(a)] = x
        out_rows.append(row)
    lang = D.lang
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(str(a), f"j = {a}", "number", "%" if share else None)
                                                                 for a in ages] + [col("_n", tt("count", lang), "integer")],
        "rows": out_rows,
        "chart": _heat(ages, years, cells, tt("age", lang), tt("year", lang),
                       tt("share", lang) if share else tt("count", lang), "pct" if share else "int", y_is_year=True),
        "notes": [n for n in [note, "Возраст j — рыбы от j−1 до j лет. Урожайное поколение видно как яркая диагональ снизу-слева "
                                    "вверх-вправо: с каждым годом (строкой выше) оно на год старше (столбцом правее)."] if n],
        "sources": _sources(D, "age_samples"),
        "drill": {"dataset_type": "age_samples", "x": "age", "y": "year"},
        "species_shown": sp,
    }


def v_sample_size(D, opt):
    rows, meta = need(D, "age_samples")
    spc = [s for s in meta["species"] if any(r.get(s) for r in rows)]
    years = _years(rows)
    n = {(y, s): sum(r.get(s) or 0 for r in rows if r["year"] == y) if any(r.get(s) is not None for r in rows if r["year"] == y)
         else None for y in years for s in spc}
    cells = [[i, j, n[(y, s)]] for i, y in enumerate(years) for j, s in enumerate(spc) if n[(y, s)] is not None]
    lang = D.lang
    return {
        "columns": [col("species", tt("species", lang))] + [col(str(y), str(y), "integer") for y in years],
        "rows": [{"species": D.sp_name(s), **{str(y): n[(y, s)] for y in years}} for s in spc],
        "chart": _heat(years, [D.sp_name(s) for s in spc], cells, tt("year", lang), tt("species", lang), tt("count", lang),
                       x_is_year=True),
        "sources": _sources(D, "age_samples"),
        "drill": {"dataset_type": "age_samples", "x": "year"},
        "threshold_rule": "small_sample",
    }


def _props(D):
    rows, _ = D.table("species_props")
    return {r["species"]: r for r in rows or []}


def v_mature_share(D, opt):
    rows, meta = need(D, "age_samples")
    sp, note = _pick_species(D, rows, meta["species"], opt)
    pr = _props(D).get(sp)
    years = _years(rows)
    lang = D.lang
    shares, mean_age, out = [], [], []
    for y in years:
        yr = [(r["age"], r.get(sp)) for r in rows if r["year"] == y and r.get(sp) is not None]
        n = sum(v for _, v in yr)
        ma = _r(sum(a * v for a, v in yr) / n, 2) if n else None
        sh = _r(sum(v for a, v in yr if pr and a > pr["m0"]) / n * 100, 1) if n and pr else None
        shares.append(sh), mean_age.append(ma)
        out.append({"year": y, "share": sh, "mean_age": ma, "n": n})
    notes = [n for n in [note] if n]
    if not pr:
        notes.append("Нет m0 вида в «Биологических параметрах видов» — доля половозрелых не считается")
    else:
        notes.append(f"Половозрелые — возрастные группы старше m0 = {pr['m0']} (рыбы старше {pr['m0']} лет)")
    return {
        "columns": [col("year", tt("year", lang), "integer"),
                    col("share", "Доля половозрелых, %" if lang != "kk" else "Жыныстық жетілгендер үлесі, %", "number"),
                    col("mean_age", "Средний возраст j" if lang != "kk" else "Орташа жас j", "number"),
                    col("n", tt("count", lang), "integer")],
        "rows": out,
        "chart": {"kind": "dual", "x": years, "x_is_year": True,
                  "left": {"name": "Доля половозрелых, %" if lang != "kk" else "Жыныстық жетілгендер үлесі, %", "values": shares},
                  "right": {"name": "Средний возраст j" if lang != "kk" else "Орташа жас j", "values": mean_age}},
        "notes": notes, "sources": _sources(D, "age_samples", "species_props"),
        "drill": {"dataset_type": "age_samples", "x": "year"}, "species_shown": sp,
    }


def v_age_vs_mean(D, opt):
    rows, meta = need(D, "age_samples")
    sp, note = _pick_species(D, rows, meta["species"], opt)
    years, ages = _years(rows), sorted({r["age"] for r in rows})
    year = opt.get("year") or years[-1]
    def dist(y):
        v = {r["age"]: r.get(sp) for r in rows if r["year"] == y}
        n = sum(x or 0 for x in v.values())
        return {a: (v.get(a) or 0) / n * 100 for a in ages} if n else None
    cur = dist(year)
    others = [d for d in (dist(y) for y in years if y != year) if d]
    avg = {a: sum(d[a] for d in others) / len(others) for a in ages} if others else None
    lang = D.lang
    series = [{"key": "year", "name": str(year), "values": [_r(cur[a], 1) if cur else None for a in ages]}]
    if avg:
        series.append({"key": "avg", "name": "среднее других лет" if lang != "kk" else "басқа жылдардың орташасы",
                       "values": [_r(avg[a], 1) for a in ages]})
    return {
        "columns": [col("age", tt("age", lang), "integer"), col("year", str(year) + ", %", "number"),
                    col("avg", "Среднее других лет, %" if lang != "kk" else "Басқа жылдардың орташасы, %", "number")],
        "rows": [{"age": a, "year": series[0]["values"][i], "avg": series[1]["values"][i] if avg else None}
                 for i, a in enumerate(ages)],
        "chart": {"kind": "series", "x": ages, "x_title": tt("age", lang), "y_title": tt("share", lang), "default": "bar",
                  "allowed": ["bar", "line"], "series": series},
        "notes": [n for n in [note] if n], "sources": _sources(D, "age_samples"),
        "drill": {"dataset_type": "age_samples", "x": "age", "fixed": {"year": year}}, "species_shown": sp,
    }


# ------------------------------------------------------------------ 3. Средний вес
def v_growth(D, opt):
    rows, meta = need(D, "mean_weights")
    sp, note = _pick_species(D, rows, meta["species"], {**opt, "species": opt.get("species")}) if not opt.get("species") \
        else (opt["species"], None)
    years, ages = _years(rows), sorted({r["age"] for r in rows})
    w = {(r["year"], r["age"]): r.get(sp) for r in rows}
    last = years[-5:]
    lang = D.lang
    series = [{"key": str(y), "name": str(y), "values": [w.get((y, a)) for a in ages]} for y in last]
    lo, hi, avg = [], [], []
    for a in ages:
        v = [w[(y, a)] for y in years if w.get((y, a)) is not None]
        lo.append(min(v) if v else None), hi.append(max(v) if v else None)
        avg.append(_r(sum(v) / len(v), 1) if v else None)
    series.insert(0, {"key": "avg", "name": "многолетнее среднее (коридор — мин.–макс.)" if lang != "kk"
                      else "көпжылдық орташа (дәліз — ең аз–ең көп)", "values": avg, "lo": lo, "hi": hi})
    return {
        "columns": [col("age", tt("age", lang), "integer")] + [col(str(y), str(y), "number", "г") for y in years]
                   + [col("avg", "Среднее" if lang != "kk" else "Орташа", "number", "г")],
        "rows": [{"age": a, **{str(y): w.get((y, a)) for y in years}, "avg": avg[i]} for i, a in enumerate(ages)],
        "chart": {"kind": "series", "x": ages, "x_title": tt("age", lang), "y_title": tt("weight", lang), "default": "line",
                  "allowed": ["line"], "series": series},
        "notes": [n for n in [note] if n], "sources": _sources(D, "mean_weights"),
        "drill": {"dataset_type": "mean_weights", "x": "age", "series": "year"}, "species_shown": sp,
    }


def v_weight_dev(D, opt):
    rows, meta = need(D, "mean_weights")
    sp, note = (opt["species"], None) if opt.get("species") else _pick_species(D, rows, meta["species"], opt)
    years, ages = _years(rows), sorted({r["age"] for r in rows})
    w = {(r["year"], r["age"]): r.get(sp) for r in rows}
    avg = {}
    for a in ages:
        v = [w[(y, a)] for y in years if w.get((y, a))]
        avg[a] = sum(v) / len(v) if v else None
    cells, out = [], []
    for i, y in enumerate(years):
        row = {"year": y}
        for j, a in enumerate(ages):
            v = w.get((y, a))
            d = _r((v / avg[a] - 1) * 100, 1) if v and avg[a] else None
            row[str(a)] = d
            if d is not None:
                cells.append([j, i, d])
        out.append(row)
    lang = D.lang
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(str(a), f"j = {a}", "number", "%") for a in ages],
        "rows": out,
        "chart": _heat(ages, years, cells, tt("age", lang), tt("year", lang), tt("dev", lang), "dev", y_is_year=True),
        "notes": [n for n in [note, "Тёплые клетки — рыба тяжелее обычного для своего возраста, холодные — легче"] if n],
        "sources": _sources(D, "mean_weights"),
        "drill": {"dataset_type": "mean_weights", "x": "age", "y": "year"}, "species_shown": sp,
    }


def v_biomass_structure(D, opt):
    rows_n, meta = need(D, "age_samples")
    rows_w, _ = need(D, "mean_weights")
    sp, note = (opt["species"], None) if opt.get("species") else _pick_species(D, rows_n, meta["species"], opt)
    w = {(r["year"], r["age"]): r.get(sp) for r in rows_w}
    years, ages = _years(rows_n), sorted({r["age"] for r in rows_n})
    mass = {}
    for r in rows_n:
        n, ww = r.get(sp), w.get((r["year"], r["age"]))
        if n is not None and ww is not None:
            mass[(r["year"], r["age"])] = n * ww
    lang = D.lang
    series = []
    for a in ages:
        vals = []
        for y in years:
            t = sum(v for (yy, _), v in mass.items() if yy == y)
            vals.append(_r(mass.get((y, a), 0) / t * 100, 1) if t else None)
        if any(vals):
            series.append({"key": str(a), "name": f"j = {a}", "values": vals})
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(s["key"], s["name"], "number", "%") for s in series],
        "rows": [{"year": y, **{s["key"]: s["values"][i] for s in series}} for i, y in enumerate(years)],
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": "Доля массы, %" if lang != "kk"
                  else "Массаның үлесі, %", "default": "stack100", "allowed": ["stack100", "line"], "series": series},
        "notes": [n for n in [note, "Масса возрастной группы = число рыб, подвергнутых биологической обработке, × средний вес"] if n],
        "sources": _sources(D, "age_samples", "mean_weights"),
        "drill": {"dataset_type": "age_samples", "x": "year"}, "species_shown": sp,
    }


# ------------------------------------------------------------------ 4. Параметры видов и водоёма
def v_lifecycle(D, opt):
    pr = _props(D)
    if not pr:
        raise NoData("Нет набора «Биологические параметры видов» для этого водоёма")
    lang = D.lang
    sps = sorted(pr, key=lambda s: (pr[s]["m1"], s))
    return {
        "columns": [col("species", tt("species", lang)), col("m0", "m0 — половозрелость, лет" if lang != "kk"
                    else "m0 — жыныстық жетілу, жыл", "integer"),
                    col("m1", "m1 — максимальный возраст" if lang != "kk" else "m1 — ең жоғары жас", "integer"),
                    col("m2", "m2 — корм хищников до" if lang != "kk" else "m2 — жыртқыштарға жем", "integer"),
                    col("is_predator", "Хищник" if lang != "kk" else "Жыртқыш", "boolean")],
        "rows": [{"species": D.sp_name(s), **{k: pr[s].get(k) for k in ("m0", "m1", "m2", "is_predator")}} for s in sps],
        "chart": {"kind": "lifecycle", "species": [D.sp_name(s) for s in sps], "m0": [pr[s]["m0"] for s in sps],
                  "m1": [pr[s]["m1"] for s in sps], "m2": [pr[s]["m2"] for s in sps],
                  "predator": [bool(pr[s].get("is_predator")) for s in sps],
                  "labels": {"young": "молодь (до m0)" if lang != "kk" else "шабақтар (m0 дейін)",
                             "adult": "половозрелые (m0–m1)" if lang != "kk" else "жыныстық жетілгендер (m0–m1)",
                             "m2": "корм хищников до m2" if lang != "kk" else "m2 дейін жыртқыштарға жем",
                             "axis": "Возраст, лет" if lang != "kk" else "Жасы, жыл"}},
        "sources": _sources(D, "species_props"),
        "drill": {"dataset_type": "species_props"},
    }


PROP_COLS = [("is_predator", "Хищник", "boolean", None), ("fecundity_min", "Плодовитость мин.", "number", "икр."),
             ("fecundity_max", "Плодовитость макс.", "number", "икр."), ("k_net", "Уловистость сети", "number", None),
             ("k_seine", "Уловистость невода", "number", None), ("v_cr", "Крейсерская скорость", "number", "м/с"),
             ("fry_density", "Предельная плотность мальков", "number", "шт/м²")]


def v_species_cards(D, opt):
    pr = _props(D)
    if not pr:
        raise NoData("Нет набора «Биологические параметры видов» для этого водоёма")
    sps = sorted(pr, key=lambda s: D.sp_name(s))
    if opt.get("species"):
        sps = [s for s in sps if s == opt["species"]] or sps
    lang = D.lang
    return {
        "columns": [col("species", tt("species", lang))] + [col(k, t, ty, u) for k, t, ty, u in PROP_COLS],
        "rows": [{"species": D.sp_name(s), **{k: pr[s].get(k) for k, *_ in PROP_COLS}} for s in sps],
        "cards": [{"title": D.sp_name(s), "items": [{"label": t, "value": pr[s].get(k), "unit": u, "type": ty}
                                                    for k, t, ty, u in PROP_COLS]} for s in sps],
        "chart": None, "default_view": "tiles",
        "sources": _sources(D, "species_props"),
        "drill": {"dataset_type": "species_props"},
    }


def v_params_compare(D, opt, all_wbs: list[tuple[str, str, "Data"]] | None = None):
    """Параметры вида на разных водоёмах (all_wbs — [(код, название, Data)])."""
    sp = opt.get("species")
    lang = D.lang
    rows = []
    for code, name, d in all_wbs or []:
        pr = _props(d)
        for s, p in pr.items():
            if sp and s != sp:
                continue
            rows.append({"water_body": name, "species": D.sp_name(s), **{k: p.get(k) for k in ("m0", "m1", "m2")},
                         **{k: p.get(k) for k, *_ in PROP_COLS}, "_current": code == D.wb})
    if not rows:
        raise NoData("Нет биологических параметров видов ни на одном водоёме")
    rows.sort(key=lambda r: (r["species"], not r["_current"], r["water_body"]))
    return {
        "columns": [col("species", tt("species", lang)), col("water_body", "Водоём" if lang != "kk" else "Су айдыны"),
                    col("m0", "m0", "integer"), col("m1", "m1", "integer"), col("m2", "m2", "integer")]
                   + [col(k, t, ty, u) for k, t, ty, u in PROP_COLS],
        "rows": rows, "chart": None, "default_view": "table",
        "notes": ["Строки текущего водоёма выделены"],
        "sources": _sources(D, "species_props"),
    }


def v_conditions(D, opt):
    rows, _ = need(D, "yearly_conditions")
    years = _years(rows)
    by = {r["year"]: r for r in rows}
    lang = D.lang
    def changes(k):
        vals = [by[y].get(k) for y in years]
        return sum(1 for a, b in zip(vals, vals[1:]) if a is not None and b is not None and a != b)
    return {
        "columns": [col("year", tt("year", lang), "integer"),
                    col("lake_area_km2", "Площадь водоёма" if lang != "kk" else "Су айдынының ауданы", "number", "км²"),
                    col("net_length_m", "Длина сети" if lang != "kk" else "Ау ұзындығы", "number", "м"),
                    col("net_hours", "Время стоянки сети" if lang != "kk" else "Аудың тұру уақыты", "integer", "ч")],
        "rows": [{"year": y, **{k: by[y].get(k) for k in ("lake_area_km2", "net_length_m", "net_hours")}} for y in years],
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": "Площадь водоёма, км²" if lang != "kk"
                  else "Су айдынының ауданы, км²", "default": "line", "allowed": ["line", "bar"],
                  "series": [{"key": "lake_area_km2", "name": "Площадь водоёма, км²" if lang != "kk" else "Ауданы, км²",
                              "values": [by[y].get("lake_area_km2") for y in years]}]},
        "tiles": [{"label": "Смен длины сети" if lang != "kk" else "Ау ұзындығының өзгерістері", "value": changes("net_length_m")},
                  {"label": "Смен времени стоянки" if lang != "kk" else "Тұру уақытының өзгерістері", "value": changes("net_hours")}],
        "sources": _sources(D, "yearly_conditions"),
        "drill": {"dataset_type": "yearly_conditions", "x": "year"},
    }


# ------------------------------------------------------------------ 5. Квоты
def _year_species_table(D, dtype):
    rows, meta = need(D, dtype)
    years = _years(rows)
    by = {r["year"]: r for r in rows}
    spc = [s for s in meta["species"] if any(by[y].get(s) is not None for y in years)]
    return years, spc, by


def v_quota(D, opt):
    years, spc, by = _year_species_table(D, "npc_pdu")
    lang = D.lang
    series = [{"key": s, "name": D.sp_name(s), "values": [by[y].get(s) for y in years]} for s in spc]
    total = [_r(sum(by[y].get(s) or 0 for s in spc), 2) for y in years]
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(s, D.sp_name(s), "number", "т") for s in spc]
                   + [col("_total", tt("total", lang), "number", "т")],
        "rows": [{"year": y, **{s: by[y].get(s) for s in spc}, "_total": total[i]} for i, y in enumerate(years)],
        "chart": {"kind": "series", "x": years, "x_is_year": True, "y_title": tt("quota", lang), "default": "stack",
                  "allowed": ["stack", "line", "stack100"], "series": series,
                  "extra_line": {"name": tt("total", lang), "values": total, "same_axis": True}},
        "tiles": _last_tiles(years, total, "т", lang)[:3],
        "sources": _sources(D, "npc_pdu"), "drill": {"dataset_type": "npc_pdu", "x": "year"},
    }


def v_quota_change(D, opt):
    years, spc, by = _year_species_table(D, "npc_pdu")
    lang = D.lang
    def ch(s, i):
        a, b = by[years[i - 1]].get(s), by[years[i]].get(s)
        return _r((b / a - 1) * 100, 1) if a and b is not None else None
    out = [{"species": D.sp_name(s), **{str(y): (ch(s, i) if i else None) for i, y in enumerate(years)}} for s in spc]
    last = len(years) - 1
    vals = [ch(s, last) if last > 0 else None for s in spc]
    return {
        "columns": [col("species", tt("species", lang))] + [col(str(y), str(y), "number", "%") for y in years[1:]],
        "rows": [{k: v for k, v in r.items() if k != str(years[0])} for r in out],
        "chart": {"kind": "series", "x": [D.sp_name(s) for s in spc], "x_title": tt("species", lang),
                  "y_title": f"{tt('change', lang)} ({years[-1]})" if years else tt("change", lang), "default": "bar",
                  "allowed": ["bar"], "series": [{"key": "change", "name": str(years[-1]) if years else "", "values": vals}],
                  "signed": True},
        "tiles": [{"label": D.sp_name(s), "value": v, "unit": "%", "signed": True} for s, v in zip(spc, vals)],
        "sources": _sources(D, "npc_pdu"), "drill": {"dataset_type": "npc_pdu"},
    }


def v_quota_vs_stock(D, opt):
    yq, spq, bq = _year_species_table(D, "npc_pdu")
    try:
        ys, sps, bs = _year_species_table(D, "npc_stock")
    except NoData:
        ys, sps, bs = [], [], {}
    sp = opt.get("species")
    years = sorted(set(yq) | set(ys))
    lang = D.lang
    def val(by, y, spc):
        r = by.get(y)
        if not r:
            return None
        if sp:
            return r.get(sp)
        v = [r.get(s) for s in spc if r.get(s) is not None]
        return _r(sum(v), 2) if v else None
    q = [val(bq, y, spq) for y in years]
    s = [val(bs, y, sps) for y in years]
    return {
        "columns": [col("year", tt("year", lang), "integer"), col("quota", tt("quota", lang), "number"),
                    col("stock", tt("stock_npc", lang), "number")],
        "rows": [{"year": y, "quota": q[i], "stock": s[i]} for i, y in enumerate(years)],
        "chart": {"kind": "dual", "x": years, "x_is_year": True, "left": {"name": tt("quota", lang), "values": q, "type": "bar"},
                  "right": {"name": tt("stock_npc", lang), "values": s}},
        "notes": [f"{D.sp_name(sp) if sp else tt('all_species', lang)}; единицы разные (т и тыс. шт) — оси раздельные"],
        "sources": _sources(D, "npc_pdu", "npc_stock"), "drill": {"dataset_type": "npc_pdu", "x": "year"},
    }


# ------------------------------------------------------------------ 6. Качество данных
def v_completeness(D, opt):
    rows, meta = need(D, "catches")
    spc = meta["species"]
    years = _years(rows)
    cells, out = [], []
    for j, s in enumerate(spc):
        row = {"species": D.sp_name(s)}
        for i, y in enumerate(years):
            yr = [r for r in rows if r["year"] == y]
            rec = sum(1 for r in yr if r.get(s) is not None)
            share = _r(rec / len(yr) * 100, 0) if yr else None
            row[str(y)] = share
            if share is not None:
                cells.append([i, j, share])
        out.append(row)
    lang = D.lang
    return {
        "columns": [col("species", tt("species", lang))] + [col(str(y), str(y), "number", "%") for y in years],
        "rows": out,
        "chart": _heat(years, [D.sp_name(s) for s in spc], cells, tt("year", lang), tt("species", lang),
                       "Ловов, где вид учитывался, %" if lang != "kk" else "Түр есепке алынған аулаулар, %", "pct",
                       x_is_year=True),
        "notes": ["Пустая ячейка в данных — вид не учитывался (не ноль); 0 — учитывался, но не пойман"],
        "sources": _sources(D, "catches"), "drill": {"dataset_type": "catches", "x": "year"},
    }


def quality_issues(D, rules: dict) -> list[dict]:
    """Проблемы данных: [{issue, year, count, dataset_type, where, level}]."""
    out = []
    rows, meta = D.table("catches")
    kinds = D.gear_kind
    if rows:
        spc = meta["species"]
        empty, seine_no_area, net_area, unknown_place = Counter(), Counter(), Counter(), Counter()
        for r in rows:
            vals = [r.get(s) for s in spc]
            if vals and all(v in (None, 0) for v in vals):
                empty[r["year"]] += 1
            k = kinds.get(r.get("gear"))
            if k == "seine" and not r.get("area_ha"):
                seine_no_area[r["year"]] += 1
            if k == "net" and r.get("area_ha") not in (None,):
                net_area[r["year"]] += 1
            if D.places and r.get("place") and place_key(r["place"]) not in D.places:
                unknown_place[r["year"]] += 1
        for cnt, text, lvl, where in ((empty, "Лов без улова (все виды пусто или 0)", "info", {"_empty": True}),
                                      (seine_no_area, "Невод без площади облова", "error", {"gear_kind": "seine", "_no_area": True}),
                                      (net_area, "У сети указана площадь облова (не учитывается)", "warning",
                                       {"gear_kind": "net", "_has_area": True}),
                                      (unknown_place, "Место лова не из справочника «Места лова»", "warning", {"_unknown_place": True})):
            for y, c in sorted(cnt.items()):
                out.append({"issue": text, "year": y, "count": c, "dataset_type": "catches", "where": {"year": y, **where},
                            "level": lvl})
    rows_w, meta_w = D.table("mean_weights")
    if rows_w:
        for y in _years(rows_w):
            for s in meta_w["species"]:
                ser = sorted((r["age"], r.get(s)) for r in rows_w if r["year"] == y and r.get(s) is not None)
                bad = [a for (a0, w0), (a, w) in zip(ser, ser[1:]) if w < w0]
                if bad:
                    out.append({"issue": f"Средний вес убывает с возрастом: {D.sp_name(s)}, возраст {', '.join(map(str, bad))}",
                                "year": y, "count": len(bad), "dataset_type": "mean_weights", "where": {"year": y},
                                "level": "info"})
    rows_a, meta_a = D.table("age_samples")
    m = (rules.get("small_sample") or {})
    if rows_a and m.get("enabled", True):
        lim = (m.get("params") or {}).get("min_fish", RULES_BY["small_sample"]["params"]["min_fish"]["default"])
        for y in _years(rows_a):
            for s in meta_a["species"]:
                vals = [r.get(s) for r in rows_a if r["year"] == y and r.get(s) is not None]
                if vals and 0 < sum(vals) < lim:
                    out.append({"issue": f"Мало рыб, подвергнутых биологической обработке: {D.sp_name(s)} — {sum(vals):g} (меньше {lim})",
                                "year": y, "count": sum(vals), "dataset_type": "age_samples", "where": {"year": y},
                                "level": "warning"})
    return out


def v_quality(D, opt, rules=None):
    order = {"error": 0, "warning": 1, "info": 2}
    issues = sorted(quality_issues(D, rules or {}), key=lambda i: (order[i["level"]], i["dataset_type"], i["year"]))
    lang = D.lang
    return {
        "columns": [col("level", "Уровень" if lang != "kk" else "Деңгей"), col("issue", "Что найдено" if lang != "kk" else "Не табылды"),
                    col("year", tt("year", lang), "integer"), col("count", "Сколько" if lang != "kk" else "Саны", "integer"),
                    col("dataset", "Набор данных" if lang != "kk" else "Деректер жиынтығы")],
        "rows": [{**i, "dataset": (DTYPE_TITLES[i["dataset_type"]][1 if lang == "kk" else 0])} for i in issues],
        "chart": None, "default_view": "table",
        "tiles": [{"label": "ошибок" if lang != "kk" else "қателер", "value": sum(1 for i in issues if i["level"] == "error")},
                  {"label": "предупреждений" if lang != "kk" else "ескертулер",
                   "value": sum(1 for i in issues if i["level"] == "warning")},
                  {"label": "к сведению" if lang != "kk" else "назар аударыңыз", "value": sum(1 for i in issues if i["level"] == "info")}],
        "issues": issues,
        "sources": _sources(D, "catches", "mean_weights", "age_samples"),
        "drill": {"by_row": True},
    }


# ------------------------------------------------------------------ Обзор и замечания
def v_overview(D, opt, rules=None):
    rows, meta = D.table("catches")
    lang = D.lang
    tiles = []
    if rows:
        years = _years(rows)
        sci = sum(1 for r in rows if r.get("catch_type") == "scientific")
        places = {D.place(r.get("place")) for r in rows if r.get("place")}
        sp = [s for s in meta["species"] if any(r.get(s) for r in rows)]
        tiles += [
            {"label": "Годы наблюдений" if lang != "kk" else "Бақылау жылдары", "value": f"{years[0]}–{years[-1]}" if years else "—",
             "hint": f"{len(years)} лет" if lang != "kk" else f"{len(years)} жыл", "section": "catches"},
            {"label": "Ловов" if lang != "kk" else "Аулаулар", "value": len(rows),
             "hint": (f"научных {sci / len(rows) * 100:.0f} %" if lang != "kk" else f"ғылыми {sci / len(rows) * 100:.0f} %"),
             "section": "catches"},
            {"label": "Мест лова" if lang != "kk" else "Аулау орындары", "value": len(places), "section": "catches"},
            {"label": "Видов в уловах" if lang != "kk" else "Ауланымдағы түрлер", "value": len(sp), "section": "catches"},
        ]
    for dt, sec in (("age_samples", "ages"), ("mean_weights", "weights"), ("npc_pdu", "quota")):
        r, _ = D.table(dt)
        if r:
            ys = _years(r)
            tiles.append({"label": DTYPE_TITLES[dt][1 if lang == "kk" else 0], "value": f"{ys[0]}–{ys[-1]}" if ys else "—",
                          "section": sec})
    issues = quality_issues(D, rules or {})
    tiles.append({"label": "Замечаний к данным" if lang != "kk" else "Деректерге ескертулер",
                  "value": sum(1 for i in issues if i["level"] in ("error", "warning")), "section": "quality",
                  "level": "warning" if any(i["level"] in ("error", "warning") for i in issues) else None})
    if not tiles:
        raise NoData("Для водоёма ещё нет загруженных данных")
    return {"columns": [col("label", "Показатель" if lang != "kk" else "Көрсеткіш"), col("value", "Значение" if lang != "kk" else "Мәні")],
            "rows": [{"label": t["label"], "value": t["value"]} for t in tiles], "tiles": tiles, "chart": None,
            "default_view": "tiles", "sources": _sources(D, "catches", "age_samples", "mean_weights", "npc_pdu")}


# Правила замечаний «На что обратить внимание». Пороги — значения по умолчанию разработчика (не методика):
# их меняют пользователи в «Конструктор → Дашборды → Правила замечаний».
RULES = [
    {"code": "cpue_low", "title_ru": "Улов на усилие ниже среднего", "title_kk": "Күшке шаққандағы ауланым орташадан төмен",
     "description": "Научный лов, сеть: улов на усилие последнего года ниже среднего за предыдущие годы",
     "params": {"years": {"title": "За сколько предыдущих лет среднее", "default": 5, "min": 2, "max": 20},
                "pct": {"title": "Ниже среднего более чем на, %", "default": 30, "min": 1, "max": 100}}},
    {"code": "cpue_high", "title_ru": "Улов на усилие выше среднего", "title_kk": "Күшке шаққандағы ауланым орташадан жоғары",
     "description": "Научный лов, сеть: улов на усилие последнего года выше среднего за предыдущие годы",
     "params": {"years": {"title": "За сколько предыдущих лет среднее", "default": 5, "min": 2, "max": 20},
                "pct": {"title": "Выше среднего более чем на, %", "default": 50, "min": 1, "max": 1000}}},
    {"code": "cpue_extreme", "title_ru": "Минимум или максимум ряда", "title_kk": "Қатардың ең азы немесе ең көбі",
     "description": "Улов на усилие последнего года — самый низкий или самый высокий за все годы", "params": {}},
    {"code": "places_missing", "title_ru": "Не ловили на постоянных местах", "title_kk": "Тұрақты орындарда ауламаған",
     "description": "Место постоянное, если на нём ловили не меньше заданной доли лет",
     "params": {"share": {"title": "Постоянное место — ловили не меньше, % лет", "default": 50, "min": 10, "max": 100},
                "count": {"title": "Сообщать, если пропущено мест не меньше", "default": 1, "min": 1, "max": 50}}},
    {"code": "hauls_drop", "title_ru": "Мало научных ловов", "title_kk": "Ғылыми аулаулар аз",
     "description": "Число научных ловов последнего года меньше среднего",
     "params": {"pct": {"title": "Меньше среднего более чем на, %", "default": 30, "min": 1, "max": 100}}},
    {"code": "small_sample", "title_ru": "Мало рыб, подвергнутых биологической обработке", "title_kk": "Биологиялық өңдеуден өткен балық аз",
     "description": "Число рыб вида, подвергнутых биологической обработке за год, меньше порога",
     "params": {"min_fish": {"title": "Минимум рыб, подвергнутых биологической обработке", "default": 35, "min": 1, "max": 10000}}},
    {"code": "outlier_haul", "title_ru": "Один лов дал большую часть улова", "title_kk": "Бір аулау ауланымның көп бөлігін берді",
     "description": "Доля одного лова в годовой сумме улова вида больше порога",
     "params": {"pct": {"title": "Доля одного лова больше, %", "default": 50, "min": 10, "max": 100},
                "min_hauls": {"title": "Если ловов вида в году не меньше", "default": 5, "min": 2, "max": 1000}}},
    {"code": "weight_dev", "title_ru": "Вес сильно отличается от обычного", "title_kk": "Салмақ әдеттегіден қатты өзгеше",
     "description": "Средний вес возрастной группы последнего года отличается от многолетнего среднего",
     "params": {"pct": {"title": "Отклонение больше, %", "default": 25, "min": 1, "max": 500}}},
    {"code": "quota_change", "title_ru": "Квота сильно изменилась", "title_kk": "Квота қатты өзгерді",
     "description": "ПДУ НПЦ вида изменился к прошлому году",
     "params": {"pct": {"title": "Изменение больше, %", "default": 30, "min": 1, "max": 1000}}},
    {"code": "conditions_change", "title_ru": "Изменилась схема постановки сетей", "title_kk": "Ау қою тәртібі өзгерді",
     "description": "Длина сети или время стоянки в последнем году не такие, как в предыдущем", "params": {}},
    {"code": "data_errors", "title_ru": "Ошибки в данных", "title_kk": "Деректердегі қателер",
     "description": "Есть замечания раздела «Качество данных» уровня «ошибка» или «предупреждение»", "params": {}},
    # ---- уловистость: «Можно ли верить запасу» (предварительные значения, 22.10.2026, по данным Жайсана 2015–2024)
    {"code": "catch_bounds_share", "group": "catchability", "title_ru": "Запас задан границами уловистости",
     "title_kk": "Қор аулағыштық шектерімен берілген",
     "description": "Доля окончательного запаса вида в возрастах, где уловистость невода или сети равна своей границе "
                    "(задана ограничением, а не данными). Четверть запаса — уже существенная доля. "
                    "Предварительное значение, 22.10.2026",
     "params": {"pct": {"title": "Запас на границах уловистости больше, %", "default": 25, "min": 1, "max": 100}}},
    {"code": "gears_disagree", "group": "catchability", "title_ru": "Невод и сеть расходятся", "title_kk": "Сүзекі мен ау алшақ",
     "description": "Годовой запас по неводу и по сети отличается больше чем в заданное число раз: запас и ПДУ неопределённы "
                    "как минимум во столько же раз. Предварительное значение, 22.10.2026",
     "params": {"ratio": {"title": "Невод и сеть расходятся больше чем в, раз", "default": 2, "min": 1.1, "max": 100, "step": 0.1}}},
    {"code": "cohort_growth", "group": "catchability", "title_ru": "Поколения растут", "title_kk": "Ұрпақтар өседі",
     "description": "Поколение не может вырасти за год: ожидается убыль. Рост больше допуска у заметной доли поколений — "
                    "повод проверить уловистость и данные биологической обработки. Предварительное значение, 22.10.2026",
     "params": {"growth": {"title": "Рост поколения больше, %", "default": 100, "min": 0, "max": 1000},
                "share": {"title": "Сообщать, если выросло поколений больше, %", "default": 25, "min": 1, "max": 100}}},
    {"code": "fit_r2_low", "group": "catchability", "title_ru": "Слабая подгонка сигмоиды невода", "title_kk": "Сүзекі сигмоидасы әлсіз сәйкестендірілген",
     "description": "Кривая улова объясняет меньше заданной доли разброса — параметры года (j50, Z) ненадёжны. "
                    "Предварительное значение, 22.10.2026",
     "params": {"r2": {"title": "R² подгонки сигмоиды невода меньше", "default": 0.5, "min": 0, "max": 1, "step": 0.05}}},
    # ---- запасы: «Сходятся ли оценки запаса» (предварительные значения, 24.10.2026, по данным Жайсана 2015–2024)
    {"code": "model_vs_catch", "group": "stock", "title_ru": "Модель расходится с оценкой по уловам",
     "title_kk": "Модель ауланым бағасынан алшақ",
     "description": "Численность по модели за год отличается от окончательного запаса по уловам больше чем в заданное число раз. "
                    "Модель обучена на оценках по уловам: расхождение вдвое — модель не воспроизводит свои данные. "
                    "Предварительное значение, 24.10.2026",
     "params": {"ratio": {"title": "Модель и оценка по уловам расходятся больше чем в, раз", "default": 2, "min": 1.1, "max": 100, "step": 0.1}}},
    {"code": "model_vs_npc", "group": "stock", "title_ru": "Модель расходится с оценкой НПЦ", "title_kk": "Модель ҒӨО бағасынан алшақ",
     "description": "Численность по модели за год отличается от оценки запаса НПЦ больше чем в заданное число раз: ПДУ приложения "
                    "и официальный ПДУ НПЦ заведомо не сопоставимы. Предварительное значение, 24.10.2026",
     "params": {"ratio": {"title": "Модель и НПЦ расходятся больше чем в, раз", "default": 2, "min": 1.1, "max": 100, "step": 0.1}}},
    {"code": "trend_vs_catch", "group": "stock", "title_ru": "Модель и оценка по уловам меняются по-разному",
     "title_kk": "Модель мен ауланым бағасы әртүрлі өзгереді",
     "description": "Изменение численности по модели с первого года ряда отличается от изменения оценки по уловам больше чем в "
                    "заданное число раз: направление важнее уровня, при расхождении динамики прогноз ненадёжен. "
                    "Предварительное значение, 24.10.2026",
     "params": {"ratio": {"title": "Изменения расходятся больше чем в, раз", "default": 2, "min": 1.1, "max": 100, "step": 0.1}}},
]
RULES_BY = {r["code"]: r for r in RULES}


def rule_params(rules, code):
    r = rules.get(code) or {}
    p = {k: v["default"] for k, v in RULES_BY[code]["params"].items()}
    p.update({k: v for k, v in (r.get("params") or {}).items() if k in p and v is not None})
    return r.get("enabled", True), p


def signals(D, rules: dict) -> list[dict]:
    """Замечания «На что обратить внимание»: [{level, rule, text, section}]."""
    out = []
    lang = D.lang

    def on(code):
        return rule_params(rules, code)

    rows, meta = D.table("catches")
    if rows:
        spc = [s for s in meta["species"] if any(r.get(s) for r in rows)]
        for s in spc:
            try:
                res = v_cpue(D, {"species": s, "gear_kind": "net", "catch_type": "scientific"})
            except NoData:
                break
            pts = [(r["year"], r["mean"]) for r in res["rows"] if r["mean"] is not None]
            if len(pts) < 2:
                continue
            y1, v1 = pts[-1]
            for code, sign in (("cpue_low", -1), ("cpue_high", 1)):
                en, p = on(code)
                prev = [v for _, v in pts[:-1]][-int(p["years"]):]
                if en and prev:
                    avg = sum(prev) / len(prev)
                    if avg and sign * (v1 / avg - 1) * 100 > p["pct"]:
                        out.append({"level": "warning" if sign < 0 else "info", "rule": code, "section": "catches", "species": s,
                                    "text": f"{D.sp_name(s).capitalize()}: улов на усилие (сеть, научный лов) в {y1} году "
                                            f"{'ниже' if sign < 0 else 'выше'} среднего за {len(prev)} предыдущих лет "
                                            f"на {abs((v1 / avg - 1) * 100):.0f} %"})
            en, _ = on("cpue_extreme")
            if en and len(pts) >= 3:
                vals = [v for _, v in pts]
                if v1 == min(vals):
                    out.append({"level": "warning", "rule": "cpue_extreme", "section": "catches", "species": s,
                                "text": f"{D.sp_name(s).capitalize()}: улов на усилие в {y1} году — самый низкий за {len(pts)} лет"})
                elif v1 == max(vals):
                    out.append({"level": "info", "rule": "cpue_extreme", "section": "catches", "species": s,
                                "text": f"{D.sp_name(s).capitalize()}: улов на усилие в {y1} году — самый высокий за {len(pts)} лет"})
        sci = [r for r in rows if r.get("catch_type") == "scientific"]
        years = _years(sci)
        en, p = on("places_missing")
        if en and len(years) >= 3:
            have = defaultdict(set)
            for r in sci:
                if r.get("place"):
                    have[D.place(r["place"])].add(r["year"])
            regular = [pl for pl, ys in have.items() if len(ys) / len(years) * 100 >= p["share"]]
            for y in years:
                miss = [pl for pl in regular if y not in have[pl]]
                if len(miss) >= p["count"] and regular:
                    out.append({"level": "info", "rule": "places_missing", "section": "catches",
                                "text": f"В {y} году не ловили на {len(miss)} из {len(regular)} постоянных мест: "
                                        + ", ".join(sorted(miss)[:5]) + ("…" if len(miss) > 5 else "")})
        en, p = on("hauls_drop")
        if en and len(years) >= 3:
            cnt = Counter(r["year"] for r in sci)
            y1 = years[-1]
            avg = sum(cnt[y] for y in years[:-1]) / (len(years) - 1)
            if avg and (1 - cnt[y1] / avg) * 100 > p["pct"]:
                out.append({"level": "warning", "rule": "hauls_drop", "section": "catches",
                            "text": f"В {y1} году {cnt[y1]} научных ловов — меньше среднего ({avg:.0f}) "
                                    f"на {(1 - cnt[y1] / avg) * 100:.0f} %"})
        en, p = on("outlier_haul")
        if en:
            for y in _years(rows):
                yr = [r for r in sci if r["year"] == y]
                for s in spc:
                    v = [r.get(s) for r in yr if r.get(s) is not None]
                    tot = sum(v)
                    if len(v) >= p["min_hauls"] and tot and max(v) / tot * 100 > p["pct"]:
                        out.append({"level": "info", "rule": "outlier_haul", "section": "catches", "species": s,
                                    "text": f"{D.sp_name(s).capitalize()}, {y}: один лов дал {max(v) / tot * 100:.0f} % "
                                            f"годового научного улова ({max(v):g} из {tot:g} шт)"})
    en, p = on("small_sample")
    if en:
        r_a, m_a = D.table("age_samples")
        if r_a:
            y1 = _years(r_a)[-1]
            small, small_codes = [], []
            for s in m_a["species"]:
                v = [r.get(s) for r in r_a if r["year"] == y1 and r.get(s) is not None]
                if v and 0 < sum(v) < p["min_fish"]:
                    small.append(f"{D.sp_name(s)} — {sum(v):g}")
                    small_codes.append(s)
            if small:
                out.append({"level": "warning", "rule": "small_sample", "section": "ages", "species_list": small_codes,
                            "text": f"Рыб, подвергнутых биологической обработке в {y1} году, меньше {p['min_fish']}: " + ", ".join(small)})
    en, p = on("weight_dev")
    if en:
        r_w, m_w = D.table("mean_weights")
        if r_w:
            yrs = _years(r_w)
            y1 = yrs[-1]
            for s in m_w["species"]:
                devs = []
                for a in sorted({r["age"] for r in r_w}):
                    cur = next((r.get(s) for r in r_w if r["year"] == y1 and r["age"] == a), None)
                    oth = [r.get(s) for r in r_w if r["year"] != y1 and r["age"] == a and r.get(s)]
                    if cur and oth:
                        d = (cur / (sum(oth) / len(oth)) - 1) * 100
                        if abs(d) > p["pct"]:
                            devs.append(f"j={a}: {d:+.0f} %")
                if devs:
                    out.append({"level": "info", "rule": "weight_dev", "section": "weights", "species": s,
                                "text": f"{D.sp_name(s).capitalize()}: средний вес в {y1} году отличается от многолетнего: " + ", ".join(devs[:4])})
    en, p = on("quota_change")
    if en:
        try:
            years, spc, by = _year_species_table(D, "npc_pdu")
        except NoData:
            years = []
        if len(years) >= 2:
            a, b = years[-2], years[-1]
            for s in spc:
                x0, x1 = by[a].get(s), by[b].get(s)
                if x0 and x1 is not None and abs((x1 / x0 - 1) * 100) > p["pct"]:
                    out.append({"level": "info", "rule": "quota_change", "section": "quota", "species": s,
                                "text": f"{D.sp_name(s).capitalize()}: ПДУ НПЦ {b} года к {a} — {(x1 / x0 - 1) * 100:+.0f} % ({x0:g} → {x1:g} т)"})
    en, _ = on("conditions_change")
    if en:
        r_c, _ = D.table("yearly_conditions")
        if r_c and len(r_c) >= 2:
            ys = sorted(r_c, key=lambda r: r["year"])
            a, b = ys[-2], ys[-1]
            for k, t in (("net_length_m", "длина сети"), ("net_hours", "время стоянки сети")):
                if a.get(k) is not None and b.get(k) is not None and a[k] != b[k]:
                    out.append({"level": "warning", "rule": "conditions_change", "section": "params",
                                "text": f"В {b['year']} году изменилась {t}: {a[k]:g} → {b[k]:g}. Улов на усилие по годам "
                                        f"сравнивайте осторожно"})
    en, _ = on("data_errors")
    if en:
        iss = [i for i in quality_issues(D, rules) if i["level"] in ("error", "warning")]
        if iss:
            out.append({"level": "error" if any(i["level"] == "error" for i in iss) else "warning", "rule": "data_errors",
                        "section": "quality", "text": f"Замечаний к данным: {len(iss)} (раздел «Качество данных»)"})
    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda s: order.get(s["level"], 3))
    return out


def v_signals(D, opt, rules=None):
    sig = signals(D, rules or {})
    sp = opt.get("species")
    if sp:          # «Все данные по виду»: только замечания этого вида
        sig = [x for x in sig if x.get("species") == sp or sp in (x.get("species_list") or [])]
    lang = D.lang
    return {"columns": [col("level", "Уровень" if lang != "kk" else "Деңгей"), col("text", "Замечание" if lang != "kk" else "Ескерту")],
            "rows": [{"level": s["level"], "text": s["text"]} for s in sig], "signals": sig, "chart": None,
            "default_view": "signals", "sources": _sources(D, "catches", "age_samples", "mean_weights", "npc_pdu", "yearly_conditions"),
            "notes": ["Пороги замечаний настраиваются: Конструктор → Дашборды → Правила замечаний"]}


# ------------------------------------------------------------------ улов по ловам и возрастам (формула (20), этап 2)
def _cba(D, opt):
    rows, meta = D.run_table("stock_by_catch", "catch_by_age")
    if rows is None:
        if meta is None:
            raise NoData("Для водоёма ещё нет расчёта запаса по уловам (этап 2) — улов по возрастам появится после него")
        raise NoData("В запуске нет таблицы «Улов по ловам и возрастам» — перезапустите расчёт (алгоритм этапа 2 версии 1.0.2 и новее)")
    gear = {"net": "сеть", "seine": "невод"}.get(opt.get("gear_kind", "net"))
    ct = opt.get("catch_type", "scientific")
    ctn = {"scientific": ("научный", "scientific"), "commercial": ("промысловый", "commercial")}.get(ct)
    names = {D.sp_name(c): c for c in D.species} | {s.get("name_ru"): c for c, s in D.species.items()}
    out = [r for r in rows if (not gear or r["gear"] == gear) and (not ctn or r.get("catch_type") in ctn)]
    for r in out:
        r["_sp"] = names.get(r["species"], r["species"])
        r["_iso"] = _iso(r.get("date"))
    ages = sorted(int(k[1:]) for k in (rows[0] if rows else {}) if re.fullmatch(r"a\d+", k))
    return out, meta, ages


def _iso(d) -> str:
    """Дата лова в виде ГГГГ-ММ-ДД (в таблицах расчёта — ДД.ММ.ГГГГ)."""
    d = str(d or "")
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else d[:10]


def _ru_date(iso) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if len(iso) >= 10 else iso


def _cba_species(D, rows, opt):
    if opt.get("species"):
        return opt["species"], None
    tot = Counter()
    for r in rows:
        tot[r["_sp"]] += r.get("total") or 0
    if not tot:
        raise NoData("Нет ловов для выбранных условий")
    best = tot.most_common(1)[0][0]
    return best, f"Вид не выбран — показан вид с самым большим уловом: {D.sp_name(best)}"


HOW_20 = "method-catch-age"


def v_age_catch_year(D, opt):
    rows, meta, ages = _cba(D, opt)
    sp, note = _cba_species(D, rows, opt)
    rows = [r for r in rows if r["_sp"] == sp]
    years = sorted({r["year"] for r in rows})
    tot = {(y, a): sum(r.get(f"a{a}") or 0 for r in rows if r["year"] == y) for y in years for a in ages}
    ages = [a for a in ages if any(tot[(y, a)] for y in years)]
    cells = [[j, i, round(tot[(y, a)], 1)] for i, y in enumerate(years) for j, a in enumerate(ages) if tot[(y, a)]]
    lang = D.lang
    return {
        "columns": [col("year", tt("year", lang), "integer")] + [col(f"a{a}", f"j = {a}", "number", "шт") for a in ages]
                   + [col("_n", tt("hauls", lang), "integer")],
        "rows": [{"year": y, **{f"a{a}": round(tot[(y, a)], 1) for a in ages},
                  "_n": sum(1 for r in rows if r["year"] == y)} for y in years],
        "chart": _heat(ages, years, cells, tt("age", lang), tt("year", lang),
                       "Поймано рыб возраста j за год, шт" if lang != "kk" else "Жыл ішінде ауланған j жасындағы балық, дана",
                       "int", y_is_year=True),
        "notes": [n for n in [note, "Сумма по ловам года: Σ_d Y_ijd, где Y_ijd = Y_id · q_ij(t_d)"] if n],
        "meta": meta, "help": HOW_20,
        "drill": {"dataset_type": "catch_by_age", "y": "year", "x": "age"},
        "filter_label": f"{_filter_note(D, opt)} · {tt(opt.get('gear_kind', 'net'), lang)} · {D.sp_name(sp)}",
        "species_shown": sp,
    }


def v_age_catch_hauls(D, opt):
    rows, meta, ages = _cba(D, opt)
    sp, note = _cba_species(D, rows, opt)
    rows = [r for r in rows if r["_sp"] == sp]
    years = sorted({r["year"] for r in rows})
    if not years:
        raise NoData("Нет ловов для выбранных условий")
    year = int(opt.get("year") or years[-1])
    if year not in years:
        year = years[-1]
    yr = sorted((r for r in rows if r["year"] == year), key=lambda r: (r["_iso"], r["haul"]))
    ages = [a for a in ages if any(r.get(f"a{a}") for r in yr)] or ages[:1]
    label = lambda r: f"{r['_iso'][8:10]}.{r['_iso'][5:7]} · {D.place(r.get('place')) or '—'} · №{r['haul']}"  # noqa: E731
    ylab = [label(r) for r in yr]
    cells = [[j, i, round(r[f"a{a}"], 1)] for i, r in enumerate(yr) for j, a in enumerate(ages) if (r.get(f"a{a}") or 0) >= 0.05]
    lang = D.lang
    return {
        "columns": [col("haul", "Лов №" if lang != "kk" else "Аулау №", "integer"), col("date", "Дата" if lang != "kk" else "Күні"),
                    col("place", tt("place", lang)), col("total", "Улов вида в лове, Y_id" if lang != "kk" else "Түрдің аулаудағы ауланымы, Y_id", "number", "шт")]
                   + [col(f"a{a}", f"j = {a}", "number", "шт") for a in ages],
        "rows": [{"haul": r["haul"], "date": _ru_date(r["_iso"]), "place": D.place(r.get("place")), "total": r.get("total"),
                  **{f"a{a}": r.get(f"a{a}") for a in ages}} for r in yr],
        "chart": {**_heat(ages, ylab, cells, tt("age", lang), "Лов" if lang != "kk" else "Аулау",
                          "Улов возраста j в лове, Y_ijd, шт" if lang != "kk" else "Аулаудағы j жасының ауланымы, Y_ijd, дана", "pct"),
                  "row_keys": [r["haul"] for r in yr]},
        "notes": [n for n in [note, "Щёлкните по клетке и нажмите «Показать строки», чтобы увидеть расчёт этого лова на числах"] if n],
        "meta": meta, "help": HOW_20, "year_choices": years, "year": year,
        "drill": {"dataset_type": "catch_by_age", "y": "haul", "y_values": [r["haul"] for r in yr], "fixed": {"year": year}},
        "filter_label": f"{_filter_note(D, opt)} · {tt(opt.get('gear_kind', 'net'), lang)} · {D.sp_name(sp)} · {year}",
        "species_shown": sp,
    }


def explain_haul(D, where: dict, opt: dict) -> dict:
    """Один лов на числах: Y_ijd = Y_id · q_ij(t_d) по возрастам."""
    rows, meta, ages = _cba(D, opt)
    sp = where.get("_species") or _cba_species(D, rows, opt)[0]
    haul = where.get("haul")
    gear = {"net": "сеть", "seine": "невод"}.get(opt.get("gear_kind", "net"))
    rec = next((r for r in rows if r["haul"] == haul and r["_sp"] == sp and (not gear or r["gear"] == gear)), None)
    if not rec:
        raise NoData("Лов не найден в результатах расчёта")
    shares, _ = D.run_table("stock_by_catch", "age_shares")
    q = next((r for r in shares or [] if r["year"] == rec["year"] and r["species"] == rec["species"]), {})
    pr = _props(D).get(sp) or {}
    m1 = pr.get("m1")
    out = []
    for a in ages:
        n = q.get(f"n{a}")
        qq = q.get(f"q{a}")
        y = rec.get(f"a{a}")
        if not qq and not y:
            continue
        out.append({"age": a, "n": n, "q": qq, "Y": rec.get("total"), "Yj": y})
    lang = D.lang
    title = (f"{D.sp_name(sp).capitalize()}, лов №{haul}: {_ru_date(rec['_iso'])}, "
             f"{D.place(rec.get('place')) or '—'}, {rec['gear']}")
    return {
        "columns": [col("age", tt("age", lang), "integer"), col("n", "Подвергнуто биол. обработке, шт" if lang != "kk" else "Биол. өңдеуден өткен, дана", "number"),
                    col("q", "Доля q_ij" if lang != "kk" else "Үлес q_ij", "number"),
                    col("Y", "Y_id, шт", "number"), col("Yj", "Y_ijd = Y_id · q_ij, шт", "number")],
        "rows": out, "total": len(out), "title": title,
        "formula": f"Y_ijd = Y_id · q_ij(t_d); Y_id = {rec.get('total'):g} шт; q_ij — доли возрастов среди рыб, подвергнутых биологической обработке в {rec['year']} году, "
                   f"со сглаживанием (группы j ≤ m1{f' = {m1}' if m1 else ''}; см. справку «Улов по возрастам»); сумма по возрастам = {sum(r['Yj'] or 0 for r in out):.4g} шт",
        "dataset_id": None, "meta": meta, "help": HOW_20,
    }



# ------------------------------------------------------------------ светофор видов и журнал ловов
def v_traffic(D, opt, rules=None):
    """Светофор видов: строка — вид; улов на усилие (сеть, научный лов) за годы, последний год к среднему,
    доля в улове, доля половозрелых, вес к норме, квота к прошлому году, замечания."""
    rules = rules or {}
    rows, meta = need(D, "catches")
    sci = [r for r in rows if r.get("catch_type") == "scientific"] or rows
    tot = Counter()
    for r in sci:
        for c in meta["species"]:
            tot[c] += r.get(c) or 0
    spc = [c for c, v in tot.most_common() if v > 0]
    if opt.get("species"):
        spc = [c for c in spc if c == opt["species"]] or [opt["species"]]
    _, p_low = rule_params(rules, "cpue_low")
    _, p_high = rule_params(rules, "cpue_high")
    _, p_w = rule_params(rules, "weight_dev")
    _, p_q = rule_params(rules, "quota_change")
    years_all = _years(sci)
    y_last = years_all[-1] if years_all else None
    tot_last = sum(sum(r.get(c) or 0 for c in meta["species"]) for r in sci if r["year"] == y_last)
    sig = signals(D, rules)
    try:
        qy, qsp, qby = _year_species_table(D, "npc_pdu")
    except NoData:
        qy, qsp, qby = [], [], {}
    rw, mw = D.table("mean_weights")
    lang = D.lang
    out = []
    for c in spc:
        row = {"_code": c, "species": D.sp_name(c), "_levels": {}}
        try:
            cp = v_cpue(D, {"species": c, "gear_kind": "net", "catch_type": "scientific"})
            pts = [(r["year"], r["mean"]) for r in cp["rows"] if r["mean"] is not None]
        except NoData:
            pts = []
        row["spark"] = [v for _, v in pts]
        row["_spark_years"] = [y for y, _ in pts]
        if len(pts) >= 2:
            prev = [v for _, v in pts[:-1]][-int(p_low["years"]):]
            avg = sum(prev) / len(prev)
            ch = _r((pts[-1][1] / avg - 1) * 100, 0) if avg else None
            row["cpue_change"] = ch
            if ch is not None:
                row["_levels"]["cpue_change"] = "down" if ch < -p_low["pct"] else "up" if ch > p_high["pct"] else None
        row["share"] = _r(sum(r.get(c) or 0 for r in sci if r["year"] == y_last) / tot_last * 100, 1) if tot_last else None
        try:
            ms = v_mature_share(D, {"species": c})
            vals = [r["share"] for r in ms["rows"] if r["share"] is not None]
            row["mature"] = vals[-1] if vals else None
        except NoData:
            row["mature"] = None
        if rw:
            yw = _years(rw)
            if yw:
                devs = []
                for a in sorted({r["age"] for r in rw}):
                    cur = next((r.get(c) for r in rw if r["year"] == yw[-1] and r["age"] == a), None)
                    oth = [r.get(c) for r in rw if r["year"] != yw[-1] and r["age"] == a and r.get(c)]
                    if cur and oth:
                        devs.append((cur / (sum(oth) / len(oth)) - 1) * 100)
                if devs:
                    row["weight"] = _r(sum(devs) / len(devs), 1)
                    row["_levels"]["weight"] = "down" if row["weight"] < -p_w["pct"] else "up" if row["weight"] > p_w["pct"] else None
        if len(qy) >= 2 and c in qsp:
            a, b = qby[qy[-2]].get(c), qby[qy[-1]].get(c)
            if a and b is not None:
                row["quota"] = _r((b / a - 1) * 100, 0)
                row["_levels"]["quota"] = "down" if row["quota"] < -p_q["pct"] else "up" if row["quota"] > p_q["pct"] else None
        row["signals"] = sum(1 for x in sig if x.get("species") == c or c in (x.get("species_list") or []))
        out.append(row)
    L = lambda ru, kk: kk if lang == "kk" else ru  # noqa: E731
    cols = [col("species", tt("species", lang)),
            col("spark", L("Улов на усилие (сеть) по годам", "Күшке шаққандағы ауланым (ау) жылдар бойынша"), "spark"),
            col("cpue_change", L(f"{y_last or ''} к среднему, %", f"{y_last or ''} орташаға, %"), "number"),
            col("share", L(f"Доля в улове {y_last or ''}, %", f"{y_last or ''} ауланымдағы үлесі, %"), "number"),
            col("mature", L("Половозрелые, %", "Жыныстық жетілгендер, %"), "number"),
            col("weight", L("Вес к норме, %", "Салмақ нормаға, %"), "number"),
            col("quota", L("Квота к прошлому году, %", "Квота өткен жылға, %"), "number"),
            col("signals", L("Замечания", "Ескертулер"), "integer")]
    return {"columns": cols, "rows": out, "chart": None, "default_view": "traffic",
            "notes": [L("Улов на усилие — научный лов, сеть. Цвет: отклонение больше порогов «Правил замечаний»; "
                        "щелчок по строке открывает «Все данные по виду»",
                        "Күшке шаққандағы ауланым — ғылыми аулау, ау. Түс: «Ескерту ережелері» шектерінен үлкен ауытқу; "
                        "жолды басу «Түр бойынша барлық деректерді» ашады")],
            "sources": _sources(D, "catches", "age_samples", "mean_weights", "npc_pdu")}


def v_journal(D, opt):
    """Журнал ловов: все ловы набора с подписями, для фильтров и итогов в интерфейсе."""
    rows, meta = need(D, "catches")
    lang = D.lang
    L = lambda ru, kk: kk if lang == "kk" else ru  # noqa: E731
    kinds = D.gear_kind
    spc = [c for c in meta["species"] if any(r.get(c) is not None for r in rows)]
    sp = opt.get("species")
    if sp in spc:
        spc = [sp] + [c for c in spc if c != sp]
    out = []
    for i, r in enumerate(rows):
        d = r.get("date") or ""
        k = kinds.get(r.get("gear"))
        out.append({"_i": i, "year": r.get("year"), "date": _ru_date(d) if d else None, "_iso": d, "month": int(d[5:7]) if d else None,
                    "place": D.place(r.get("place")), "gear": D.gear_name(r.get("gear")), "_gear_kind": k,
                    "length": r.get("gear_size_m"), "area": r.get("area_ha") if k != "net" else None,
                    "catch_type": D.catch_type_name(r.get("catch_type")), "_catch_type": r.get("catch_type"),
                    **{c: r.get(c) for c in spc}})
    cols = [col("year", tt("year", lang), "integer"), col("date", L("Дата", "Күні"), "date"),
            col("place", tt("place", lang)), col("gear", L("Орудие", "Құрал")),
            col("length", L("Длина сети / невода, м", "Ау / сүзекі ұзындығы, м"), "number"),
            col("area", L("Площадь облова, га", "Ауланған аудан, га"), "number"),
            col("catch_type", L("Тип лова", "Аулау түрі"))] + \
        [{**col(c, D.sp_name(c), "number", L("шт", "дана")), "species": True, "selected": c == sp} for c in spc]
    filt = {"years": _years(rows), "places": sorted({x["place"] for x in out if x["place"]}),
            "gears": sorted({x["gear"] for x in out if x["gear"]}), "types": sorted({x["catch_type"] for x in out if x["catch_type"]}),
            "months": sorted({x["month"] for x in out if x["month"]})}
    return {"columns": cols, "rows": out, "journal": filt, "chart": None, "default_view": "journal",
            "sources": _sources(D, "catches")}


VIEWS = OrderedDict([
    ("overview", v_overview), ("signals", v_signals), ("traffic", v_traffic), ("journal", v_journal),
    ("cpue", v_cpue), ("composition", v_composition), ("coverage_places", v_coverage_places),
    ("coverage_months", v_coverage_months), ("haul_box", v_haul_box), ("type_compare", v_type_compare),
    ("hauls_count", v_hauls_count), ("age_catch_year", v_age_catch_year), ("age_catch_hauls", v_age_catch_hauls),
    ("age_heatmap", v_age_heatmap), ("sample_size", v_sample_size), ("mature_share", v_mature_share),
    ("age_vs_mean", v_age_vs_mean),
    ("growth", v_growth), ("weight_dev", v_weight_dev), ("biomass_structure", v_biomass_structure),
    ("lifecycle", v_lifecycle), ("species_cards", v_species_cards), ("params_compare", v_params_compare),
    ("conditions", v_conditions),
    ("quota", v_quota), ("quota_change", v_quota_change), ("quota_vs_stock", v_quota_vs_stock),
    ("completeness", v_completeness), ("quality", v_quality),
])
NEEDS_RULES = {"overview", "signals", "quality", "traffic", "ca_trust", "st_trust", "ca_bounds_years", "ca_bounds_ages", "ca_cohorts",
               "ca_gears_age", "ca_passport", "ca_z", "ca_blind", "ca_strong", "ca_seine_heat", "ca_net_heat"}

# результаты расчёта (уловистость, запасы) — отдельный модуль
from . import calc_views  # noqa: E402
from . import calc_stock_views  # noqa: E402

VIEWS.update(calc_views.VIEWS)
VIEWS.update(calc_stock_views.VIEWS)


# ------------------------------------------------------------------ сравнение двух лет
def compare_years(res: dict, a: int, b: int) -> dict:
    """Оставить в результате только годы a и b и добавить их разницу."""
    ch = res.get("chart") or {}
    yrs = [a, b]
    if ch.get("kind") in ("series", "box", "dual") and ch.get("x_is_year"):
        idx = [ch["x"].index(y) for y in yrs if y in ch["x"]]
        pick = lambda v: [v[i] for i in idx] if isinstance(v, list) else v  # noqa: E731
        ch = {**ch, "x": [ch["x"][i] for i in idx], "default": "bar" if ch["kind"] == "series" and ch.get("default") == "line" else ch.get("default")}
        if ch["kind"] == "series":
            ch["series"] = [{**s, "values": pick(s["values"]), **({"lo": pick(s["lo"]), "hi": pick(s["hi"])} if s.get("lo") else {})}
                            for s in ch["series"]]
            if ch.get("extra_line"):
                ch["extra_line"] = {**ch["extra_line"], "values": pick(ch["extra_line"]["values"])}
        elif ch["kind"] == "box":
            ch["boxes"] = pick(ch["boxes"])
            old = {i: n for n, i in enumerate(idx)}
            ch["outliers"] = [[old[i], v] for i, v in ch["outliers"] if i in old]
        else:
            ch["left"] = {**ch["left"], "values": pick(ch["left"]["values"])}
            ch["right"] = {**ch["right"], "values": pick(ch["right"]["values"])}
    elif ch.get("kind") == "heatmap" and (ch.get("x_is_year") or ch.get("y_is_year")):
        axis = "x" if ch.get("x_is_year") else "y"
        old = {ch[axis].index(y): n for n, y in enumerate(yrs) if y in ch[axis]}
        k = 0 if axis == "x" else 1
        ch = {**ch, axis: [y for y in yrs if y in ch[axis]],
              "cells": [[*(c[:k]), old[c[k]], *(c[k + 1:])] for c in ch["cells"] if c[k] in old]}
    res = {**res, "chart": ch, "compare": [a, b]}
    rows = res.get("rows") or []
    if rows and "year" in rows[0]:
        ra = next((r for r in rows if r.get("year") == a), None)
        rb = next((r for r in rows if r.get("year") == b), None)
        new = [r for r in (ra, rb) if r]
        if ra and rb:
            diff = {"year": f"{b} − {a}"}
            for c in res["columns"]:
                k = c["code"]
                if k != "year" and isinstance(ra.get(k), (int, float)) and isinstance(rb.get(k), (int, float)) \
                        and not isinstance(ra.get(k), bool):
                    diff[k] = _r(rb[k] - ra[k], 3)
            new.append(diff)
        res["rows"] = new
    elif rows and str(a) in rows[0] and str(b) in rows[0]:
        cols = [c for c in res["columns"] if c["code"] not in {str(y) for y in range(1900, 2101)} or c["code"] in (str(a), str(b))]
        for r in rows:
            if isinstance(r.get(str(a)), (int, float)) and isinstance(r.get(str(b)), (int, float)):
                r["_diff"] = _r(r[str(b)] - r[str(a)], 3)
        res["columns"] = cols + [{"code": "_diff", "title": f"{b} − {a}", "type": "number"}]
    res["tiles"] = []
    return res


# ------------------------------------------------------------------ строки для перехода
def drill_rows(D, dtype: str, where: dict, opt: dict) -> dict:
    if dtype == "catch_by_age":
        if where.get("haul") is not None:
            return explain_haul(D, where, opt)
        rows, meta, ages = _cba(D, opt)
        sp = where.get("_species") or _cba_species(D, rows, opt)[0]
        sel = [r for r in rows if r["_sp"] == sp and (where.get("year") is None or r["year"] == where["year"])]
        a = where.get("age")
        lang = D.lang
        cols = [col("haul", "Лов №", "integer"), col("date", "Дата", "date"), col("place", tt("place", lang)),
                col("total", "Y_id, шт", "number")] + [col(f"a{x}", f"j = {x}", "number") for x in ages if a is None or x == a]
        out = [{"haul": r["haul"], "date": r["_iso"], "place": D.place(r.get("place")), "total": r.get("total"),
                **{f"a{x}": r.get(f"a{x}") for x in ages}} for r in sel if a is None or r.get(f"a{a}")]
        return {"columns": cols, "rows": out, "total": len(out), "dataset_id": None, "meta": meta}
    rows, meta = need(D, dtype)
    kinds = D.gear_kind
    spc = meta["species"]
    out = []
    w = {k: v for k, v in (where or {}).items() if k != "_species"}
    if dtype == "catches":
        base, _ = haul_rows(D, {**opt, "gear": None})
        rows = base if not w.pop("_all_types", False) else rows
    for r in rows:
        ok = True
        for k, v in w.items():
            if v in (None, ""):
                continue
            if k == "gear_kind":
                ok &= kinds.get(r.get("gear")) == v
            elif k == "place":
                ok &= D.place(r.get("place")) == v
            elif k == "month":
                ok &= bool(r.get("date")) and int(r["date"][5:7]) == int(v)
            elif k == "species":
                ok &= r.get(v) not in (None, 0)
            elif k == "_empty":
                ok &= all(r.get(s) in (None, 0) for s in spc)
            elif k == "_no_area":
                ok &= not r.get("area_ha")
            elif k == "_has_area":
                ok &= r.get("area_ha") is not None
            elif k == "_unknown_place":
                ok &= bool(D.places) and bool(r.get("place")) and place_key(r["place"]) not in D.places
            elif k == "gear_kind|catch_type":
                g, c = str(v).split("|")
                ok &= kinds.get(r.get("gear")) == g and r.get("catch_type") == c
            else:
                ok &= r.get(k) == v or str(r.get(k)) == str(v)
            if not ok:
                break
        if ok:
            out.append(r)
    lang = D.lang
    if dtype == "catches":
        cols = [col("year", tt("year", lang), "integer"), col("date", "Дата", "date"), col("place", tt("place", lang)),
                col("gear", "Орудие", "string"), col("gear_size_m", "Длина, м", "number"), col("area_ha", "Площадь, га", "number"),
                col("catch_type", "Тип лова")]
        disp = []
        for r in out:
            d = dict(r)
            d["gear"] = D.gear_name(r.get("gear"))
            d["catch_type"] = D.catch_type_name(r.get("catch_type"))
            disp.append(d)
        out = disp
    else:
        cols = [col(k, k) for k in (out[0].keys() if out else []) if k not in spc]
        if dtype == "species_props":
            out = [{**r, "species": D.sp_name(r.get("species"))} for r in out]
    cols += [col(s, D.sp_name(s), "number") for s in spc if any(r.get(s) is not None for r in out)]
    return {"columns": cols, "rows": out[:2000], "total": len(out), "dataset_id": meta["dataset_id"],
            "version": meta["version"]}
