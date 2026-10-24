"""
Сквозная проверка интерфейса в браузере (Playwright, Chromium) на работающем приложении.

    FISH_E2E_URL=http://127.0.0.1:8080 FISH_E2E_PASSWORD=<пароль admin> python -m pytest tests/e2e -q

Предполагается, что данные Жайсана загружены (tools/seed_zhaysan.py) и выполнен хотя бы один расчёт.
Без FISH_E2E_URL тесты пропускаются.
"""
import os
import uuid

import pytest

URL = os.environ.get("FISH_E2E_URL")
PWD = os.environ.get("FISH_E2E_PASSWORD")
pytestmark = pytest.mark.skipif(not URL or not PWD, reason="нет FISH_E2E_URL / FISH_E2E_PASSWORD")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    exe = os.environ.get("FISH_E2E_CHROME")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        yield b
        b.close()


def login(page, login="admin", password=None):
    page.goto(URL + "/login")
    page.fill("input[autocomplete=username]", login)
    page.fill("input[type=password]", password or PWD)
    page.click("button[type=submit]")
    page.wait_for_url(lambda u: "/login" not in u, timeout=10000)


def test_admin_flow(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page)
    page.goto(URL + "/monitoring/")
    page.wait_for_selector("text=Зайсан (Жайсан)")
    page.goto(URL + "/monitoring/waterbody/zhaysan")
    for tab in ("Уловистость", "Запасы", "ПДУ"):
        page.get_by_text(tab, exact=True).first.click()
        page.wait_for_timeout(1500)
    page.goto(URL + "/input/datasets?wb=zhaysan")
    page.wait_for_selector("text=Уловы по ловам")
    for path in ("/design/dictionaries", "/calc/calculations?wb=zhaysan", "/calc/catalog", "/calc/params",
                 "/design/algorithms", "/monitoring/dashboards", "/admin/users", "/admin/audit", "/design/signal-rules"):
        page.goto(URL + path)
        page.wait_for_timeout(1200)
        assert page.url.startswith(URL + path.split("?")[0]), (path, page.url)
    assert not errors, errors


def _user(role, password="user-pass-1"):
    """Новый пользователь роли (через API администратора); возвращает логин."""
    import httpx
    api = httpx.Client(base_url=URL + "/api", timeout=30)
    tok = api.post("/users/auth/login", json={"login": "admin", "password": PWD}).json()["access_token"]
    login_name = f"{role}_" + uuid.uuid4().hex[:6]
    r = api.post("/users/users", headers={"Authorization": f"Bearer {tok}"},
                 json={"login": login_name, "name": "Коллега Тест", "role": role, "password": password})
    assert r.status_code == 201, r.text
    return login_name


def _change_password(page, old, new):
    page.wait_for_selector("text=Смените пароль")
    inputs = page.locator(".el-dialog input[type=password]")
    inputs.nth(0).fill(old)
    inputs.nth(1).fill(new)
    inputs.nth(2).fill(new)
    page.locator(".el-dialog button.el-button--primary").click()
    page.wait_for_timeout(1000)


