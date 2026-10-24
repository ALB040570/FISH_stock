"""
Пояснения к представлениям исходных данных (панель справа от графика):
    how  — «Как читать»: 2–4 простых пункта (RU/KK);
    now  — «Что видно сейчас»: короткий вывод по данным — только факты, которые уже есть на графике
           (сравнение со средним, минимумы и максимумы, ширина полосы, число ловов); научных заключений нет;
    next — «Что проверить дальше»: ссылки на соседние представления (код виджета шаблона мониторинга).
"""
from __future__ import annotations


def L(lang, ru, kk):
    return kk if lang == "kk" else ru


def n(v, d=None):
    """Число по-русски: пробел между разрядами, запятая."""
    if v is None:
        return "—"
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer() and abs(v) >= 100):
        return f"{int(round(v)):,}".replace(",", " ")
    a = abs(v)
    d = d if d is not None else (0 if a >= 100 else 1 if a >= 10 else 2)
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def rel(v, avg, lang):
    """«выше среднего в 2,4 раза» / «ниже на 30 %»."""
    if not avg or v is None:
        return ""
    r = v / avg
    if r >= 1.5:
        return L(lang, f"выше в {n(r, 1)} раза", f"{n(r, 1)} есе жоғары")
    if r <= 1 / 1.5 and r > 0:
        return L(lang, f"ниже в {n(1 / r, 1)} раза", f"{n(1 / r, 1)} есе төмен")
    p = (r - 1) * 100
    if abs(p) < 1:
        return L(lang, "почти на уровне", "шамамен деңгейінде")
    return L(lang, f"{'выше' if p > 0 else 'ниже'} на {n(abs(p), 0)} %", f"{n(abs(p), 0)} %-ға {'жоғары' if p > 0 else 'төмен'}")


