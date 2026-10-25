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


TOFI = F("tofi_code", "Код ТОФИ", "ТОФИ коды", system=False,
         hint="код значения в классификаторе ТОФИ (например _FV_1001)")


def simple_entity(code, ru, kk, description, extra=(), aliases=False):
    """Справочник «код — название (рус./каз.) — код ТОФИ» (классификатор «Факторы» ТОФИ, 21.10.2026)."""
    fields = [
        F("code", "Код", "Код", required=True, unique=True),
        F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
        F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
        *extra,
    ]
    if aliases:
        fields.append(ALIASES)
    fields.append(TOFI)
    return {"code": code, "title_ru": ru, "title_kk": kk, "system": True, "description": description,
            "display_field": "name_ru", "fields": fields}


ALIASES = F("aliases", "Другие написания", "Басқа жазылуы", "text", system=False,
            hint="по одному в строке; при загрузке файлов такие написания приводятся к названию записи")

# Значения справочников из классификатора «Факторы» ТОФИ (файл заказчика 21.10.2026):
# (код, название рус., название каз., код ТОФИ). Казахские названия — перевод разработчика, на проверку.
CLASSIFIERS = {
    "water_body_types": [
        ("sea", "море", "теңіз", "_FV_1001"),
        ("lake", "озеро", "көл", "_FV_1002"),
        ("river", "река", "өзен", "_FV_1003"),
        ("reservoir", "водохранилище", "су қоймасы", "_FV_1004"),
        ("pond", "пруд", "тоған", "_FV_1005"),
        ("dam", "плотина", "бөгет", "_FV_1006"),
        ("channel", "проток", "арна", "_FV_1007"),
    ],
    "water_body_statuses": [
        ("international", "водоём международного значения", "халықаралық маңызы бар су айдыны", "_FV_1011"),
        ("republican", "водоём республиканского значения", "республикалық маңызы бар су айдыны", "_FV_1012"),
        ("local", "водоём местного значения", "жергілікті маңызы бар су айдыны", "_FV_1013"),
    ],
    "water_body_origins": [
        ("natural", "естественный водоём", "табиғи су айдыны", "_FV_1015"),
        ("artificial", "искусственный водоём", "жасанды су айдыны", "_FV_1016"),
    ],
    "fishery_kinds": [
        ("amateur", "любительское (спортивное) рыболовство", "әуесқойлық (спорттық) балық аулау", "_FV_1049"),
        ("commercial", "промысловое рыболовство", "кәсіпшілік балық аулау", "_FV_1050"),
        ("lake_farm", "озёрно-товарное рыбоводное хозяйство", "көлдік-тауарлық балық өсіру шаруашылығы", "_FV_1051"),
        ("cage_farm", "садковое рыбоводное хозяйство", "торлы балық өсіру шаруашылығы", "_FV_1052"),
    ],
    "catch_types": [
        ("scientific", "научный лов", "ғылыми аулау", "_FV_1087"),
        ("commercial", "промысловый лов", "кәсіпшілік аулау", "_FV_1088"),
        ("sport", "спортивно-любительский лов", "спорттық-әуесқойлық аулау", "_FV_1089"),
    ],
    "gear_categories": [
        ("commercial", "промысловые орудия", "кәсіпшілік құралдар", "_FV_1084"),
        ("non_commercial", "непромысловые орудия", "кәсіпшілікке жатпайтын құралдар", "_FV_1085"),
    ],
    "fish_sexes": [
        ("female", "самка", "аналық", "_FV_1091"),
        ("male", "самец", "аталық", "_FV_1092"),
        ("juvenile", "ювенильные", "ювенильді (жыныстық жетілмеген)", "_FV_1093"),
    ],
    "forage_bases": [
        ("zoobenthos", "зообентос", "зообентос", "_FV_1095"),
        ("zooplankton", "зоопланктон", "зоопланктон", "_FV_1096"),
    ],
}
# прежние значения в данных и файлах заказчика → запись справочника (другие написания)
CLASSIFIER_ALIASES = {
    ("catch_types", "scientific"): "научный",
    ("catch_types", "commercial"): "промысловый",
    ("catch_types", "sport"): "спортивно-любительский\nлюбительский",
}

