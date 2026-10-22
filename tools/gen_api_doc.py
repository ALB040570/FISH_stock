"""Генерация docs/api.md по маршрутам сервисов:  python tools/gen_api_doc.py > docs/api.md"""
import contextlib
import importlib
import io
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "libs" / "fishcommon"))
os.environ["FISH_DATA_DIR"] = tempfile.mkdtemp()
os.environ["FISH_URL_USERS"] = "http://127.0.0.1:9"

D = {
    "health": "Состояние сервиса", "login": "Вход: логин и пароль → токены", "refresh": "Обновление токена доступа",
    "me": "Текущий пользователь", "change_password": "Смена своего пароля", "roles": "Список ролей",
    "list_users": "Пользователи", "create_user": "Создать пользователя", "update_user": "Изменить имя, e-mail, роль",
    "block_user": "Заблокировать", "unblock_user": "Разблокировать", "reset_password": "Сбросить пароль",
    "delete_user": "Удалить (логически)", "directory": "Имена пользователей для подписей", "audit_list": "Журнал действий (фильтры, страницы)",
    "audit_export": "Выгрузка журнала в Excel",
    "list_datasets": "Наборы данных (фильтр по водоёму и типу)", "create_dataset": "Создать набор (водоём × тип)",
    "get_dataset": "Набор данных", "delete_dataset": "Удалить набор (логически)", "versions": "Версии",
    "get_data": "Таблица версии набора", "template": "Excel-шаблон типа набора (виды водоёма)",
    "export": "Выгрузка версии в Excel", "source_file": "Исходный загруженный файл версии",
    "upload": "Загрузка Excel (merge/replace, dry_run — только проверка)",
    "upload_new": "Загрузка Excel с созданием набора, если его нет", "edit": "Правка в браузере → новая версия",
    "restore": "Восстановить версию как новую", "diff": "Сравнение двух версий", "water_body_status": "Сводка данных по водоёмам",
    "bundle": "Текущие версии наборов водоёма",
    "catalog": "Каталог алгоритмов и версий", "catalog_item": "Алгоритм и его версии", "package": "Пакет версии (zip)",
    "package_files": "Файлы пакета версии / текст файла", "enable": "Включить версию", "disable": "Отключить версию",
    "list_profiles": "Профили водоёмов", "get_profile": "Профиль водоёма (значения, схема, версии)",
    "profile_version": "Значения версии профиля", "save_profile": "Сохранить профиль → новая версия",
    "copy_profile": "Скопировать профиль из другого водоёма", "list_calcs": "Расчёты", "create_calc": "Создать расчёт",
    "get_calc": "Расчёт и его версии", "update_calc": "Изменить расчёт → новая версия", "delete_calc": "Удалить расчёт",
    "from_template": "Создать расчёт из шаблона (full / stock)", "check_calc": "Проверка готовности и план запуска",
    "start_run": "Поставить запуск в очередь (в т. ч. с шага по базовому запуску)", "list_runs": "Запуски (история)",
    "get_run": "Запуск: шаги, ход выполнения, место в очереди", "step_result": "Результат шага (таблицы, показатели, файлы)",
    "step_log": "Журнал шага", "step_file": "Файл результата шага", "cancel": "Отменить запуск",
    "set_main": "Отметить основным запуском водоёма", "export_zip": "Все результаты запуска (zip)",
    "report": "Отчёт по запуску: report.docx / report.pdf", "queue": "Очередь и выполняющиеся запуски",
    "wb_status": "Сводка расчётов по водоёмам (для карты)", "monitoring_run": "Запуск для мониторинга водоёма",
    "list_boards": "Дашборды (шаблоны, свои, общие)", "get_board": "Дашборд", "create_board": "Создать дашборд",
    "update_board": "Изменить дашборд → новая версия", "copy_board": "Копия дашборда/шаблона", "delete_board": "Удалить дашборд",
    "widget_data": "Данные виджета (источник, фильтры, агрегирование)",
    "field_types": "Типы полей", "list_entities": "Справочники", "get_entity": "Справочник (поля)",
    "create_entity": "Создать справочник", "update_entity": "Изменить поля → новая версия", "delete_entity": "Удалить справочник",
    "entity_versions": "Версии справочника", "entity_version": "Описание версии справочника", "list_records": "Записи справочника",
    "lookup": "Соответствие названий и кодов", "create_record": "Создать запись", "get_record": "Запись",
    "update_record": "Изменить запись → новая версия", "delete_record": "Удалить запись", "record_versions": "История записи",
    "water_bodies_geojson": "Водоёмы (GeoJSON для карты)", "kazakhstan": "Граница Казахстана (GeoJSON)",
    "parse_geo": "Разбор контура из GeoJSON/KML", "list_dtypes": "Типы наборов данных", "get_dtype": "Тип набора (версия)",
    "create_dtype": "Создать тип набора", "update_dtype": "Изменить тип → новая версия", "dtype_versions": "Версии типа",
    "list_projects": "Алгоритмы (проекты)", "create_project": "Новый алгоритм (черновик из шаблона)",
    "get_project": "Алгоритм: черновики, опубликованные версии", "create_draft": "Черновик от опубликованной версии",
    "get_draft": "Черновик: файлы, манифест, история, тесты", "get_file": "Текст файла черновика",
    "put_file": "Сохранить файл → новая ревизия", "delete_file": "Удалить файл", "download": "Черновик (zip)",
    "delete_draft": "Удалить черновик", "validate": "Проверка: манифест, параметры, синтаксис, точка входа",
    "start_test": "Тестовый прогон (с предшественниками, сверка с версией)", "get_test": "Состояние и журнал теста",
    "get_test_result": "Результат теста", "publish": "Публикация проверенной версии в каталог",
    "get_sections": "Оглавление справки: разделы и статьи", "get_article": "Статья (expand=1 — с таблицами параметров и примером)",
    "get_versions": "Версии статьи", "search": "Поиск по справке", "context": "Статья для экрана приложения",
    "example": "Варианты примера на числах (виды, годы)", "bundled_image": "Рисунок поставки",
    "save_article": "Сохранить статью → новая версия", "restore": "Восстановить версию статьи",
    "take_bundled": "Взять текст поставки", "create_article": "Новая статья", "delete_article": "Удалить статью",
    "upload_image": "Загрузить рисунок", "get_image": "Рисунок статьи", "export_docx": "Руководство / раздел / статья в Word",
    "export_pdf": "Руководство / раздел / статья в PDF", "export_md": "Руководство / раздел в Markdown",
}
NAMES = {"users": "1. Администрирование пользователей", "data_admin": "2. Администрирование входных данных",
         "algo_admin": "3. Администрирование алгоритмов расчёта", "dashboards": "4. Администрирование дашбордов",
         "data_model": "5. Моделирование данных (справочник)", "algo_model": "6. Моделирование алгоритмов расчёта",
         "help": "7. Справка"}

