"""
Системные шаблоны дашбордов. Виджеты:
    kpi | line | bar | table | band (полоса интервала) | text | special (особые представления: см. kind)
Источник данных виджета (source):
    {"kind": "dataset", "dataset_type": <тип>}                       — текущая версия набора водоёма
    {"kind": "run", "algorithm": <код>, "table": <таблица>}         — запуск для мониторинга (основной/последний)
    {"kind": "payload", "algorithm": <код>}                         — полное представление шага (особые виджеты)
Подстановки фильтров: water_body, species, year (значения дашборда), "$last_year".
"""

TABS_MONITORING = [
    {"code": "data", "title_ru": "Исходные данные", "title_kk": "Бастапқы деректер"},
    {"code": "catchability", "title_ru": "Уловистость", "title_kk": "Аулағыштық"},
    {"code": "stock", "title_ru": "Запасы", "title_kk": "Қорлар"},
    {"code": "pdu", "title_ru": "ПДУ", "title_kk": "ШРА"},
]


KK = {
    "Сводка данных": "Деректер жиынтығы", "Улов научных ловов по годам, шт": "Жылдар бойынша ғылыми аулау ауланымы, дана",
    "Число ловов по годам": "Жылдар бойынша аулаулар саны", "Возрастная проба последнего года, шт": "Соңғы жылғы жас сынамасы, дана",
    "ПДУ НПЦ, т": "ҒӨО ШРА, т", "Уловы по ловам": "Аулаулар бойынша ауланым", "Уловистость невода": "Аудың аулағыштығы",
    "Уловистость сети": "Желінің аулағыштығы", "Коэффициенты уловистости невода": "Аудың аулағыштық коэффициенттері",
    "Численность: модель и оценки по уловам": "Саны: модель және ауланым бойынша бағалаулар",
    "Годовой запас по орудиям лова, шт": "Аулау құралдары бойынша жылдық қор, дана",
    "Окончательный запас по возрастам, последний год, шт": "Жас бойынша түпкілікті қор, соңғы жыл, дана",
    "ПДУ по видам": "Түрлер бойынша ШРА", "Из чего сложился ПДУ: запас → возраст → квота": "ШРА неден құралды: қор → жас → квота",
    "Прогноз по сценариям": "Сценарийлер бойынша болжам", "ПДУ НПЦ по водоёмам, т": "Су айдындары бойынша ҒӨО ШРА, т",
    "Окончательный запас по уловам, шт": "Ауланым бойынша түпкілікті қор, дана",
}


def W(id_, tab, type_, title, source, w=6, h=4, **opt):
    return {"id": id_, "tab": tab, "type": type_, "title_ru": title, "title_kk": KK.get(title, ""), "source": source,
            "w": w, "h": h, "options": opt}


MONITORING = {
    "code": "monitoring",
    "title_ru": "Мониторинг водоёма",
    "title_kk": "Су айдынының мониторингі",
    "description": "Исходные данные, уловистость, запасы и ПДУ выбранного водоёма. Результаты — основной запуск "
                   "водоёма, иначе последний успешный.",
    "is_template": True, "system": True, "visibility": "shared",
    "filters": {"water_body": None, "species": None},
    "tabs": TABS_MONITORING,
    "widgets": [
        # ---- исходные данные
        W("d_kpi", "data", "special", "Сводка данных", {"kind": "status"}, 12, 2, kind="data_summary"),
        W("d_catch", "data", "bar", "Улов научных ловов по годам, шт", {"kind": "dataset", "dataset_type": "catches"},
          6, 5, x="year", y="$species", agg="sum", series="gear"),
        W("d_hauls", "data", "bar", "Число ловов по годам", {"kind": "dataset", "dataset_type": "catches"},
          6, 5, x="year", y="count", agg="count", series="gear"),
        W("d_sample", "data", "line", "Возрастная проба последнего года, шт", {"kind": "dataset", "dataset_type": "age_samples"},
          6, 5, x="age", y="$species", agg="sum", filter={"year": "$last_year"}),
        W("d_npc", "data", "line", "ПДУ НПЦ, т", {"kind": "dataset", "dataset_type": "npc_pdu"}, 6, 5,
          x="year", y="$species", agg="sum"),
        W("d_table", "data", "table", "Уловы по ловам", {"kind": "dataset", "dataset_type": "catches"}, 12, 6),
        # ---- уловистость
        W("c_seine", "catchability", "special", "Уловистость невода", {"kind": "payload", "algorithm": "seine_catchability"},
          6, 6, kind="seine_curves"),
        W("c_net", "catchability", "special", "Уловистость сети", {"kind": "payload", "algorithm": "stock_by_catch"},
          6, 6, kind="net_curves"),
        W("c_table", "catchability", "table", "Коэффициенты уловистости невода",
          {"kind": "run", "algorithm": "seine_catchability", "table": "coefficients"}, 12, 5),
        # ---- запасы
        W("s_total", "stock", "special", "Численность: модель и оценки по уловам",
          {"kind": "payload", "algorithm": "bayes_cohort"}, 12, 6, kind="bayes_band"),
        W("s_gears", "stock", "line", "Годовой запас по орудиям лова, шт",
          {"kind": "run", "algorithm": "stock_by_catch", "table": "yearly_stock"}, 6, 5,
          x="year", y="stock", series="gear", filter={"variant": "with_ages", "method": "on_stock"}),
        W("s_age", "stock", "bar", "Окончательный запас по возрастам, последний год, шт",
          {"kind": "run", "algorithm": "stock_by_catch", "table": "stock_by_age"}, 6, 5,
          x="age_title", y="stock", filter={"year": "$last_year"}),
        # ---- ПДУ
        W("p_summary", "pdu", "special", "ПДУ по видам", {"kind": "payload", "algorithm": "forecast_pdu"}, 12, 4,
          kind="pdu_summary"),
        W("p_breakdown", "pdu", "special", "Из чего сложился ПДУ: запас → возраст → квота",
          {"kind": "payload", "algorithm": "pdu_by_age"}, 12, 7, kind="pdu_breakdown"),
        W("p_forecast", "pdu", "special", "Прогноз по сценариям", {"kind": "payload", "algorithm": "forecast_pdu"}, 12, 6,
          kind="forecast_scenarios"),
    ],
}

COMPARE = {
    "code": "compare",
    "title_ru": "Сравнение водоёмов и лет",
    "title_kk": "Су айдындары мен жылдарды салыстыру",
    "description": "Пример конструктора: ПДУ НПЦ и запас по выбранным водоёмам.",
    "is_template": True, "system": True, "visibility": "shared",
    "filters": {"water_bodies": [], "species": None},
    "tabs": [{"code": "main", "title_ru": "Сравнение", "title_kk": "Салыстыру"}],
    "widgets": [
        W("cmp_pdu", "main", "line", "ПДУ НПЦ по водоёмам, т", {"kind": "dataset", "dataset_type": "npc_pdu", "multi": True},
          12, 5, x="year", y="$species", series="water_body", agg="sum"),
        W("cmp_stock", "main", "line", "Окончательный запас по уловам, шт",
          {"kind": "run", "algorithm": "stock_by_catch", "table": "yearly_stock", "multi": True}, 12, 5,
          x="year", y="stock", series="water_body", filter={"variant": "with_ages", "method": "on_stock", "gear": "сеть+невод"}),
    ],
}

# Ревизия системных шаблонов: при обновлении приложения неизменённые пользователями шаблоны обновляются
TEMPLATE_REV = 2

SYSTEM = [MONITORING, COMPARE]
