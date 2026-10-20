"""
Начальное наполнение справочников (системные сущности и типы наборов данных).

Структуры повторяют исходные данные заказчика (legacy/data_catch/*.py) — см. docs/data_formats.md.
Системные поля (system=True) используются алгоритмами: их нельзя удалить или сменить им тип.
"""

def F(code, ru, kk, type_="string", **kw):
    d = {"code": code, "title_ru": ru, "title_kk": kk, "type": type_, "required": kw.pop("required", False),
         "system": kw.pop("system", True)}
    d.update(kw)
    return d


WATER_BODY_TYPES = [
    {"value": "lake", "title_ru": "Озеро", "title_kk": "Көл"},
    {"value": "reservoir", "title_ru": "Водохранилище", "title_kk": "Су қоймасы"},
    {"value": "river", "title_ru": "Река", "title_kk": "Өзен"},
    {"value": "sea", "title_ru": "Море", "title_kk": "Теңіз"},
    {"value": "other", "title_ru": "Другое", "title_kk": "Басқа"},
]

ENTITIES = [
    {
        "code": "water_bodies", "title_ru": "Водоёмы", "title_kk": "Су айдындары", "system": True,
        "description": "Рыбохозяйственные водоёмы. Точка обязательна, контур — по желанию.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True,
              hint="латиница, например zhaysan; используется в файлах и расчётах"),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            F("type", "Тип", "Түрі", "enum", required=True, enum=WATER_BODY_TYPES),
            F("region", "Область", "Облыс"),
            F("basin", "Бассейн", "Алап"),
            F("area_km2", "Площадь, км²", "Ауданы, км²", "number", unit="км²", min=0),
            F("point", "Точка на карте", "Картадағы нүкте", "geo_point", required=True),
            F("shape", "Контур", "Контуры", "geo_shape"),
            F("note", "Примечание", "Ескертпе", "text", system=False),
        ],
    },
    {
        "code": "species", "title_ru": "Виды рыб", "title_kk": "Балық түрлері", "system": True,
        "description": "Виды рыб. Код используется в расчётах, названия — в шаблонах Excel (столбцы видов).",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            F("latin", "Латинское название", "Латынша атауы", system=False),
            F("is_predator", "Хищник", "Жыртқыш", "boolean"),
        ],
    },
    {
        "code": "gears", "title_ru": "Орудия лова", "title_kk": "Аулау құралдары", "system": True,
        "description": "Орудия научного лова. Вид орудия определяет формулу расчёта запаса.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            F("kind", "Вид орудия", "Құрал түрі", "enum", required=True, enum=[
                {"value": "seine", "title_ru": "Невод (метод площадей)", "title_kk": "Сүзекі (аудан әдісі)"},
                {"value": "net", "title_ru": "Сеть (балансовый метод)", "title_kk": "Ау (баланс әдісі)"},
            ]),
        ],
    },
]

SPECIES = [
    ("lesh", "лещ", "тыран", "Abramis brama", False),
    ("sudak", "судак", "көксерке", "Sander lucioperca", True),
    ("okun", "окунь", "алабұға", "Perca fluviatilis", True),
    ("plotva", "плотва", "торта", "Rutilus rutilus", False),
    ("shuka", "щука", "шортан", "Esox lucius", True),
    ("sazan", "сазан", "сазан", "Cyprinus carpio", False),
    ("yaz", "язь", "аққайран", "Leuciscus idus", False),
    ("karas", "карась", "мөңке", "Carassius gibelio", False),
    ("yorsh", "ерш", "таутан", "Gymnocephalus cernua", False),
    ("lin", "линь", "оңғақ", "Tinca tinca", False),
    ("nalim", "налим", "налим", "Lota lota", True),
    ("tolstolobik", "толстолобик", "дөңмаңдай", "Hypophthalmichthys molitrix", False),
    # виды Балхаша и Капчагая (данные заказчика 20.10.2026); хищник — значение по умолчанию,
    # для расчёта берётся признак из «Биологических параметров видов» водоёма
    ("zherekh", "жерех", "ақмарқа", "Leuciscus aspius", True),
    ("som", "сом", "жайын", "Silurus glanis", True),
    ("bersh", "берш", "берш", "Sander volgensis", True),
    ("zmeegolov", "змееголов", "жыланбас", "Channa argus", True),
    ("b_amur", "белый амур", "ақ амур", "Ctenopharyngodon idella", False),
]

