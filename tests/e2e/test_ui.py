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
    page.wait_for_selector("text=Зайсан (Жайсан)")
    page.goto(URL + "/monitoring/zhaysan")
    for tab in ("Уловистость", "Запасы", "ПДУ"):
        page.get_by_text(tab, exact=True).first.click()
        page.wait_for_timeout(1500)
    page.goto(URL + "/data?wb=zhaysan")
    page.wait_for_selector("text=Уловы по ловам")
    for path in ("/dictionaries", "/calculations?wb=zhaysan", "/runs", "/catalog", "/profiles", "/algorithms",
                 "/dashboards", "/users", "/audit"):
        page.goto(URL + path)
        page.wait_for_timeout(1200)
    assert not errors, errors


def test_viewer_and_language(browser):
    import httpx
    api = httpx.Client(base_url=URL + "/api", timeout=30)
    tok = api.post("/users/auth/login", json={"login": "admin", "password": PWD}).json()["access_token"]
    login_name = "viewer_" + uuid.uuid4().hex[:6]
    r = api.post("/users/users", headers={"Authorization": f"Bearer {tok}"},
                 json={"login": login_name, "name": "Коллега", "role": "viewer", "password": "viewer-pass-1"})
    assert r.status_code == 201
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    login(page, login_name, "viewer-pass-1")
    # первый вход — обязательная смена пароля
    page.wait_for_selector("text=Смените пароль")
    inputs = page.locator(".el-dialog input[type=password]")
    inputs.nth(0).fill("viewer-pass-1")
    inputs.nth(1).fill("viewer-pass-2")
    inputs.nth(2).fill("viewer-pass-2")
    page.locator(".el-dialog button.el-button--primary").click()
    page.wait_for_timeout(1000)
    page.goto(URL + "/data?wb=zhaysan")
    page.wait_for_selector("text=Уловы по ловам")
    assert page.locator("text=Загрузить Excel").count() == 0       # наблюдатель не загружает
    assert page.locator("text=Пользователи").count() == 0
    page.get_by_text("ҚАЗ", exact=True).first.click()
    page.wait_for_selector("text=Бастапқы деректер")


def test_monitoring_slides(browser):
    """Мониторинг: слайды по умолчанию, стрелки, режим вида, журнал ловов, комментарии, лента."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/zhaysan")
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
    page.goto(URL + "/monitoring/zhaysan?tab=catchability&s=seine")
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
    page.goto(URL + "/monitoring/zhaysan?tab=catchability")
    page.wait_for_selector(".tr.row")
    assert "s=summary" in page.url and page.locator(".tr.row").count() == 8
    assert "Проверки пройдены у" in page.locator(".tr-head").inner_text()
    page.locator(".tr.row .sp").first.click()
    page.wait_for_function("location.search.includes('sp=') && location.search.includes('s=seine')")
    page.goto(URL + "/monitoring/zhaysan?tab=catchability")
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
    page.goto(URL + "/monitoring/zhaysan?tab=catchability&s=checks&sp=lesh")
    page.wait_for_selector(".slide canvas")
    titles = []
    for _ in range(7):
        titles.append(page.locator(".slide .wt").first.inner_text())
        if page.locator(".nav.next").is_enabled():
            page.locator(".nav.next").click()
            page.wait_for_timeout(1200)
    assert any("Проверка поколений" in t for t in titles) and any("Кого не видит" in t for t in titles), titles
    page.goto(URL + "/monitoring/zhaysan?tab=catchability&s=summary&w=k_passport")
    page.wait_for_selector(".slide canvas")
    assert "Паспорт" in page.locator(".slide").first.inner_text()
    assert not errors, errors


def test_monitoring_stock(browser):
    """Запас по уловам: виды за год → вид, переключатели расчёта общие для слайдов."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("try{localStorage.removeItem('fishstock.monitoring.view')}catch(e){}")
    login(page)
    page.goto(URL + "/monitoring/zhaysan?tab=stock&s=by_catch")
    page.wait_for_selector(".slide .el-table__row")
    page.locator(".slide .el-table__row").first.click()
    page.wait_for_function("location.search.includes('w=st_tiles')")
    page.wait_for_selector(".slide .tile")
    page.locator(".wctl .el-radio-button").filter(has_text="средняя по виду").click()
    page.wait_for_selector(".wctl .el-radio-button.is-active:has-text('средняя по виду')")
    page.locator(".nav.next").click()
    page.wait_for_selector(".slide canvas")
    assert page.locator(".wctl .el-radio-button.is-active").filter(has_text="средняя по виду").count() == 1
    assert not errors, errors

