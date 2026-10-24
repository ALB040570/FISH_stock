"""
Статья справки «Слайды мониторинга: как читать» (monitoring-slides, RU и KK) — все слайды шаблона мониторинга по
вкладкам и разделам: название, подзаголовок и пояснение «Как читать», которое показывается справа от слайда.
Источник — services/dashboards/app/templates.py и explain.py / calc_explain.py, поэтому статья всегда совпадает
с приложением. После правки шаблона или пояснений:

    python tools/gen_slides_help.py

(тест services/dashboards/tests/test_slides_help.py проверяет, что статья не отстала).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "services" / "help" / "app" / "content"

TEXT = {
    "ru": {
        "title": "Слайды мониторинга: как читать",
        "intro": ("Все слайды мониторинга водоёма по вкладкам и разделам — с тем же пояснением «Как читать», что и "
                  "на панели справа от слайда (значок книги). Статья собирается из шаблона мониторинга, поэтому совпадает "
                  "с приложением. Числа на слайдах — данные выбранного водоёма; что видно на них сейчас, подсказывает "
                  "та же панель (значок глаза)."),
        "where": "Откуда данные",
        "tabs": {
            "data": "наборы исходных данных водоёма (последние версии) — см. также [Исходные данные в мониторинге](help:monitoring-data).",
            "catchability": "основные расчёты a (уловистость сети) и b (уловистость невода); доля рыбы в сети σ — из d.",
            "stock": "основные расчёты c, d (оценки по ловам), e, f, g (годовой и окончательный запас), i (модель).",
            "pdu": "основные расчёты h (лимиты в экземплярах особей по ПДУ НПЦ) и j (прогноз и ПДУ по модели) — см. также [Как читать вкладку ПДУ](help:pdu-reading).",
        },
        "tab": "Вкладка", "section": "Раздел", "next": "Дальше",
        "outro": ("Какие расчёты стали основными и когда считались — кнопка состояния рядом с выбором водоёма; "
                  "подробнее — [Мониторинг водоёма](help:monitoring). Как устроены сами расчёты — раздел "
                  "[Методика расчёта](help:method-overview)."),
    },
    "kk": {
        "title": "Мониторинг слайдтары: қалай оқу керек",
        "intro": ("Су айдыны мониторингінің барлық слайдтары қойындылар мен бөлімдер бойынша — слайдтың оң жағындағы "
                  "панельдегі (кітап белгісі) «Қалай оқу керек» түсіндірмесімен бірге. Мақала мониторинг үлгісінен "
                  "жиналады, сондықтан қосымшамен сәйкес келеді. Слайдтардағы сандар — таңдалған су айдынының деректері; "
                  "оларда қазір не көрінетінін сол панель (көз белгісі) айтады."),
        "where": "Деректер қайдан",
        "tabs": {
            "data": "су айдынының бастапқы деректер жиынтықтары (соңғы нұсқалары) — сондай-ақ [Мониторингтегі бастапқы деректер](help:monitoring-data).",
            "catchability": "a (аудың аулағыштығы) және b (сүзекінің аулағыштығы) негізгі есептеулері; аудағы балық үлесі σ — d-дан.",
            "stock": "c, d (аулаулар бойынша бағалар), e, f, g (жылдық және түпкілікті қор), i (модель) негізгі есептеулері.",
            "pdu": "h (ҒӨО ШРА бойынша дарақ данасымен лимиттер) және j (болжам және модель бойынша ШРА) негізгі есептеулері — сондай-ақ [ШРА қойындысын қалай оқу керек](help:pdu-reading).",
        },
        "tab": "Қойынды", "section": "Бөлім", "next": "Әрі қарай",
        "outro": ("Қай есептеулер негізгі болғаны және қашан есептелгені — су айдынын таңдаудың жанындағы күй түймесі; "
                  "толығырақ — [Су айдынының мониторингі](help:monitoring). Есептеулердің өзі қалай құрылғаны — "
                  "[Есептеу әдістемесі](help:method-overview) бөлімі."),
    },
}


def _modules():
    """Шаблоны и пояснения сервиса дашбордов — под своим именем пакета (в тестах имя app занято другими сервисами)."""
    name = "fs_dashboards_app"
    if name not in sys.modules:
        pkg = REPO / "services" / "dashboards" / "app"
        spec = importlib.util.spec_from_file_location(name, pkg / "__init__.py", submodule_search_locations=[str(pkg)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return importlib.import_module(name + ".templates"), importlib.import_module(name + ".explain")


def build(lang: str) -> str:
    templates, explain = _modules()
    T = TEXT[lang]
    tl = "title_kk" if lang == "kk" else "title_ru"
    sl = "subtitle_kk" if lang == "kk" else "subtitle_ru"
    by_id = {w["id"]: w for w in templates.MONITORING["widgets"]}
    out = [f"# {T['title']}", "", T["intro"], ""]
    for tab in templates.MONITORING["tabs"]:
        ws = [w for w in templates.MONITORING["widgets"] if w["tab"] == tab["code"]]
        if not ws:
            continue
        out += [f"## {T['tab']} «{tab[tl]}»", "", f"*{T['where']}:* {T['tabs'].get(tab['code'], '')}", ""]
        for sec in tab.get("sections", []):
            sws = [w for w in ws if w["section"] == sec["code"]]
            if not sws:
                continue
            out += [f"### {T['section']} «{sec[tl]}»", ""]
            for w in sws:
                view = w["source"]["view"]
                sub = (w.get(sl) or "").strip()
                out.append(f"**{w[tl]}**" + (f" — {sub}" if sub else ""))
                out.append("")
                for ru, kk in explain.HOW.get(view, []):
                    out.append(f"- {(kk if lang == 'kk' else ru).strip()}")
                nxt = [lab for wid, ru_l, kk_l in explain.NEXT.get(view, []) if wid in by_id
                       for lab in [(kk_l if lang == "kk" else ru_l)]]
                if nxt:
                    out.append(f"- *{T['next']}:* " + "; ".join(nxt) + ".")
                out.append("")
    out += [T["outro"], ""]
    return "\n".join(out)


def path(lang: str) -> Path:
    return CONTENT / lang / "monitoring-slides.md"


if __name__ == "__main__":
    for lg in ("ru", "kk"):
        path(lg).write_text(build(lg), encoding="utf-8")
        print(path(lg).relative_to(REPO))