def test_cabinets_flow(browser):
    """Кабинеты (№ 52) и стартовая страница «Поток» (№ 53): плитки по роли, клавиши, старые адреса, переключатель."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page)
    assert page.url.rstrip("/") == URL                                  # администратор — на «Поток»
    page.wait_for_selector(".flow .tile")
    assert page.locator("[data-cabinet]").count() == 5
    assert page.locator("[data-pipe]").count() == 2
    assert page.locator("[data-pipe] .plabel:visible").count() == 0           # стрелки: подписи — в подсказке
    assert page.locator("[data-test=credits]").count() == 1                 # строка разработчиков
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")  # «Главная» без прокрутки (24.10)
    page.keyboard.press("2")
    page.wait_for_url(URL + "/calc/calculations")
    assert page.locator(".cab-title").inner_text().strip() == "Расчёт запасов рыб"
    # переключатель кабинетов в шапке
    page.locator(".cab-switch button").click()
    page.locator(".el-dropdown-menu__item").filter(has_text="Моделирование").click()
    page.wait_for_url(URL + "/design/dictionaries")
    # логотип ведёт на «Главную»; слайд мониторинга помещается в экран без прокрутки (замечания 24.10)
    assert page.locator("[data-test=brand]").get_attribute("href") == "/"
    page.goto(URL + "/monitoring/waterbody/zhaysan")
    page.wait_for_selector(".slide .widget")
    page.wait_for_timeout(1500)
    assert page.evaluate("(() => { const m = document.querySelector('.main'); return m.scrollHeight <= m.clientHeight })()")
    # старые адреса единого интерфейса
    for old, new in (("/data?wb=zhaysan", "/input/datasets?wb=zhaysan"), ("/runs", "/calc/calculations"),
                     ("/monitoring/zhaysan?tab=pdu", "/monitoring/waterbody/zhaysan?tab=pdu"), ("/users", "/admin/users"),
                     ("/dictionaries", "/design/dictionaries"), ("/admin/catalog", "/calc/catalog"),
                     ("/calc/runs/01ABC", "/calc/calculations"), ("/profiles", "/calc/params")):
        page.goto(URL + old)
        page.wait_for_url(lambda u, n=new: u.startswith(URL + n), timeout=10000)
    # «Продолжить» ведёт на последний экран
    page.goto(URL + "/")
    page.wait_for_selector("[data-test=continue]")
    assert page.locator("[data-test=continue]").get_attribute("href").startswith("/calc/params")
    assert not errors, errors
    # ихтиолог: четыре кабинета, без администрирования
    p2 = browser.new_page(viewport={"width": 1440, "height": 900})
    name = _user("ichthyologist")
    login(p2, name, "user-pass-1")
    _change_password(p2, "user-pass-1", "user-pass-2")
    p2.wait_for_selector(".flow .tile")
    assert p2.locator("[data-cabinet]").count() == 4 and p2.locator("[data-cabinet=admin]").count() == 0
    p2.goto(URL + "/admin/users")
    p2.wait_for_url(URL + "/")


def test_operator(browser):
    """Оператор ввода данных (№ 54): сразу «Ввод данных», загрузка доступна, расчёты — нет, мониторинг — чтение."""
    name = _user("operator")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    login(page, name, "user-pass-1")
    _change_password(page, "user-pass-1", "user-pass-2")
    page.wait_for_url(lambda u: u.startswith(URL + "/input/datasets"))
    page.goto(URL + "/input/datasets?wb=zhaysan")
    page.wait_for_selector("text=Уловы по ловам")
    assert page.locator("text=Загрузить Excel").count() >= 1
    page.goto(URL + "/calc/calculations")
    page.wait_for_url(lambda u: u.startswith(URL + "/input/"))
    page.goto(URL + "/monitoring/waterbody/zhaysan")
    page.wait_for_selector(".slide .widget")
    assert page.locator(".slide-side textarea").count() == 0            # комментарии — только чтение


def test_viewer_and_language(browser):
    """Наблюдатель — сразу «Мониторинг» (№ 53), внутренние состояния скрыты (№ 55), другие кабинеты закрыты."""
    login_name = _user("viewer", "viewer-pass-1")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    login(page, login_name, "viewer-pass-1")
    _change_password(page, "viewer-pass-1", "viewer-pass-2")
    assert page.url.startswith(URL + "/monitoring/")
    page.wait_for_selector("text=Зайсан (Жайсан)")
    assert page.locator("text=данные новее расчёта").count() == 0
    assert page.locator(".cab-switch").count() == 0                    # один кабинет — переключателя нет
    for path in ("/input/datasets?wb=zhaysan", "/calc/calculations", "/admin/users", "/"):
        page.goto(URL + path)
        page.wait_for_url(lambda u: u.startswith(URL + "/monitoring/"), timeout=10000)
    assert page.locator("text=Пользователи").count() == 0
    page.get_by_text("ҚАЗ", exact=True).first.click()
    page.wait_for_selector("text=Су айдындарының картасы")


def _tabs(page):
    page.wait_for_selector(".slide .widget", timeout=20000)
    return [t.strip() for t in page.locator(".mon-tabs .el-tabs__item, .el-tabs__header .el-tabs__item").all_inner_texts()]


@pytest.mark.parametrize("role", ["viewer", "operator", "presenter"])
def test_roles_monitoring_limited(browser, role):
    """Наблюдатель, оператор, «Презентация» (№ 62): в мониторинге — «Исходные данные» и «ПДУ НПЦ»; прямой адрес
    скрытой вкладки не открывает её; на карте — ПДУ НПЦ."""
    name = _user(role)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page, name, "user-pass-1")
    _change_password(page, "user-pass-1", "user-pass-2")
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=pdu")
    tabs = _tabs(page)
    assert "Исходные данные" in tabs and "ПДУ" in tabs and "Уловистость" not in tabs and "Запасы" not in tabs, tabs
    assert page.locator("text=ПДУ, рассчитанный в приложении").count() == 0
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=stock&s=summary&w=st_trust")
    page.wait_for_timeout(2500)
    assert page.locator("text=Сходятся ли оценки запаса").count() == 0
    page.goto(URL + "/monitoring/")
    page.wait_for_selector("text=Зайсан (Жайсан)")
    page.get_by_text("Зайсан (Жайсан)").first.click()
    page.wait_for_timeout(1500)
    if page.locator("text=ПДУ НПЦ, т").count() == 0:
        assert page.locator("text=ПДУ, т").count() == 0                  # ПДУ приложения на карте не показывается
    assert not errors, errors


def test_presenter(browser):
    """«Презентация» (№ 62): «Поток», просмотр данных, расчётов и конструктора без правки; справка — обзор."""
    name = _user("presenter")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page, name, "user-pass-1")
    _change_password(page, "user-pass-1", "user-pass-2")
    assert page.url.rstrip("/") == URL                                  # стартовая — «Поток»
    page.wait_for_selector(".flow .tile")
    assert page.locator("[data-cabinet=admin]").count() == 0
    page.goto(URL + "/input/datasets?wb=zhaysan")
    page.wait_for_selector("text=Уловы по ловам")
    assert page.locator("text=Загрузить Excel").count() == 0
    page.goto(URL + "/calc/calculations?wb=zhaysan")
    page.wait_for_selector("[data-test=calcs-table] .el-table__row")
    assert page.locator("text=Параметры алгоритмов").count() == 0 and page.locator("[data-test=calc-new]").count() == 0
    page.locator("[data-test=calcs-table] .el-table__row").first.click()
    page.wait_for_selector("[data-test=calc-journal]")
    page.wait_for_timeout(1000)
    for txt in ("Таблицы", "Файлы", "Скачать", "Пересчитать", "Протокол выполнения"):
        assert page.get_by_text(txt, exact=True).count() == 0, txt
    page.goto(URL + "/calc/params")
    page.wait_for_url(lambda u: not u.startswith(URL + "/calc/params"))
    page.goto(URL + "/design/catalog")                                  # перенесён в «Расчёт запасов рыб» (№ 70)
    page.wait_for_url(URL + "/calc/catalog")
    page.wait_for_selector("text=Запас по математической модели")
    assert page.get_by_text("Код версии", exact=True).count() == 0 and page.locator("[data-test=run-bayes_cohort]").count() == 0
    page.goto(URL + "/design/algorithms")
    page.wait_for_url(lambda u: not u.startswith(URL + "/design/algorithms"))
    page.goto(URL + "/admin/users")
    page.wait_for_url(lambda u: not u.startswith(URL + "/admin/"))
    page.goto(URL + "/monitoring/help")
    page.wait_for_selector("text=О приложении FishStock")
    assert page.locator("text=Установка и сопровождение").count() == 0 and page.locator("text=Математику: алгоритмы").count() == 0
    page.goto(URL + "/monitoring/help/method-scheme")
    page.wait_for_selector("h1:has-text('Схема расчёта ПДУ'), h2:has-text('Схема расчёта ПДУ')")
    page.goto(URL + "/monitoring/waterbody/zhaysan")
    page.wait_for_selector(".slide .widget")
    assert page.locator(".slide-side textarea").count() == 0            # комментарии — нет
    assert not errors, errors


def test_monitoring_slides(browser):
    """Мониторинг: слайды по умолчанию, стрелки, режим вида, журнал ловов, комментарии, лента."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan")
    page.wait_for_selector(".slide .widget")
    assert page.locator(".dots .dot").count() >= 2
    page.wait_for_selector(".slide-side .now")                     # «Что видно сейчас»
    page.keyboard.press("ArrowRight")
    page.wait_for_function("location.search.includes('w=')")
    assert page.locator(".dot.on .dn").inner_text() == "2"
    # щелчок по строке светофора — «Все данные по виду»: вид выбран, открыт «Обзор» этого вида с первого слайда
    page.locator(".tt tbody tr").nth(1).click()
    page.wait_for_function("location.search.includes('sp=') && location.search.includes('s=overview')")
    page.wait_for_function("document.querySelector('.dot.on .dn')?.textContent === '1'")
    page.locator(".chips .chip").first.click()
    # режим вида: чип вида → заголовок с названием вида, адрес помнит вид
    page.locator(".chips .chip").nth(1).click()
    page.wait_for_function("location.search.includes('sp=')")
    page.locator(".chips .chip").first.click()
    # журнал ловов в разделе «Уловы»: русские заголовки, фильтр по году
    page.locator(".secs label").filter(has_text="Уловы").click()
    page.locator(".dots .dot").filter(has_text="Журнал ловов").click()
    page.wait_for_selector(".jr .el-table")
    heads = page.locator(".jr .el-table__header th").all_inner_texts()
    assert any("Дата" in h for h in heads) and not any("date" == h.strip() for h in heads)
    # комментарий: написать и увидеть счётчик
    text = "e2e " + uuid.uuid4().hex[:6]
    page.locator(".slide-side textarea").fill(text)
    page.locator(".slide-side button").filter(has_text="Отправить").click()
    page.wait_for_selector(f"text={text}")
    page.wait_for_selector(".dot.on .dc")
    page.locator(".slide-side .cm-i").filter(has_text=text).locator(".del").click()
    page.locator(".el-message-box button.el-button--primary").click()
    page.wait_for_timeout(800)
    assert page.locator(f"text={text}").count() == 0
    # лента
    page.locator(".secline .el-radio-button").filter(has_text="Лента").click()
    page.wait_for_selector(".grid12 > .widget")
    assert page.locator(".slide").count() == 0
    assert not errors, errors