# написания видов в исходных файлах заказчика → код вида
SPECIES_ALIASES = {"т_лоб": "tolstolobik", "толстолоб": "tolstolobik", "б_амур": "b_amur", "беламур": "b_amur"}

GEARS = [
    ("seine", "невод", "сүзекі", "seine"),
    ("net", "сеть", "ау", "net"),
]

YEAR = F("year", "Год", "Жыл", "integer", required=True, min=1900, max=2100)
AGE = F("age", "Возраст j (группа от j−1 до j лет)", "Жас j", "integer", required=True, min=1, max=40,
        hint="как в исходных данных: j = 2 — рыбы от 1 до 2 лет")


def species_cols(value_type, unit, ru, kk, min_=0):
    return {"enabled": True, "entity": "species", "value_type": value_type, "unit": unit, "min": min_,
            "title_ru": ru, "title_kk": kk,
            "missing": "Пустая ячейка — вид не учитывался (не ноль). Ноль — вид учитывался, но не пойман."}


DATASET_TYPES = [
    {
        "code": "catches", "title_ru": "Уловы по ловам", "title_kk": "Аулаулар бойынша ауланым",
        "description": "Каждая строка — один лов (замёт невода или постановка сети). Столбцы видов — улов, штук.",
        "period_field": "year", "system": True,
        "columns": [
            YEAR,
            F("date", "Дата лова", "Аулау күні", "date", required=True),
            F("place", "Место лова", "Аулау орны", required=True),
            F("gear", "Орудие лова", "Аулау құралы", "ref", required=True, ref_entity="gears"),
            F("gear_desc", "Описание орудия", "Құрал сипаттамасы", system=False, hint="например «сети 20-80 мм»"),
            F("gear_size_m", "Размер орудия (длина), м", "Құрал өлшемі, м", "number", unit="м", min=0,
              hint="в расчётах не используется; в части данных Капчагая не указан"),
            F("area_ha", "Обловленная площадь, га", "Ауланған аудан, га", "number", unit="га", min=0,
              hint="для невода; у сетей — 0 или пусто"),
            F("catch_type", "Тип лова", "Аулау түрі", "enum", required=True, enum=[
                {"value": "научный", "title_ru": "научный", "title_kk": "ғылыми"},
                {"value": "промысловый", "title_ru": "промысловый", "title_kk": "кәсіптік"},
            ]),
        ],
        "species_columns": species_cols("integer", "шт", "Улов по видам, шт", "Түрлер бойынша ауланым, дана"),
    },
    {
        "code": "age_samples", "title_ru": "Возрастные пробы", "title_kk": "Жас сынамалары",
        "description": "Число рыб, прошедших биологический анализ, по возрастам (на год, по всем орудиям).",
        "period_field": "year", "system": True,
        "key_fields": ["year", "age"],
        "columns": [YEAR, AGE],
        "species_columns": species_cols("integer", "шт", "Число рыб в пробе, шт", "Сынамадағы балық саны, дана"),
    },
    {
        "code": "mean_weights", "title_ru": "Средний вес по возрастам", "title_kk": "Жас бойынша орташа салмақ",
        "description": "Средний вес рыбы, г, по возрастам и годам.",
        "period_field": "year", "system": True,
        "key_fields": ["year", "age"],
        "columns": [YEAR, AGE],
        "species_columns": species_cols("number", "г", "Средний вес, г", "Орташа салмақ, г"),
    },
    {
        "code": "species_props", "title_ru": "Биологические параметры видов", "title_kk": "Түрлердің биологиялық параметрлері",
        "description": "Параметры видов для водоёма (как в zhaysan_fish_prop.py).",
        "period_field": None, "system": True,
        "key_fields": ["species"],
        "rules": [
            {"type": "le", "left": "m0", "right": "m1", "message": "m0 не может быть больше m1"},
            {"type": "le", "left": "m2", "right": "m1", "level": "warning",
             "message": "m2 больше m1: кормом хищников считаются все возрасты (проверьте значение)"},
            {"type": "le", "left": "fecundity_min", "right": "fecundity_max",
             "message": "Минимальная плодовитость больше максимальной"},
        ],
        "columns": [
            F("species", "Вид", "Түрі", "ref", required=True, ref_entity="species"),
            F("m0", "Возраст половой зрелости m0", "Жыныстық жетілу жасы m0", "integer", required=True, min=1, max=40),
            F("m1", "Максимальный возраст m1", "Ең жоғары жас m1", "integer", required=True, min=2, max=40),
            F("m2", "Возраст, до которого — корм хищников m2", "Жыртқыштарға жем болатын жас m2", "integer",
              required=True, min=1, max=40),
            F("v_cr", "Крейсерская скорость, м/с", "Круиздік жылдамдық, м/с", "number", required=True, unit="м/с", min=0),
            F("k_net", "Средняя уловистость сети", "Аудың орташа аулағыштығы", "number", required=True, min=0, max=1),
            F("k_seine", "Средняя уловистость невода", "Аудың орташа аулағыштығы", "number", required=True, min=0, max=1),
            F("is_predator", "Хищник", "Жыртқыш", "boolean", required=True),
            F("fecundity_min", "Плодовитость, мин., икринок", "Өсімталдық, мин.", "number", required=True, unit="шт", min=0),
            F("fecundity_max", "Плодовитость, макс., икринок", "Өсімталдық, макс.", "number", required=True, unit="шт", min=0),
            F("fry_density", "Предельная плотность мальков, шт/м²", "Шабақтардың шекті тығыздығы, дана/м²",
              "number", required=True, unit="шт/м²", min=0),
        ],
        "species_columns": {"enabled": False},
    },
    {
        "code": "yearly_conditions", "title_ru": "Условия по годам", "title_kk": "Жылдар бойынша жағдайлар",
        "description": "Площадь водоёма и параметры сетей по годам.",
        "period_field": "year", "system": True, "key_fields": ["year"],
        "columns": [
            YEAR,
            F("lake_area_km2", "Площадь водоёма, км²", "Су айдынының ауданы, км²", "number", required=True, unit="км²", min=0),
            F("net_length_m", "Длина сети, м", "Ау ұзындығы, м", "number", required=True, unit="м", min=0),
            F("net_hours", "Время стоянки сети, ч", "Аудың тұру уақыты, сағ", "integer", required=True, unit="ч", min=1),
        ],
        "species_columns": {"enabled": False},
    },
    {
        "code": "npc_stock", "title_ru": "Оценка запаса НПЦ", "title_kk": "ҒӨО қор бағасы",
        "description": "Оценка запаса НПЦ РХ, тыс. шт (в расчётах умножается на 1000).",
        "period_field": "year", "system": True, "key_fields": ["year"],
        "columns": [YEAR],
        "species_columns": species_cols("number", "тыс. шт", "Запас, тыс. шт", "Қор, мың дана"),
    },
    {
        "code": "npc_pdu", "title_ru": "ПДУ НПЦ", "title_kk": "ҒӨО ШРА",
        "description": "Предельно допустимый улов, установленный НПЦ, т.",
        "period_field": "year", "system": True, "key_fields": ["year"],
        "columns": [YEAR],
        "species_columns": species_cols("number", "т", "ПДУ, т", "ШРА, т"),
    },
]