HOW = {
    "cpue": [("Линия — средний улов за один лов: у сети на 100 м сети за постановку, у невода на 1 га облова.",
              "Сызық — бір аулаудағы орташа ауланым: ауда бір қоюға 100 м ауға, сүзекіде 1 га ауланған ауданға."),
             ("Серая полоса — где с вероятностью 95 % лежит настоящее среднее. Чем больше ловов и чем они ровнее, тем она уже.",
              "Сұр жолақ — шынайы орташа 95 % ықтималдықпен жатқан аралық. Аулау көп әрі біркелкі болса, ол тар."),
             ("Если полосы двух лет не перекрываются — разница настоящая; если перекрываются — может быть случайностью.",
              "Екі жылдың жолақтары қиылыспаса — айырмашылық шынайы; қиылысса — кездейсоқ болуы мүмкін."),
             ("Сравнивайте годы с одинаковой схемой лова: те же места, сезон и сети.",
              "Аулау тәртібі бірдей жылдарды салыстырыңыз: сол орындар, маусым және аулар.")],
    "composition": [("Столбец — все пойманные за год рыбы (100 %), цвет — доля вида.", "Баған — жылда ауланған барлық балық (100 %), түс — түрдің үлесі."),
                    ("Пунктир — доля хищных видов.", "Үзік сызық — жыртқыш түрлердің үлесі."),
                    ("Резкая смена долей — повод проверить, не изменилась ли схема лова.", "Үлестердің күрт өзгеруі — аулау тәртібі өзгермеді ме, тексеруге себеп.")],
    "hauls_count": [("Высота столбца — число ловов за год, цвет — орудие и тип лова.", "Бағанның биіктігі — жылдағы аулаулар саны, түс — құрал және аулау түрі."),
                    ("Чем меньше ловов, тем менее точны средние за этот год.", "Аулау аз болса, сол жылдың орташалары соғұрлым дәл емес.")],
    "coverage_places": [("Строка — место лова, столбец — год, число — сколько ловов там было.", "Жол — аулау орны, баған — жыл, сан — онда қанша аулау болды."),
                        ("Пустые клетки — в этот год там не ловили.", "Бос ұяшықтар — сол жылы онда ауланбаған."),
                        ("Годы сравнимы, если ловили в тех же местах.", "Сол орындарда ауланса, жылдарды салыстыруға болады.")],
    "coverage_months": [("Клетка — сколько ловов было в этом месяце года.", "Ұяшық — жылдың осы айында қанша аулау болғаны."),
                        ("Рыба в разные сезоны ловится по-разному: сравнивайте годы с похожим сезоном лова.",
                         "Балық әр маусымда әртүрлі ауланады: маусымы ұқсас жылдарды салыстырыңыз.")],
    "haul_box": [("«Ящик» охватывает половину ловов года, черта внутри — медиана (типичный лов).",
                  "«Жәшік» жылдағы аулаулардың жартысын қамтиды, ішіндегі сызық — медиана (әдеттегі аулау)."),
                 ("Усы — обычный разброс, точки — необычно большие уловы (выбросы).", "Мұрттар — әдеттегі шашырау, нүктелер — ерекше үлкен ауланымдар (шығарындылар)."),
                 ("Если выброс один, но огромный, годовая сумма держится на нём — проверьте эту строку.",
                  "Шығарынды біреу, бірақ өте үлкен болса, жылдық қосынды соған тіреледі — сол жолды тексеріңіз.")],
    "type_compare": [("Две линии — улов на усилие (сеть) в научном и в промысловом лове.", "Екі сызық — ғылыми және кәсіпшілік аулаудағы күшке шаққандағы ауланым (ау)."),
                     ("Промысел ловит там, где рыбы много, и крупной ячеёй — его линия обычно выше и медленнее падает.",
                      "Кәсіпшілік балық көп жерде және ірі ұяшықпен аулайды — оның сызығы әдетте жоғары және баяу төмендейді."),
                     ("Для оценки численности опирайтесь на научный лов.", "Санды бағалау үшін ғылыми аулауға сүйеніңіз.")],
    "age_catch_year": [("Клетка — сколько рыб возраста j поймано за год (улов каждого лова разложен по рыбам, подвергнутым биологической обработке в том же году).",
                        "Ұяшық — жылда j жасындағы қанша балық ауланғаны (әр аулау сол жылы биологиялық өңдеуден өткен балықтар бойынша жастарға бөлінген)."),
                       ("Яркая диагональ снизу-слева вверх-вправо — урожайное поколение: каждый год (строкой выше) оно на год старше (столбцом правее).", "Төменгі-сол жақтан жоғары-оңға қарай ашық диагональ — өнімді ұрпақ: жыл сайын (бір жол жоғары) ол бір жасқа үлкен (бір баған оңға).")],
    "age_catch_hauls": [("Строка — лов выбранного года, клетка — сколько рыб возраста j в нём (дробные числа — ожидаемое количество).",
                         "Жол — таңдалған жылдың аулауы, ұяшық — ондағы j жасындағы балық саны (бөлшек сан — күтілетін саны)."),
                        ("Щёлкните клетку и «Показать строки данных» — увидите расчёт лова на числах.",
                         "Ұяшықты басып, «Деректер жолдарын көрсету» — аулау есебін сандармен көресіз.")],
    "age_heatmap": [("Строка — год, столбец — возраст, клетка — доля этого возраста среди рыб, подвергнутых биологической обработке.", "Жол — жыл, баған — жас, ұяшық — биологиялық өңдеуден өткен балықтар арасындағы осы жастың үлесі."),
                    ("Урожайное поколение — яркая диагональ снизу-слева вверх-вправо: годы идут снизу вверх, поэтому через год (строкой выше) это же поколение на год старше (столбцом правее).",
                     "Өнімді ұрпақ — төменгі-сол жақтан жоғары-оңға қарай ашық диагональ: жылдар төменнен жоғары жүреді, сондықтан бір жылдан кейін (бір жол жоғары) сол ұрпақ бір жасқа үлкен (бір баған оңға)."),
                    ("Сильное поколение молодых возрастов — будущий промысловый запас.", "Жас жастардың күшті ұрпағы — болашақ кәсіптік қор.")],
    "age_vs_mean": [("Столбцы — доля каждого возраста среди рыб, подвергнутых биологической обработке, в последнем году и в среднем за другие годы.",
                     "Бағандар — соңғы жылы және басқа жылдардың орташасында биологиялық өңдеуден өткен балықтар арасындағы әр жастың үлесі."),
                    ("Возраст, которого больше обычного, — возможное сильное поколение.", "Әдеттегіден көп жас — мүмкін күшті ұрпақ.")],
    "sample_size": [("Клетка — сколько рыб вида подвергнуто биологической обработке за год.", "Ұяшық — жылда түрдің қанша балығы биологиялық өңдеуден өтті."),
                    ("Если таких рыб меньше порога «Правил замечаний», возрастной состав ненадёжен.",
                     "Мұндай балық «Ескерту ережелері» шегінен аз болса, жас құрамы сенімсіз.")],
    "mature_share": [("Левая ось — доля половозрелых рыб (старше m0) среди рыб, подвергнутых биологической обработке, правая — средний возраст.",
                      "Сол ось — биологиялық өңдеуден өткен балықтар арасындағы жыныстық жетілгендердің үлесі (m0-ден үлкен), оң ось — орташа жас."),
                     ("Рост обеих линий — стадо стареет; падение — омолаживается (пополнение или вылов старших).",
                      "Екі сызықтың өсуі — табын қартаяды; төмендеуі — жасарады (толықтыру немесе үлкендерді аулау).")],
    "growth": [("Линии — средний вес по возрастам в последние годы; полоса — от минимума до максимума за все годы.",
                "Сызықтар — соңғы жылдардағы жас бойынша орташа салмақ; жолақ — барлық жылдардағы ең аздан ең көпке дейін."),
               ("Линия ниже полосы — рыба в этот год легче обычного.", "Сызық жолақтан төмен — сол жылы балық әдеттегіден жеңіл.")],
    "weight_dev": [("Клетка — насколько вес возраста в этом году отличается от многолетнего среднего, %.",
                    "Ұяшық — осы жылғы жас салмағы көпжылдық орташадан қаншалықты өзгеше, %."),
                   ("Тёплые — тяжелее обычного, холодные — легче. Целая холодная строка — плохой год нагула.",
                    "Жылы — әдеттегіден ауыр, суық — жеңіл. Тұтас суық жол — нашар қоректену жылы.")],
    "biomass_structure": [("Столбец — масса рыб, подвергнутых биологической обработке за год (100 %), цвет — доля возрастной группы (число рыб × вес).",
                           "Баған — жылы биологиялық өңдеуден өткен балықтардың массасы (100 %), түс — жас тобының үлесі (балық саны × салмақ)."),
                          ("Показывает, на каких возрастах держится масса — их изъятие сильнее всего меняет запас.",
                           "Масса қай жастарға тірелетінін көрсетеді — оларды аулау қорды ең көп өзгертеді.")],
    "lifecycle": [("Светлая часть — молодь до возраста половозрелости m0, тёмная — половозрелые до предельного возраста m1.",
                   "Ашық бөлік — m0 жыныстық жетілу жасына дейінгі шабақтар, қою — m1 шекті жасқа дейінгі жыныстық жетілгендер."),
                  ("Ромб — до какого возраста вид служит кормом хищникам (m2).", "Ромб — түр қай жасқа дейін жыртқыштарға жем болады (m2).")],
    "species_cards": [("Значения из набора «Биологические параметры видов» — их использует расчёт.",
                       "Мәндер «Түрлердің биологиялық параметрлері» жиынтығынан — оларды есептеу пайдаланады."),
                      ("Проверьте их перед расчётом: ошибка здесь влияет на все этапы.", "Есептеу алдында тексеріңіз: мұндағы қате барлық кезеңдерге әсер етеді.")],
    "params_compare": [("Те же параметры вида на других водоёмах.", "Түрдің басқа су айдындарындағы сол параметрлері."),
                       ("Сильное отличие от других водоёмов — повод перепроверить значение или его обоснование.",
                        "Басқа су айдындарынан қатты айырмашылық — мәнді немесе оның негіздемесін қайта тексеруге себеп.")],
    "conditions": [("Линия — площадь водоёма по годам (по сути — уровень воды).", "Сызық — жылдар бойынша су айдынының ауданы (мәні бойынша — су деңгейі)."),
                   ("Плитки — сколько раз менялись длина и время стоянки сети: каждая смена мешает сравнивать годы.",
                    "Плиткалар — ау ұзындығы мен тұру уақыты неше рет өзгерді: әр өзгеріс жылдарды салыстыруға кедергі.")],
    "quota": [("Столбец — ПДУ НПЦ за год, цвет — вид; пунктир — общий итог.", "Баған — жылдағы ҒӨО ШРА, түс — түр; үзік сызық — жалпы жиынтық.")],
    "quota_change": [("Столбец — на сколько процентов изменилась квота вида к прошлому году.", "Баған — түрдің квотасы өткен жылға қарағанда неше пайызға өзгерді."),
                     ("Красный — квота уменьшена.", "Қызыл — квота азайтылған.")],
    "quota_vs_stock": [("Столбцы — квота (т, левая ось), линия — оценка запаса НПЦ (тыс. шт, правая ось).",
                        "Бағандар — квота (т, сол ось), сызық — ҒӨО қор бағасы (мың дана, оң ось)."),
                       ("Обычно квота следует за запасом; расхождение направлений — повод разобраться.",
                        "Әдетте квота қорға ілеседі; бағыттардың алшақтығы — анықтауға себеп.")],
    "completeness": [("Клетка — в какой доле ловов года вид учитывался.", "Ұяшық — түр жылдағы аулаулардың қандай үлесінде есепке алынды."),
                     ("Меньше 100 % — в части ловов вид не записывали (пусто), это не то же, что «не поймали» (0).",
                      "100 %-дан аз — аулаулардың бір бөлігінде түр жазылмаған (бос), бұл «ауланбады» (0) дегенмен бірдей емес.")],
    "quality": [("Ошибки нужно исправить до расчёта, предупреждения — проверить, «к сведению» — учесть.",
                 "Қателерді есептеуге дейін түзету, ескертулерді тексеру, «назар аударыңыз» — ескеру керек."),
                ("Щелчок по строке открывает сами записи.", "Жолды басу жазбалардың өзін ашады.")],
    "overview": [("Плитки — что загружено и за какие годы; щелчок открывает раздел.", "Плиткалар — не жүктелді және қай жылдар үшін; басу бөлімді ашады.")],
    "signals": [("Замечания собраны по правилам с порогами — их можно настроить в «Правилах замечаний».",
                 "Ескертулер шектері бар ережелер бойынша жиналған — оларды «Ескерту ережелерінде» баптауға болады."),
                ("Замечание — повод посмотреть внимательнее, а не вывод.", "Ескерту — мұқият қарауға себеп, қорытынды емес.")],
    "traffic": [("Строка — вид: мини-график улова на усилие и показатели последнего года.",
                 "Жол — түр: күшке шаққандағы ауланымның шағын графигі және соңғы жыл көрсеткіштері."),
                ("Красный — заметное снижение, зелёный — заметный рост (пороги из «Правил замечаний»).",
                 "Қызыл — айтарлықтай төмендеу, жасыл — айтарлықтай өсу («Ескерту ережелері» шектері)."),
                ("Щелчок по строке открывает «Все данные по виду».", "Жолды басу «Түр бойынша барлық деректерді» ашады.")],
    "journal": [("Все ловы набора; фильтры сверху, сортировка — щелчком по заголовку.", "Жиынтықтың барлық аулаулары; сүзгілер жоғарыда, сұрыптау — тақырыпты басу."),
                ("Строка «Итого» считает только отфильтрованные ловы; в Excel выгружается то же.",
                 "«Барлығы» жолы тек сүзілген аулауларды есептейді; Excel-ге де сол жүктеледі.")],
}