def test_monitoring_catchability(browser):
    """Уловистость: невод и сеть слайдами, все виды → вид, год стрелками и щелчком по строке."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=catchability&s=seine")
    page.wait_for_selector(".slide .el-table__row")
    page.locator(".slide .el-table__row").first.click()          # вид → все данные по виду, «Параметры года»
    page.wait_for_function("location.search.includes('sp=') && location.search.includes('w=k_s_tiles')")
    page.wait_for_selector(".slide .tile")
    assert page.locator(".dots .dot").count() >= 6
    y0 = page.locator(".ystep .el-select").inner_text()
    page.locator(".ystep button").first.click()                  # предыдущий год
    page.wait_for_function(f"location.search.includes('y={int(y0) - 1}')")
    page.locator(".secs label").filter(has_text="Сеть").click()
    page.wait_for_selector(".slide .tile")
    assert not errors, errors


def test_monitoring_trust(browser):
    """Уловистость открывается на «Сводке»: 8 видов; строка → вид в «Неводе», ячейка «поколения» → «Запасы»."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=catchability")
    page.wait_for_selector(".tr.row")
    assert "s=summary" in page.url and page.locator(".tr.row").count() == 8
    assert "Проверки пройдены у" in page.locator(".tr-head").inner_text()
    page.locator(".tr.row .sp").first.click()
    page.wait_for_function("location.search.includes('sp=') && location.search.includes('s=seine')")
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=catchability")
    page.wait_for_selector(".tr.row")
    page.locator(".tr.row").first.locator(".cell").nth(2).click()
    page.wait_for_function("location.search.includes('tab=stock') && location.search.includes('w=st_ages')")
    assert not errors, errors