# семейства рыб: (код = латинское название, рус., каз., код ТОФИ)
FAMILIES = [
    ("acipenseridae", "Осетровые", "Бекіре тұқымдастар", "_FV_1054"),
    ("salmonidae", "Лососевые", "Албырт тұқымдастар", "_FV_1055"),
    ("clupeidae", "Сельдевые", "Майшабақ тұқымдастар", "_FV_1056"),
    ("cyprinidae", "Карповые", "Тұқы тұқымдастар", "_FV_1057"),
    ("percidae", "Окуневые", "Алабұға тұқымдастар", "_FV_1058"),
    ("gadidae", "Тресковые", "Нәлім тұқымдастар", "_FV_1059"),
    ("pleuronectidae", "Камбаловые", "Камбала тұқымдастар", "_FV_1060"),
    ("scombridae", "Скумбриевые", "Скумбрия тұқымдастар", "_FV_1061"),
    ("thunnini", "Тунцовые", "Тунец тұқымдастар", "_FV_1062"),
    ("carangidae", "Ставридовые", "Ставрида тұқымдастар", "_FV_1063"),
    ("esocidae", "Щуковые", "Шортан тұқымдастар", "_FV_1064"),
    ("siluridae", "Сомовые", "Жайын тұқымдастар", "_FV_1065"),
    ("petromyzontidae", "Миноговые", "Миноға тұқымдастар", "_FV_1066"),
    ("anguillidae", "Угревые", "Жыланбалық тұқымдастар", "_FV_1067"),
    ("osmeridae", "Корюшковые", "Корюшка тұқымдастар", "_FV_1068"),
    ("channidae", "Змееголовые", "Жыланбас тұқымдастар", "_FV_1069"),
]