# что проверить дальше: (код виджета, RU, KK)
NEXT = {
    "cpue": [("c_places", "Где ловили в последний год", "Соңғы жылы қай жерде ауланды"),
             ("a_heat", "Возрастной состав — нет ли урожайного поколения", "Жас құрамы — өнімді ұрпақ жоқ па"),
             ("c_box", "Разброс уловов за лов", "Бір аулаудағы шашырау")],
    "haul_box": [("d_journal", "Журнал ловов", "Аулаулар журналы")],
    "composition": [("ov_traffic", "Светофор видов", "Түрлер бағдаршамы"), ("c_places", "Охват мест", "Орындарды қамту")],
    "hauls_count": [("c_places", "Охват мест", "Орындарды қамту"), ("c_months", "Охват месяцев", "Айларды қамту")],
    "coverage_places": [("c_months", "Охват месяцев", "Айларды қамту"), ("d_journal", "Журнал ловов", "Аулаулар журналы")],
    "coverage_months": [("c_places", "Охват мест", "Орындарды қамту")],
    "type_compare": [("c_cpue_net", "Улов на усилие: сеть", "Күшке шаққандағы ауланым: ау")],
    "age_heatmap": [("a_size", "Размер проб", "Сынамалар көлемі"), ("c_age_year", "Улов по возрастам за год", "Жыл бойынша жас ауланымы")],
    "age_vs_mean": [("a_heat", "Возрастной состав по годам", "Жылдар бойынша жас құрамы")],
    "sample_size": [("a_heat", "Возрастной состав", "Жас құрамы")],
    "mature_share": [("a_heat", "Возрастной состав", "Жас құрамы"), ("p_life", "Жизненный цикл (m0)", "Өмірлік цикл (m0)")],
    "growth": [("w_dev", "Отклонение веса", "Салмақ ауытқуы")],
    "weight_dev": [("p_cond", "Условия по годам (уровень воды)", "Жылдар бойынша жағдайлар (су деңгейі)")],
    "biomass_structure": [("a_heat", "Возрастной состав", "Жас құрамы")],
    "age_catch_year": [("a_heat", "Возрастной состав", "Жас құрамы")],
    "age_catch_hauls": [("d_journal", "Журнал ловов", "Аулаулар журналы")],
    "quota_change": [("ov_traffic", "Светофор видов", "Түрлер бағдаршамы")],
    "quota_vs_stock": [("c_cpue_net", "Улов на усилие", "Күшке шаққандағы ауланым")],
    "completeness": [("d_journal", "Журнал ловов", "Аулаулар журналы")],
    "traffic": [("ov_signals", "На что обратить внимание", "Неге назар аудару керек")],
    "signals": [("ov_traffic", "Светофор видов", "Түрлер бағдаршамы")],
}