def test_monitoring_checks(browser):
    """Раздел «Проверки» вида: слайды открываются без ошибок; паспорт — щелчок по клетке открывает вид."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=catchability&s=checks&sp=lesh")
    page.wait_for_selector(".slide canvas")
    titles = []
    for _ in range(7):
        titles.append(page.locator(".slide .wt").first.inner_text())
        if page.locator(".nav.next").is_enabled():
            page.locator(".nav.next").click()
            page.wait_for_timeout(1200)
    assert any("Проверка поколений" in t for t in titles) and any("Кого не видит" in t for t in titles), titles
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=catchability&s=summary&w=k_passport")
    page.wait_for_selector(".slide canvas")
    assert "Паспорт" in page.locator(".slide").first.inner_text()
    assert not errors, errors


def test_monitoring_stock(browser):
    """Запас по уловам: виды за год → вид; уловистость всегда по возрастам — переключателя нет (№ 70)."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=stock&s=by_catch")
    page.wait_for_selector(".slide .el-table__row")
    page.locator(".slide .el-table__row").first.click()
    page.wait_for_function("location.search.includes('w=st_tiles')")
    page.wait_for_selector(".slide .tile")
    assert page.locator(".wctl .el-radio-button").filter(has_text="средняя по виду").count() == 0
    assert "по запасам" in page.locator(".slide").first.inner_text()
    page.locator(".nav.next").click()
    page.wait_for_selector(".slide canvas")
    assert not errors, errors