ENTITIES = [
    simple_entity("water_body_types", "Виды водоёмов", "Су айдындарының түрлері",
                  "Вид водоёма: море, озеро, река, водохранилище и др. (классификатор ТОФИ)."),
    simple_entity("water_body_statuses", "Статусы водоёмов для отрасли", "Су айдындарының салалық мәртебесі",
                  "Значение водоёма для рыбного хозяйства: международное, республиканское, местное."),
    simple_entity("water_body_origins", "Типы водоёмов", "Су айдындарының типтері",
                  "Естественный или искусственный водоём."),
    simple_entity("fishery_kinds", "Виды ведения рыбного хозяйства", "Балық шаруашылығын жүргізу түрлері",
                  "Рыболовство и рыбоводство на водоёме; у водоёма может быть несколько видов."),
    {
        "code": "regions", "title_ru": "Области", "title_kk": "Облыстар", "system": True,
        "description": "Административное деление Казахстана (с 2022 г.): области и города республиканского значения.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
        ],
    },
    {
        "code": "water_bodies", "title_ru": "Водоёмы", "title_kk": "Су айдындары", "system": True,
        "description": "Рыбохозяйственные водоёмы. Точка обязательна, контур — по желанию.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True,
              hint="латиница, например zhaysan; используется в файлах и расчётах"),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            F("type", "Вид водоёма", "Су айдынының түрі", "ref", required=True, ref_entity="water_body_types"),
            F("origin", "Тип водоёма", "Су айдынының типі", "ref", ref_entity="water_body_origins", system=False,
              hint="естественный или искусственный"),
            F("status", "Статус для отрасли", "Салалық мәртебесі", "ref", ref_entity="water_body_statuses",
              system=False),
            F("fishery_kinds", "Виды ведения рыбного хозяйства", "Балық шаруашылығын жүргізу түрлері", "ref_list",
              ref_entity="fishery_kinds", system=False, hint="одно или несколько"),
            F("regions", "Области", "Облыстар", "ref_list", ref_entity="regions",
              hint="одна или несколько областей; водоём находится по фильтру любой из них"),
            F("basin", "Бассейн", "Алап"),
            F("area_km2", "Площадь, км²", "Ауданы, км²", "number", unit="км²", min=0),
            F("point", "Точка на карте", "Картадағы нүкте", "geo_point", required=True),
            F("shape", "Контур", "Контуры", "geo_shape"),
            F("note", "Примечание", "Ескертпе", "text", system=False),
        ],
    },
    {
        "code": "fish_families", "title_ru": "Семейства рыб", "title_kk": "Балық тұқымдастары", "system": True,
        "description": "Систематические семейства рыб (классификатор ТОФИ).",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True, hint="латинское название семейства"),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            TOFI,
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
            F("family", "Семейство", "Тұқымдасы", "ref", ref_entity="fish_families", system=False),
            F("is_predator", "Хищник", "Жыртқыш", "boolean"),
            TOFI,
        ],
    },
    simple_entity("gear_categories", "Типы орудий лова", "Аулау құралдарының типтері",
                  "Промысловые и непромысловые орудия (классификатор ТОФИ)."),
    {
        "code": "gears", "title_ru": "Орудия лова", "title_kk": "Аулау құралдары", "system": True,
        "description": "Орудия научного лова. Вид орудия определяет формулу расчёта запаса.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            F("kind", "Вид орудия", "Құрал түрі", "enum", required=True, enum=[
                {"value": "seine", "title_ru": "Невод — активное орудие (метод площадей)",
                 "title_kk": "Сүзекі — белсенді құрал (аудан әдісі)"},
                {"value": "net", "title_ru": "Сеть — пассивное орудие (балансовый метод)",
                 "title_kk": "Ау — енжар құрал (баланс әдісі)"},
            ]),
            F("category", "Тип орудия лова", "Аулау құралының типі", "ref", ref_entity="gear_categories",
              system=False),
        ],
    },
    simple_entity("catch_types", "Типы вылова", "Аулау түрлері",
                  "Научный, промысловый, спортивно-любительский лов (столбец «Тип лова» в уловах).", aliases=True),
    {
        "code": "fishing_places", "title_ru": "Места лова", "title_kk": "Аулау орындары", "system": True,
        "description": "Места лова на каждом водоёме. При загрузке уловов место сверяется с местами своего "
                       "водоёма; другие написания приводятся к названию места.",
        "display_field": "name_ru",
        "fields": [
            F("water_body", "Водоём", "Су айдыны", "ref", required=True, ref_entity="water_bodies"),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)"),
            ALIASES,
            F("point", "Точка на карте", "Картадағы нүкте", "geo_point", system=False),
            F("note", "Примечание", "Ескертпе", "text", system=False),
        ],
    },
    simple_entity("fish_sexes", "Пол рыбы", "Балықтың жынысы",
                  "Для данных биологического анализа (пока в расчётах не используется)."),
    simple_entity("forage_bases", "Кормовая база", "Азық қоры",
                  "Группы кормовых организмов (пока в расчётах не используется)."),
    # Организации сотрудников — для профиля пользователя (решение № 58, 24.10.2026). Начально пустой:
    # названия вносит администратор; код записи хранится в профиле пользователя (сервис users).
    {
        "code": "organizations", "title_ru": "Организации", "title_kk": "Ұйымдар", "system": True,
        "description": "Организации, в которых работают пользователи приложения. Выбираются в профиле "
                       "пользователя (поле «Организация»). Код записи не меняйте — на него ссылаются профили.",
        "display_field": "name_ru",
        "fields": [
            F("code", "Код", "Код", required=True, unique=True,
              hint="латиница, цифры, точка, дефис, подчёркивание; не меняется после выбора в профилях"),
            F("name_ru", "Название (рус.)", "Атауы (орыс.)", required=True, unique=True),
            F("short_name", "Краткое название", "Қысқаша атауы", system=False),
            F("name_kk", "Название (каз.)", "Атауы (қаз.)", system=False),
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
    # из классификатора «Факторы» ТОФИ (21.10.2026); казахские названия — на проверку
    ("elets", "елец", "шабақ", "Leuciscus leuciscus", False),
    ("karp", "карп (зеркальный)", "тұқы (айналы)", "Cyprinus carpio", False),
    ("rak", "рак", "шаян", "Pontastacus leptodactylus", None),     # не рыба; признак хищника не задан
]
# семейство и код ТОФИ вида (рак — не рыба, семейства рыб нет)
SPECIES_FAMILY = {
    "lesh": "cyprinidae", "plotva": "cyprinidae", "sazan": "cyprinidae", "yaz": "cyprinidae", "karas": "cyprinidae",
    "lin": "cyprinidae", "tolstolobik": "cyprinidae", "zherekh": "cyprinidae", "b_amur": "cyprinidae",
    "elets": "cyprinidae", "karp": "cyprinidae",
    "sudak": "percidae", "okun": "percidae", "yorsh": "percidae", "bersh": "percidae",
    "shuka": "esocidae", "nalim": "gadidae", "som": "siluridae", "zmeegolov": "channidae",
}
SPECIES_TOFI = {
    "lesh": "_FV_1025", "sudak": "_FV_1026", "okun": "_FV_1027", "plotva": "_FV_1028", "sazan": "_FV_1029",
    "shuka": "_FV_1030", "yaz": "_FV_1031", "karas": "_FV_1032", "yorsh": "_FV_1033", "nalim": "_FV_1034",
    "tolstolobik": "_FV_1035", "lin": "_FV_1036", "karp": "_FV_1037", "bersh": "_FV_1038", "elets": "_FV_1039",
    "zmeegolov": "_FV_1040", "zherekh": "_FV_1041", "som": "_FV_1042", "rak": "_FV_1043", "b_amur": "_FV_1109",
}

# Области и города республиканского значения (деление с 2022 г.)
REGIONS = [
    ("abai", "область Абай", "Абай облысы"),
    ("akmola", "Акмолинская область", "Ақмола облысы"),
    ("aktobe", "Актюбинская область", "Ақтөбе облысы"),
    ("almaty_region", "Алматинская область", "Алматы облысы"),
    ("atyrau", "Атырауская область", "Атырау облысы"),
    ("west_kz", "Западно-Казахстанская область", "Батыс Қазақстан облысы"),
    ("zhambyl", "Жамбылская область", "Жамбыл облысы"),
    ("zhetysu", "область Жетісу", "Жетісу облысы"),
    ("karaganda", "Карагандинская область", "Қарағанды облысы"),
    ("kostanay", "Костанайская область", "Қостанай облысы"),
    ("kyzylorda", "Кызылординская область", "Қызылорда облысы"),
    ("mangystau", "Мангистауская область", "Маңғыстау облысы"),
    ("pavlodar", "Павлодарская область", "Павлодар облысы"),
    ("north_kz", "Северо-Казахстанская область", "Солтүстік Қазақстан облысы"),
    ("turkistan", "Туркестанская область", "Түркістан облысы"),
    ("ulytau", "область Ұлытау", "Ұлытау облысы"),
    ("east_kz", "Восточно-Казахстанская область", "Шығыс Қазақстан облысы"),
    ("astana", "г. Астана", "Астана қаласы"),
    ("almaty", "г. Алматы", "Алматы қаласы"),
    ("shymkent", "г. Шымкент", "Шымкент қаласы"),
]
REGION_BY_NAME = {ru: code for code, ru, _ in REGIONS}
# прежние названия (до 2022 г. и в данных) → код области
REGION_BY_NAME.update({"Алматинская область": "almaty_region", "Восточно-Казахстанская область": "east_kz",
                       "Карагандинская область": "karaganda", "Туркестанская область": "turkistan"})
# Водоёмы, лежащие в нескольких областях, и водоёмы, отошедшие к новым областям в 2022 г.
# (по сведениям заказчика и административным границам; координаты и области — «проверьте»)
WATER_BODY_REGIONS = {
    "balkhash": ["karaganda", "almaty_region", "zhambyl"],
    "alakol": ["zhetysu", "abai"],
    "sasykkol": ["zhetysu"],
    "koshkarkol": ["zhetysu"],
    "tengiz": ["akmola", "karaganda"],
    "shulba": ["abai", "east_kz"],
    "north_caspian": ["atyrau", "mangystau"],
}


def regions_for(code: str, old_region: str | None) -> list[str]:
    if code in WATER_BODY_REGIONS:
        return list(WATER_BODY_REGIONS[code])
    c = REGION_BY_NAME.get((old_region or "").strip())
    return [c] if c else []


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


# «Возрастные пробы» переименованы по таблице 2 методики (замечание заказчика 24.10.2026, решение № 68);
# код набора age_samples не меняется. Работающие установки переводятся при запуске (main._rename_age_samples).
AGE_SAMPLES_TITLE = ("Рыбы, подвергнутые биологической обработке", "Биологиялық өңдеуден өткен балықтар")
AGE_SAMPLES_DESCRIPTION = "Число рыб, подвергнутых биологической обработке, по возрастам (на год, по всем орудиям)."
AGE_SAMPLES_SPECIES_TITLE = ("Число рыб, подвергнутых биологической обработке, шт", "Биологиялық өңдеуден өткен балық саны, дана")
AGE_SAMPLES_OLD = {"title_ru": "Возрастные пробы", "title_kk": "Жас сынамалары",
                   "description": "Число рыб, прошедших биологический анализ, по возрастам (на год, по всем орудиям).",
                   "species_ru": "Число рыб в пробе, шт", "species_kk": "Сынамадағы балық саны, дана"}

# «Крейсерская скорость» → «Скорость блуждания» (замечание Марса Габбасова 25.10.2026, решение № 72): в балансовом
# методе нужна средняя скорость перемещения рыбы при обычном поведении, а не скорость направленного плавания.
# Код поля v_cr не меняется; файлы с прежним заголовком принимаются (aliases). Установки переводятся при запуске
# (main._rename_v_cr).
V_CR_TITLE = ("Скорость блуждания, м/с", "Кезбе жылдамдығы, м/с")
V_CR_OLD = ("Крейсерская скорость, м/с", "Круиздік жылдамдық, м/с")
V_CR_HINT = "средняя скорость перемещения рыбы при обычном (не направленном) поведении; входит в оценку запаса сетью в квадрате"

DATASET_TYPES = [
    {
        "code": "catches", "title_ru": "Уловы по ловам", "title_kk": "Аулаулар бойынша ауланым",
        "description": "Каждая строка — один лов (замёт невода или постановка сети). Столбцы видов — улов, штук.",
        "period_field": "year", "system": True,
        "columns": [
            YEAR,
            F("date", "Дата лова", "Аулау күні", "date", required=True),
            F("place", "Место лова", "Аулау орны", required=True, places_entity="fishing_places",
              hint="сверяется со справочником «Места лова» своего водоёма; другие написания приводятся к названию"),
            F("gear", "Орудие лова", "Аулау құралы", "ref", required=True, ref_entity="gears"),
            F("gear_desc", "Описание орудия", "Құрал сипаттамасы", system=False, hint="например «сети 20-80 мм»"),
            F("gear_size_m", "Размер орудия (длина), м", "Құрал өлшемі, м", "number", unit="м", min=0,
              hint="в расчётах не используется; в части данных Капчагая не указан"),
            F("area_ha", "Обловленная площадь, га", "Ауланған аудан, га", "number", unit="га", min=0, only_for_gear_kind="seine",
              hint="только для невода (активное орудие) — обязательна и больше нуля; у сети не указывается"),
            F("catch_type", "Тип лова", "Аулау түрі", "ref", required=True, ref_entity="catch_types"),
        ],
        "species_columns": species_cols("integer", "шт", "Улов по видам, шт", "Түрлер бойынша ауланым, дана"),
    },
    {
        "code": "age_samples", "title_ru": AGE_SAMPLES_TITLE[0], "title_kk": AGE_SAMPLES_TITLE[1],
        "description": AGE_SAMPLES_DESCRIPTION,
        "period_field": "year", "system": True,
        "key_fields": ["year", "age"],
        "columns": [YEAR, AGE],
        "species_columns": species_cols("integer", "шт", *AGE_SAMPLES_SPECIES_TITLE),
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
            F("v_cr", V_CR_TITLE[0], V_CR_TITLE[1], "number", required=True, unit="м/с", min=0,
              aliases=list(V_CR_OLD), hint=V_CR_HINT),
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