# ------------------------------------------------------------------ «Что видно сейчас»
def _pts(rows, key="mean"):
    return [(r["year"], r[key]) for r in rows if isinstance(r.get("year"), int) and r.get(key) is not None]


def now_cpue(res, lang, opt=None, sp_name=None, **_):
    opt = opt or {}
    rows = res.get("rows") or []
    pts = _pts(rows)
    if not pts:
        return []
    out = []
    unit = L(lang, "шт на 100 м сети" if opt.get("gear_kind", "net") == "net" else "шт на 1 га",
             "100 м ауға дана" if opt.get("gear_kind", "net") == "net" else "1 га-ға дана")
    who = sp_name or L(lang, "все виды", "барлық түрлер")
    last = next(r for r in reversed(rows) if r.get("mean") is not None)
    y1, v1 = last["year"], last["mean"]
    out.append(L(lang, f"{who.capitalize()}: в {y1} г. — {n(v1)} {unit} (ловов: {last['n']}).",
                 f"{who.capitalize()}: {y1} жылы — {n(v1)} {unit} (аулаулар: {last['n']})."))
    prev = [(y, v) for y, v in pts if y < y1][-5:]
    if prev:
        avg = sum(v for _, v in prev) / len(prev)
        out.append(L(lang, f"Среднее за {prev[0][0]}–{prev[-1][0]} — {n(avg)}: последний год {rel(v1, avg, lang)}.",
                     f"{prev[0][0]}–{prev[-1][0]} орташасы — {n(avg)}: соңғы жыл {rel(v1, avg, lang)}."))
    lo, hi = last.get("lo"), last.get("hi")
    if lo is not None and hi is not None and v1:
        wide = (hi - lo) / (2 * v1) > 0.5
        out.append(L(lang, f"Полоса {'широкая' if wide else 'узкая'} (от {n(lo)} до {n(hi)}): "
                           + ("значение ненадёжно — мало ловов или большой разброс." if wide else "значение известно достаточно точно."),
                     f"Жолақ {'кең' if wide else 'тар'} ({n(lo)}-ден {n(hi)}-ге дейін): "
                     + ("мән сенімсіз — аулау аз немесе шашырау үлкен." if wide else "мән жеткілікті дәл белгілі.")))
        p0 = next((r for r in reversed(rows) if r["year"] < y1 and r.get("lo") is not None), None)
        if p0:
            overlap = not (p0["hi"] < lo or hi < p0["lo"])
            out.append(L(lang, f"С {p0['year']} г. полосы {'перекрываются — разница может быть случайной' if overlap else 'не перекрываются — разница, скорее всего, настоящая'}.",
                         f"{p0['year']} жылмен жолақтар {'қиылысады — айырмашылық кездейсоқ болуы мүмкін' if overlap else 'қиылыспайды — айырмашылық шынайы болуы ықтимал'}."))
    vals = [v for _, v in pts]
    if len(vals) >= 3 and v1 in (max(vals), min(vals)):
        out.append(L(lang, f"Это {'максимум' if v1 == max(vals) else 'минимум'} за {len(vals)} лет.",
                     f"Бұл {len(vals)} жылдағы ең {'жоғары' if v1 == max(vals) else 'төмен'} мән."))
    return out