def test_monitoring_stock_summary(browser):
    """Запасы открываются на «Сводке»: с полным расчётом — строки видов (щелчок → вид в «Байесовской модели»),
    без него — понятное сообщение; «Запас в тоннах» работает и без модели."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=stock")
    page.wait_for_selector(".slide .tr.row, .slide :text('нет основного расчёта')")
    assert "s=summary" in page.url
    if page.locator(".slide .tr.row").count():
        page.locator(".slide .tr.row").first.click()
        page.wait_for_function("location.search.includes('s=bayes') && location.search.includes('sp=')")
    page.goto(URL + "/monitoring/waterbody/zhaysan?tab=stock&s=by_catch&sp=lesh&w=st_biomass")
    page.wait_for_selector(".slide canvas")
    assert not errors, errors


def test_users_edit_delete_profile(browser, tmp_path):
    """Пользователи и профиль (решение № 58): правка имени админом, удаление, свой профиль и фото."""
    import httpx
    api = httpx.Client(base_url=URL + "/api", timeout=30)
    tok = api.post("/users/auth/login", json={"login": "admin", "password": PWD}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    org = "e2e_" + uuid.uuid4().hex[:6]   # синтетическая организация для теста
    assert api.post("/data-model/entities/organizations/records", headers=H,
                    json={"values": {"code": org, "name_ru": "Тестовая организация " + org}}).status_code == 201
    name = _user("ichthyologist")
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page)
    page.goto(URL + "/admin/users")
    row = page.locator(".el-table__row", has_text=name).first
    row.wait_for()
    # кнопки действий видны без прокрутки (закреплённая колонка)
    btn = page.locator(".el-table__fixed-right, .el-table-fixed-column--right").locator("button", has_text="Изменить").first
    assert btn.is_visible()
    page.locator(".el-table__row", has_text=name).locator("button", has_text="Изменить").last.click()
    dlg = page.locator(".user-dlg")
    dlg.wait_for()
    assert dlg.locator("input").first.is_disabled()               # логин не меняется
    name_input = dlg.locator(".el-form-item", has_text="ФИО").locator("input")
    name_input.fill("Исправленное Имя")
    dlg.locator(".el-form-item", has_text="Должность").locator("input").fill("ведущий научный сотрудник")
    dlg.locator(".el-form-item", has_text="Организация").locator(".el-select").click()
    page.locator(".el-select-dropdown__item", has_text=org).click()
    dlg.locator("button", has_text="Сохранить").click()
    page.wait_for_selector("text=Исправленное Имя")
    page.wait_for_selector("text=ведущий научный сотрудник")
    # вход под пользователем: имя в шапке, свой профиль, фото
    p2 = browser.new_page(viewport={"width": 1280, "height": 800})
    p2.on("pageerror", lambda e: errors.append(str(e)))
    login(p2, name, "user-pass-1")
    _change_password(p2, "user-pass-1", "user-pass-2")
    p2.wait_for_selector(".uname >> text=Исправленное Имя")
    p2.locator(".user").first.click()
    p2.get_by_text("Мой профиль").click()
    pd = p2.locator(".profile-dlg")
    pd.wait_for()
    pd.locator(".el-form-item", has_text="Организация").get_by_text("Тестовая организация " + org).wait_for()
    pd.locator(".el-form-item", has_text="ФИО").locator("input").fill("Имя Из Профиля")
    # синтетическое изображение для теста (PNG, сгенерировано в браузере)
    png = p2.evaluate("""() => { const c = document.createElement('canvas'); c.width = 300; c.height = 200;
        const x = c.getContext('2d'); x.fillStyle = '#2a7'; x.fillRect(0, 0, 300, 200); return c.toDataURL('image/png') }""")
    import base64
    f = tmp_path / "photo.png"
    f.write_bytes(base64.b64decode(png.split(",", 1)[1]))
    pd.locator("input[type=file]").set_input_files(str(f))
    p2.wait_for_selector("text=Фото сохранено")
    pd.locator("button", has_text="Сохранить").click()
    p2.wait_for_selector(".uname >> text=Имя Из Профиля")
    p2.wait_for_selector(".user .el-avatar img")
    p2.reload()
    p2.wait_for_selector(".user .el-avatar img")
    p2.wait_for_selector(".uname >> text=Имя Из Профиля")
    # администратор удаляет пользователя через меню «⋯»
    page.reload()
    row = page.locator(".el-table__row", has_text="Имя Из Профиля").last
    row.wait_for()
    row.locator("button[aria-label='Ещё действия']").click()
    page.locator(".el-dropdown-menu__item:visible", has_text="Удалить").click()
    page.wait_for_selector("text=Удаление окончательное")
    page.locator(".el-message-box button.el-button--danger").click()
    page.wait_for_selector(f"text=Пользователь {name} удалён")
    page.locator(".el-table__row", has_text=name).first.wait_for(state="detached")
    assert api.post("/users/auth/login", json={"login": name, "password": "user-pass-2"}).status_code == 401
    assert not errors, errors



def test_calcs_catalog_params(browser):
    """Расчёт запасов рыб (решение № 70): расчёты a–h водоёма, каталог a–k (k — «Планируется»), запуск алгоритма из
    каталога с параметрами по умолчанию, альтернативный → основной, устаревшие и «Пересчитать устаревшие», набор
    параметров на основе «По умолчанию» с новой версией."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    login(page)
    page.goto(URL + "/calc/calculations?wb=zhaysan")
    page.wait_for_selector("[data-test=calcs-table] .el-table__row")
    assert page.locator("[data-test=calcs-table] .el-table__row").count() >= 8
    # каталог: 11 алгоритмов, k планируется
    page.goto(URL + "/calc/catalog")
    page.wait_for_selector("[data-test=algo-removal_pdu] [data-test=planned]")
    assert page.locator("[data-test^=algo-]").count() >= 11
    # запуск b из каталога: новый расчёт — альтернативный (основной уже есть)
    page.locator("[data-test=run-seine_catchability]").click()
    page.locator("[data-test=run-wb]").click()
    page.locator(".el-select-dropdown__item:visible", has_text="Зайсан (Жайсан)").first.click()
    page.locator("[data-test=run-go]").click()
    page.wait_for_url(lambda u: "/calc/calculations/" in u)
    page.wait_for_selector("[data-test=calc-set-main]", timeout=120000)
    page.locator("[data-test=calc-set-main]").click()
    page.wait_for_selector("[data-test=calc-main]")
    # расчёт c, взявший прежний основной b, устарел
    page.goto(URL + "/calc/calculations?wb=zhaysan&stale=1")
    page.wait_for_selector("[data-test=calcs-table] [data-test=stale]")
    page.locator("[data-test=recalc-stale]").click()
    import time
    t0 = time.time()
    while time.time() - t0 < 300:                                  # очередь: c → e → g → h по порядку
        page.goto(URL + "/calc/calculations?wb=zhaysan")
        page.wait_for_selector("[data-test=calcs-table] .el-table__row")
        busy = page.locator("[data-test=calcs-table] .el-tag", has_text="в очереди").count() + \
            page.locator("[data-test=calcs-table] .el-tag", has_text="выполняется").count()
        if not busy and page.locator("[data-test=calcs-table] [data-test=stale]").count() == 0:
            break
        page.wait_for_timeout(3000)
    assert page.locator("[data-test=calcs-table] [data-test=stale]").count() == 0
    # параметры: набор на основе «По умолчанию» для b, правка — новая версия
    page.goto(URL + "/calc/params?algorithm=seine_catchability")
    page.wait_for_selector("[data-test=set-base-on]")
    page.locator("[data-test=set-base-on]").click()
    name = "e2e " + uuid.uuid4().hex[:6]
    page.locator(".el-message-box input").fill(name)
    page.locator(".el-message-box button.el-button--primary").click()
    page.wait_for_selector("[data-test=set-save]")
    page.locator(".prow", has_text="SEINE_MIN_SAMPLE").locator("input").fill("25")
    page.locator("[data-test=set-save]").click()
    page.wait_for_selector("text=Сохранена новая версия набора")
    assert "v2" in page.locator(".list .item.sel").inner_text()
    assert not errors, errors