out = ["# API сервисов FishStock", "",
       "Сервисы доступны через шлюз: `/api/<сервис>/<путь>`, сервис — users, data-model, data-admin, algo-model, algo-admin, dashboards, help.",
       "Авторизация — `Authorization: Bearer <access_token>` (`POST /api/users/auth/login`). Ошибки — `{\"error\": {\"code\", \"message\", \"details\"}}`.",
       "Интерактивная документация (Swagger) каждого сервиса — `http://<сервис>:8000/docs` внутри сети Docker или `http://127.0.0.1:800N/docs` при запуске без Docker.",
       "Маршруты `/internal/*` — только для вызовов между сервисами (`X-Service-Token`), шлюз их не пропускает.", ""]
for svc in NAMES:
    for m in [m for m in sys.modules if m == "app" or m.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, str(REPO / "services" / svc))
    with contextlib.redirect_stdout(io.StringIO()):
        mod = importlib.import_module("app.main")
    sys.path.pop(0)
    out += [f"## {NAMES[svc]} — `/api/{svc.replace('_', '-')}`", "", "| Метод | Путь | Назначение |", "|---|---|---|"]
    for r in mod.app.routes:
        if not hasattr(r, "methods") or r.path.startswith(("/openapi", "/docs", "/redoc")) or "/internal/" in r.path:
            continue
        out.append(f"| {', '.join(sorted(r.methods - {'HEAD'}))} | `{r.path}` | {D.get(r.name, r.name)} |")
    out.append("")
print("\n".join(out))