def now_composition(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    last = rows[-1]
    cols = {c["code"]: c["title"] for c in res["columns"]}
    sp = sorted(((k, v) for k, v in last.items() if k not in ("year", "_pred") and v), key=lambda x: -x[1])[:3]
    out = [L(lang, f"В {last['year']} г. больше всего в улове: " + ", ".join(f"{cols[k]} {n(v, 0)} %" for k, v in sp) + ".",
             f"{last['year']} жылы ауланымда ең көбі: " + ", ".join(f"{cols[k]} {n(v, 0)} %" for k, v in sp) + ".")]
    pr = [r["_pred"] for r in rows[:-1] if r.get("_pred") is not None]
    if last.get("_pred") is not None and pr:
        avg = sum(pr) / len(pr)
        out.append(L(lang, f"Доля хищных — {n(last['_pred'], 0)} % (в среднем за прошлые годы {n(avg, 0)} %).",
                     f"Жыртқыштар үлесі — {n(last['_pred'], 0)} % (өткен жылдардың орташасы {n(avg, 0)} %)."))
    return out


def now_hauls(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    tot = [(r["year"], sum(v for k, v in r.items() if k != "year" and isinstance(v, (int, float)))) for r in rows]
    y1, v1 = tot[-1]
    avg = sum(v for _, v in tot[:-1]) / max(1, len(tot) - 1)
    return [L(lang, f"В {y1} г. — {v1} ловов; в среднем за прошлые годы {n(avg, 0)} ({rel(v1, avg, lang)}).",
              f"{y1} жылы — {v1} аулау; өткен жылдардың орташасы {n(avg, 0)} ({rel(v1, avg, lang)}).")]


def now_places(res, lang, **_):
    rows = res.get("rows") or []
    years = [c["code"] for c in res["columns"] if c["code"].isdigit()]
    if not rows or not years:
        return []
    y1 = years[-1]
    used = [r["place"] for r in rows if r.get(y1)]
    regular = [r for r in rows if r.get("_years", 0) >= max(2, len(years) / 2)]
    miss = [r["place"] for r in regular if not r.get(y1)]
    out = [L(lang, f"В {y1} г. ловили на {len(used)} местах из {len(rows)}; постоянных мест — {len(regular)}.",
             f"{y1} жылы {len(rows)} орынның {len(used)}-інде ауланды; тұрақты орындар — {len(regular)}.")]
    if miss:
        out.append(L(lang, "Пропущены постоянные места: " + ", ".join(miss[:6]) + ("…" if len(miss) > 6 else "") + " — сравнение с прошлыми годами может быть искажено.",
                     "Тұрақты орындар өткізілген: " + ", ".join(miss[:6]) + ("…" if len(miss) > 6 else "") + " — өткен жылдармен салыстыру бұрмалануы мүмкін."))
    else:
        out.append(L(lang, "Все постоянные места охвачены.", "Барлық тұрақты орындар қамтылған."))
    return out


def now_months(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    mcols = [c for c in res["columns"] if c["code"].startswith("m")]
    last = rows[-1]
    used = [c["title"] for c in mcols if last.get(c["code"])]
    typical = [c["title"] for c in mcols if sum(1 for r in rows if r.get(c["code"])) >= len(rows) / 2]
    return [L(lang, f"В {last['year']} г. ловили: {', '.join(used) or '—'}; обычно — {', '.join(typical) or '—'}.",
              f"{last['year']} жылы ауланды: {', '.join(used) or '—'}; әдетте — {', '.join(typical) or '—'}.")]


def now_box(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("n")]
    if not rows:
        return []
    r = rows[-1]
    out = [L(lang, f"В {r['year']} г. половина ловов дала от {n(r['q1'])} до {n(r['q3'])} шт, типичный лов (медиана) — {n(r['median'])} шт.",
             f"{r['year']} жылы аулаулардың жартысы {n(r['q1'])}-ден {n(r['q3'])} данаға дейін берді, әдеттегі аулау (медиана) — {n(r['median'])} дана.")]
    if r.get("max_share") is not None:
        out.append(L(lang, f"Самый большой лов — {n(r['max'], 0)} шт, это {n(r['max_share'], 0)} % годового улова; выбросов — {r['outliers']}.",
                     f"Ең үлкен аулау — {n(r['max'], 0)} дана, бұл жылдық ауланымның {n(r['max_share'], 0)} %-ы; шығарындылар — {r['outliers']}."))
    return out


def now_types(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("scientific") is not None and r.get("commercial") is not None]
    if not rows:
        return []
    r = rows[-1]
    return [L(lang, f"В {r['year']} г. промысловый улов на усилие — {n(r['commercial'])}, научный — {n(r['scientific'])}: промысловый {rel(r['commercial'], r['scientific'], lang)}.",
              f"{r['year']} жылы кәсіпшілік күшке шаққандағы ауланым — {n(r['commercial'])}, ғылыми — {n(r['scientific'])}: кәсіпшілік {rel(r['commercial'], r['scientific'], lang)}.")]


def _dominant(row, prefix=""):
    vals = [(k, v) for k, v in row.items() if k not in ("year", "_n") and isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return None, None
    k, v = max(vals, key=lambda x: x[1])
    return k.lstrip("a"), v


def now_age_heat(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    dom = [(r["year"], *_dominant(r)) for r in rows[-4:]]
    out = [L(lang, "Самый многочисленный возраст среди рыб, подвергнутых биологической обработке: " + "; ".join(f"{y} — j={a} ({n(v, 0)} %)" for y, a, v in dom if a) + ".",
             "Биологиялық өңдеуден өткен балықтар арасындағы ең көп жас: " + "; ".join(f"{y} — j={a} ({n(v, 0)} %)" for y, a, v in dom if a) + ".")]
    ages = [int(a) for _, a, _ in dom if a]
    if len(ages) >= 3 and all(b - a == 1 for a, b in zip(ages, ages[1:])):
        out.append(L(lang, "Ведущий возраст каждый год становится на год старше — одно сильное поколение идёт по диагонали.",
                     "Жетекші жас жыл сайын бір жасқа үлкейеді — бір күшті ұрпақ диагональ бойымен жүреді."))
    return out


def now_age_vs_mean(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("year") is not None and r.get("avg") is not None]
    if not rows:
        return []
    d = sorted(rows, key=lambda r: r["year"] - r["avg"])
    hi, lo = d[-1], d[0]
    return [L(lang, f"Больше обычного — возраст j={hi['age']} ({n(hi['year'], 0)} % против {n(hi['avg'], 0)} %); меньше обычного — j={lo['age']} ({n(lo['year'], 0)} % против {n(lo['avg'], 0)} %).",
              f"Әдеттегіден көп — j={hi['age']} жасы ({n(hi['avg'], 0)} %-ға қарсы {n(hi['year'], 0)} %); әдеттегіден аз — j={lo['age']} ({n(lo['avg'], 0)} %-ға қарсы {n(lo['year'], 0)} %).")]


def now_sample(res, lang, rules=None, **_):
    rows = res.get("rows") or []
    years = [c["code"] for c in res["columns"] if c["code"].isdigit()]
    if not rows or not years:
        return []
    y1 = years[-1]
    lim = ((rules or {}).get("small_sample") or {}).get("params", {}).get("min_fish", 30)
    small = [f"{r['species']} — {n(r[y1], 0)}" for r in rows if r.get(y1) and r[y1] < lim]
    total = sum(r.get(y1) or 0 for r in rows)
    out = [L(lang, f"В {y1} г. проанализировано {n(total, 0)} рыб.", f"{y1} жылы {n(total, 0)} балық талданды.")]
    if small:
        out.append(L(lang, f"Меньше {lim} рыб: " + ", ".join(small) + " — возрастной состав этих видов ненадёжен.",
                     f"{lim} балықтан аз: " + ", ".join(small) + " — бұл түрлердің жас құрамы сенімсіз."))
    return out


def now_mature(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("share") is not None]
    if len(rows) < 2:
        return []
    last = rows[-1]
    avg = sum(r["share"] for r in rows[:-1]) / (len(rows) - 1)
    ma = [r["mean_age"] for r in rows[:-1] if r.get("mean_age") is not None]
    out = [L(lang, f"В {last['year']} г. половозрелых {n(last['share'], 0)} % (в среднем {n(avg, 0)} %).",
             f"{last['year']} жылы жыныстық жетілгендер {n(last['share'], 0)} % (орташа {n(avg, 0)} %).")]
    if ma and last.get("mean_age") is not None:
        out.append(L(lang, f"Средний возраст {n(last['mean_age'], 1)} против {n(sum(ma) / len(ma), 1)} в среднем — стадо "
                           + ("стареет." if last["mean_age"] > sum(ma) / len(ma) else "омолаживается."),
                     f"Орташа жас {n(last['mean_age'], 1)}, орташа {n(sum(ma) / len(ma), 1)} — табын "
                     + ("қартаяды." if last["mean_age"] > sum(ma) / len(ma) else "жасарады.")))
    return out


def now_growth(res, lang, **_):
    rows = res.get("rows") or []
    years = [c["code"] for c in res["columns"] if c["code"].isdigit()]
    if not rows or not years:
        return []
    y1 = years[-1]
    d = [(r[y1] / r["avg"] - 1) * 100 for r in rows if r.get(y1) and r.get("avg")]
    if not d:
        return []
    m = sum(d) / len(d)
    return [L(lang, f"В {y1} г. рыба в среднем по возрастам {'тяжелее' if m > 0 else 'легче'} многолетнего на {n(abs(m), 0)} %.",
              f"{y1} жылы балық жастар бойынша орташа көпжылдықтан {n(abs(m), 0)} %-ға {'ауыр' if m > 0 else 'жеңіл'}.")]


def now_weight_dev(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    last = rows[-1]
    vals = [(k, v) for k, v in last.items() if k != "year" and v is not None]
    if not vals:
        return []
    m = sum(v for _, v in vals) / len(vals)
    k, v = max(vals, key=lambda x: abs(x[1]))
    return [L(lang, f"В {last['year']} г. среднее отклонение веса по возрастам {'+' if m > 0 else ''}{n(m, 0)} %; сильнее всего у j={k} ({'+' if v > 0 else ''}{n(v, 0)} %).",
              f"{last['year']} жылы жастар бойынша салмақтың орташа ауытқуы {'+' if m > 0 else ''}{n(m, 0)} %; ең көбі j={k} ({'+' if v > 0 else ''}{n(v, 0)} %).")]


def now_biomass(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    last = rows[-1]
    vals = sorted(((k, v) for k, v in last.items() if k != "year" and v), key=lambda x: -x[1])[:3]
    return [L(lang, f"В {last['year']} г. масса рыб, подвергнутых биологической обработке, держится на возрастах: " + ", ".join(f"j={k} ({n(v, 0)} %)" for k, v in vals) + ".",
              f"{last['year']} жылы биологиялық өңдеуден өткен балықтар массасы мына жастарға тіреледі: " + ", ".join(f"j={k} ({n(v, 0)} %)" for k, v in vals) + ".")]


def now_lifecycle(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    early = min(rows, key=lambda r: r["m0"])
    old = max(rows, key=lambda r: r["m1"])
    preds = [r["species"] for r in rows if r.get("is_predator")]
    return [L(lang, f"Раньше всех созревает {early['species']} (m0 = {early['m0']}), дольше всех живёт {old['species']} (m1 = {old['m1']}).",
              f"Ең ерте {early['species']} жетіледі (m0 = {early['m0']}), ең ұзақ {old['species']} өмір сүреді (m1 = {old['m1']})."),
            L(lang, "Хищные: " + (", ".join(preds) or "нет") + ".", "Жыртқыштар: " + (", ".join(preds) or "жоқ") + ".")]


def now_conditions(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("lake_area_km2") is not None]
    if len(rows) < 2:
        return []
    a, b = rows[0], rows[-1]
    out = [L(lang, f"Площадь водоёма: {n(a['lake_area_km2'], 0)} км² в {a['year']} г. и {n(b['lake_area_km2'], 0)} км² в {b['year']} г. ({rel(b['lake_area_km2'], a['lake_area_km2'], lang)}).",
             f"Су айдынының ауданы: {a['year']} жылы {n(a['lake_area_km2'], 0)} км² және {b['year']} жылы {n(b['lake_area_km2'], 0)} км² ({rel(b['lake_area_km2'], a['lake_area_km2'], lang)}).")]
    ch = sum(t["value"] for t in res.get("tiles") or [] if isinstance(t.get("value"), int))
    out.append(L(lang, "Схема постановки сетей не менялась — годы сравнимы." if not ch else f"Схема постановки сетей менялась {ch} раз — сравнивайте годы осторожно.",
                 "Ау қою тәртібі өзгермеген — жылдар салыстырмалы." if not ch else f"Ау қою тәртібі {ch} рет өзгерді — жылдарды абайлап салыстырыңыз."))
    return out


def now_quota(res, lang, **_):
    rows = res.get("rows") or []
    if len(rows) < 2:
        return []
    a, b = rows[-2], rows[-1]
    return [L(lang, f"ПДУ НПЦ всего: {n(b['_total'], 0)} т в {b['year']} г., {n(a['_total'], 0)} т в {a['year']} г. ({rel(b['_total'], a['_total'], lang)}).",
              f"ҒӨО ШРА барлығы: {b['year']} жылы {n(b['_total'], 0)} т, {a['year']} жылы {n(a['_total'], 0)} т ({rel(b['_total'], a['_total'], lang)}).")]


def now_quota_change(res, lang, **_):
    t = [x for x in res.get("tiles") or [] if x.get("value") is not None]
    if not t:
        return []
    up = max(t, key=lambda x: x["value"])
    dn = min(t, key=lambda x: x["value"])
    return [L(lang, f"Больше всего выросла квота: {up['label']} ({'+' if up['value'] > 0 else ''}{n(up['value'], 0)} %); меньше всего — {dn['label']} ({'+' if dn['value'] > 0 else ''}{n(dn['value'], 0)} %).",
              f"Квота ең көп өскен: {up['label']} ({'+' if up['value'] > 0 else ''}{n(up['value'], 0)} %); ең аз — {dn['label']} ({'+' if dn['value'] > 0 else ''}{n(dn['value'], 0)} %).")]


def now_quota_stock(res, lang, **_):
    rows = [r for r in res.get("rows") or [] if r.get("quota") is not None and r.get("stock") is not None]
    if len(rows) < 2:
        return []
    a, b = rows[-2], rows[-1]
    dq, ds = b["quota"] - a["quota"], b["stock"] - a["stock"]
    same = (dq >= 0) == (ds >= 0)
    return [L(lang, f"{b['year']} к {a['year']}: квота {rel(b['quota'], a['quota'], lang)}, запас НПЦ {rel(b['stock'], a['stock'], lang)} — "
                    + ("направления совпадают." if same else "направления расходятся."),
              f"{b['year']} — {a['year']}: квота {rel(b['quota'], a['quota'], lang)}, ҒӨО қоры {rel(b['stock'], a['stock'], lang)} — "
              + ("бағыттар сәйкес." if same else "бағыттар алшақ."))]


def now_completeness(res, lang, **_):
    rows = res.get("rows") or []
    years = [c["code"] for c in res["columns"] if c["code"].isdigit()]
    if not rows or not years:
        return []
    y1 = years[-1]
    low = [f"{r['species']} {n(r[y1], 0)} %" for r in rows if r.get(y1) is not None and r[y1] < 100]
    return [L(lang, f"В {y1} г. все виды учитывались во всех ловах." if not low else f"В {y1} г. не во всех ловах учитывались: " + ", ".join(low) + ".",
              f"{y1} жылы барлық түрлер барлық аулауларда есепке алынды." if not low else f"{y1} жылы барлық аулауларда есепке алынбағандар: " + ", ".join(low) + ".")]


def now_quality(res, lang, **_):
    t = {x["label"]: x["value"] for x in res.get("tiles") or []}
    vals = list(t.values())
    if len(vals) < 3:
        return []
    return [L(lang, f"Ошибок — {vals[0]}, предупреждений — {vals[1]}, к сведению — {vals[2]}." + (" Ошибки исправьте до расчёта." if vals[0] else ""),
              f"Қателер — {vals[0]}, ескертулер — {vals[1]}, назар аударыңыз — {vals[2]}." + (" Қателерді есептеуге дейін түзетіңіз." if vals[0] else ""))]


def now_signals(res, lang, **_):
    s = res.get("signals") or []
    if not s:
        return [L(lang, "По текущим порогам замечаний нет.", "Ағымдағы шектер бойынша ескертулер жоқ.")]
    w = sum(1 for x in s if x["level"] in ("warning", "error"))
    return [L(lang, f"Замечаний: {len(s)}, из них требующих внимания — {w}.", f"Ескертулер: {len(s)}, оның ішінде назар аударуды қажет ететін — {w}.")]


def now_traffic(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    dn = [r["species"] for r in rows if r["_levels"].get("cpue_change") == "down"]
    up = [r["species"] for r in rows if r["_levels"].get("cpue_change") == "up"]
    out = []
    if dn:
        out.append(L(lang, "Заметное снижение улова на усилие: " + ", ".join(dn) + ".", "Күшке шаққандағы ауланымның айтарлықтай төмендеуі: " + ", ".join(dn) + "."))
    if up:
        out.append(L(lang, "Заметный рост: " + ", ".join(up) + ".", "Айтарлықтай өсу: " + ", ".join(up) + "."))
    if not out:
        out.append(L(lang, "Ни у одного вида улов на усилие не вышел за пороги.", "Бірде-бір түрдің күшке шаққандағы ауланымы шектен шықпады."))
    return out


def now_age_catch_year(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    last = rows[-1]
    vals = [(k[1:], v) for k, v in last.items() if k.startswith("a") and v]
    if not vals:
        return []
    tot = sum(v for _, v in vals)
    k, v = max(vals, key=lambda x: x[1])
    return [L(lang, f"В {last['year']} г. больше всего поймано рыб возраста j={k}: {n(v, 0)} шт ({n(v / tot * 100, 0)} % улова).",
              f"{last['year']} жылы j={k} жасындағы балық ең көп ауланды: {n(v, 0)} дана (ауланымның {n(v / tot * 100, 0)} %-ы).")]


def now_age_catch_hauls(res, lang, **_):
    rows = res.get("rows") or []
    if not rows:
        return []
    big = max(rows, key=lambda r: r.get("total") or 0)
    return [L(lang, f"{res.get('year')} г.: ловов — {len(rows)}; самый большой — №{big['haul']} ({big['date']}, {big['place']}): {n(big['total'], 0)} шт.",
              f"{res.get('year')} ж.: аулаулар — {len(rows)}; ең үлкені — №{big['haul']} ({big['date']}, {big['place']}): {n(big['total'], 0)} дана.")]


def now_journal(res, lang, **_):
    rows = res.get("rows") or []
    return [L(lang, f"Ловов в наборе: {len(rows)}.", f"Жиынтықтағы аулаулар: {len(rows)}.")] if rows else []


def now_overview(res, lang, **_):
    tiles = res.get("tiles") or []
    if not tiles:
        return []
    out = []
    ranges = {t["label"]: t["value"] for t in tiles if isinstance(t.get("value"), str) and "–" in t["value"]}
    if ranges:
        vals = set(ranges.values())
        if len(vals) == 1:
            v = next(iter(vals))
            out.append(L(lang, f"Все наборы данных охватывают одни и те же годы: {v}.",
                         f"Барлық деректер жиынтығы бірдей жылдарды қамтиды: {v}."))
        else:
            lst = "; ".join(f"{k} — {v}" for k, v in ranges.items())
            out.append(L(lang, "Годы наборов различаются: " + lst + ".", "Жиынтықтардың жылдары әртүрлі: " + lst + "."))
    q = next((t for t in tiles if t.get("section") == "quality"), None)
    if q is not None:
        out.append(L(lang, f"Замечаний к данным: {q['value']}" + (" — подробности в разделе «Качество данных»." if q["value"] else "."),
                     f"Деректерге ескертулер: {q['value']}" + (" — толығырақ «Деректер сапасы» бөлімінде." if q["value"] else ".")))
    return out


NOW = {"overview": now_overview, "cpue": now_cpue, "composition": now_composition, "hauls_count": now_hauls, "coverage_places": now_places,
       "coverage_months": now_months, "haul_box": now_box, "type_compare": now_types, "age_heatmap": now_age_heat,
       "age_vs_mean": now_age_vs_mean, "sample_size": now_sample, "mature_share": now_mature, "growth": now_growth,
       "weight_dev": now_weight_dev, "biomass_structure": now_biomass, "lifecycle": now_lifecycle, "conditions": now_conditions,
       "quota": now_quota, "quota_change": now_quota_change, "quota_vs_stock": now_quota_stock, "completeness": now_completeness,
       "quality": now_quality, "signals": now_signals, "traffic": now_traffic, "age_catch_year": now_age_catch_year,
       "age_catch_hauls": now_age_catch_hauls, "journal": now_journal}


from . import calc_explain  # noqa: E402

HOW.update(calc_explain.HOW)
NEXT.update(calc_explain.NEXT)
NOW.update(calc_explain.NOW)


def explain(view: str, res: dict, lang: str, opt: dict, sp_name: str | None, rules: dict | None = None) -> dict:
    how = [L(lang, ru, kk) for ru, kk in HOW.get(view, [])]
    try:
        f = NOW.get(view)
        now = f(res, lang, opt=opt, sp_name=sp_name, rules=rules) if f else []
    except (KeyError, TypeError, ValueError, ZeroDivisionError, StopIteration):
        now = []
    nxt = [{"widget": w, "label": L(lang, ru, kk)} for w, ru, kk in NEXT.get(view, [])]
    return {"how": how, "now": now, "next": nxt}
