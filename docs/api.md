# API сервисов FishStocke

Сервисы доступны через шлюз: `/api/<сервис>/<путь>`, сервис — users, data-model, data-admin, algo-model, algo-admin, dashboards.
Авторизация — `Authorization: Bearer <access_token>` (`POST /api/users/auth/login`). Ошибки — `{"error": {"code", "message", "details"}}`.
Интерактивная документация (Swagger) каждого сервиса — `http://<сервис>:8000/docs` внутри сети Docker или `http://127.0.0.1:800N/docs` при запуске без Docker.
Маршруты `/internal/*` — только для вызовов между сервисами (`X-Service-Token`), шлюз их не пропускает.

## 1. Администрирование пользователей — `/api/users`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| POST | `/auth/login` | Вход: логин и пароль → токены |
| POST | `/auth/refresh` | Обновление токена доступа |
| GET | `/auth/me` | Текущий пользователь |
| POST | `/auth/password` | Смена своего пароля |
| GET | `/roles` | Список ролей |
| GET | `/users` | Пользователи |
| POST | `/users` | Создать пользователя |
| PATCH | `/users/{uid}` | Изменить имя, e-mail, роль |
| POST | `/users/{uid}/block` | Заблокировать |
| POST | `/users/{uid}/unblock` | Разблокировать |
| POST | `/users/{uid}/reset-password` | Сбросить пароль |
| DELETE | `/users/{uid}` | Удалить (логически) |
| GET | `/users/directory` | Имена пользователей для подписей |
| GET | `/audit` | Журнал действий (фильтры, страницы) |
| GET | `/audit/export.xlsx` | Выгрузка журнала в Excel |

## 2. Администрирование входных данных — `/api/data-admin`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| GET | `/datasets` | Наборы данных (фильтр по водоёму и типу) |
| POST | `/datasets` | Создать набор (водоём × тип) |
| GET | `/datasets/{ds_id}` | Набор данных |
| DELETE | `/datasets/{ds_id}` | Удалить набор (логически) |
| GET | `/datasets/{ds_id}/versions` | Версии |
| GET | `/datasets/{ds_id}/data` | Таблица версии набора |
| GET | `/templates/{dataset_type}.xlsx` | Excel-шаблон типа набора (виды водоёма) |
| GET | `/datasets/{ds_id}/export.xlsx` | Выгрузка версии в Excel |
| GET | `/datasets/{ds_id}/versions/{n}/source` | Исходный загруженный файл версии |
| POST | `/datasets/{ds_id}/upload` | Загрузка Excel (merge/replace, dry_run — только проверка) |
| POST | `/upload` | Загрузка Excel с созданием набора, если его нет |
| PUT | `/datasets/{ds_id}/data` | Правка в браузере → новая версия |
| POST | `/datasets/{ds_id}/restore/{n}` | Восстановить версию как новую |
| GET | `/datasets/{ds_id}/diff` | Сравнение двух версий |
| GET | `/water-bodies/status` | Сводка данных по водоёмам |
| GET | `/bundle/{water_body}` | Текущие версии наборов водоёма |

## 3. Администрирование алгоритмов расчёта — `/api/algo-admin`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| GET | `/catalog` | Каталог алгоритмов и версий |
| GET | `/catalog/{code}` | Алгоритм и его версии |
| GET | `/catalog/{code}/versions/{version}/package.zip` | Пакет версии (zip) |
| GET | `/catalog/{code}/versions/{version}/files` | Файлы пакета версии / текст файла |
| POST | `/catalog/{code}/versions/{version}/enable` | Включить версию |
| POST | `/catalog/{code}/versions/{version}/disable` | Отключить версию |
| GET | `/profiles` | Профили водоёмов |
| GET | `/profiles/{code}/{water_body}` | Профиль водоёма (значения, схема, версии) |
| GET | `/profiles/{code}/{water_body}/versions/{n}` | Значения версии профиля |
| PUT | `/profiles/{code}/{water_body}` | Сохранить профиль → новая версия |
| POST | `/profiles/{code}/{water_body}/copy-from/{source}` | Скопировать профиль из другого водоёма |
| GET | `/calculations` | Расчёты |
| POST | `/calculations` | Создать расчёт |
| GET | `/calculations/{cid}` | Расчёт и его версии |
| PUT | `/calculations/{cid}` | Изменить расчёт → новая версия |
| DELETE | `/calculations/{cid}` | Удалить расчёт |
| POST | `/calculations/from-template` | Создать расчёт из шаблона (full / stock) |
| POST | `/calculations/{cid}/check` | Проверка готовности и план запуска |
| POST | `/calculations/{cid}/run` | Поставить запуск в очередь (в т. ч. с шага по базовому запуску) |
| GET | `/runs` | Запуски (история) |
| GET | `/runs/{rid}` | Запуск: шаги, ход выполнения, место в очереди |
| GET | `/runs/{rid}/steps/{i}/result` | Результат шага (таблицы, показатели, файлы) |
| GET | `/runs/{rid}/steps/{i}/log` | Журнал шага |
| GET | `/runs/{rid}/steps/{i}/files/{name}` | Файл результата шага |
| POST | `/runs/{rid}/cancel` | Отменить запуск |
| POST | `/runs/{rid}/main` | Отметить основным запуском водоёма |
| GET | `/runs/{rid}/export.zip` | Все результаты запуска (zip) |
| GET | `/runs/{rid}/report.{fmt}` | Отчёт по запуску: report.docx / report.pdf |
| GET | `/queue` | Очередь и выполняющиеся запуски |
| GET | `/water-bodies/status` | Сводка расчётов по водоёмам (для карты) |
| GET | `/water-bodies/{water_body}/monitoring-run` | Запуск для мониторинга водоёма |

## 4. Администрирование дашбордов — `/api/dashboards`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| GET | `/dashboards` | Дашборды (шаблоны, свои, общие) |
| GET | `/dashboards/{did}` | Дашборд |
| POST | `/dashboards` | Создать дашборд |
| PUT | `/dashboards/{did}` | Изменить дашборд → новая версия |
| POST | `/dashboards/{did}/copy` | Копия дашборда/шаблона |
| DELETE | `/dashboards/{did}` | Удалить дашборд |
| GET | `/dashboards/{did}/versions` | Версии |
| POST | `/widgets/data` | Данные виджета (источник, фильтры, агрегирование) |

## 5. Моделирование данных (справочник) — `/api/data-model`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| GET | `/field-types` | Типы полей |
| GET | `/entities` | Справочники |
| GET | `/entities/{code}` | Справочник (поля) |
| POST | `/entities` | Создать справочник |
| PUT | `/entities/{code}` | Изменить поля → новая версия |
| DELETE | `/entities/{code}` | Удалить справочник |
| GET | `/entities/{code}/versions` | Версии справочника |
| GET | `/entities/{code}/versions/{n}` | Описание версии справочника |
| GET | `/entities/{code}/records` | Записи справочника |
| GET | `/entities/{code}/lookup` | Соответствие названий и кодов |
| POST | `/entities/{code}/records` | Создать запись |
| GET | `/entities/{code}/records/{rid}` | Запись |
| PUT | `/entities/{code}/records/{rid}` | Изменить запись → новая версия |
| DELETE | `/entities/{code}/records/{rid}` | Удалить запись |
| GET | `/entities/{code}/records/{rid}/versions` | История записи |
| GET | `/water-bodies.geojson` | Водоёмы (GeoJSON для карты) |
| GET | `/kazakhstan.geojson` | Граница Казахстана (GeoJSON) |
| POST | `/geo/parse` | Разбор контура из GeoJSON/KML |
| GET | `/dataset-types` | Типы наборов данных |
| GET | `/dataset-types/{code}` | Тип набора (версия) |
| POST | `/dataset-types` | Создать тип набора |
| PUT | `/dataset-types/{code}` | Изменить тип → новая версия |
| GET | `/dataset-types/{code}/versions` | Версии типа |

## 6. Моделирование алгоритмов расчёта — `/api/algo-model`

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Состояние сервиса |
| GET | `/algorithms` | Алгоритмы (проекты) |
| POST | `/algorithms` | Новый алгоритм (черновик из шаблона) |
| GET | `/algorithms/{code}` | Алгоритм: черновики, опубликованные версии |
| POST | `/algorithms/{code}/drafts` | Черновик от опубликованной версии |
| GET | `/drafts/{did}` | Черновик: файлы, манифест, история, тесты |
| GET | `/drafts/{did}/file` | Текст файла черновика |
| PUT | `/drafts/{did}/file` | Сохранить файл → новая ревизия |
| DELETE | `/drafts/{did}/file` | Удалить файл |
| POST | `/drafts/{did}/upload` | Загрузка Excel (merge/replace, dry_run — только проверка) |
| GET | `/drafts/{did}/download.zip` | Черновик (zip) |
| DELETE | `/drafts/{did}` | Удалить черновик |
| POST | `/drafts/{did}/validate` | Проверка: манифест, параметры, синтаксис, точка входа |
| POST | `/drafts/{did}/test` | Тестовый прогон (с предшественниками, сверка с версией) |
| GET | `/tests/{tid}` | Состояние и журнал теста |
| GET | `/tests/{tid}/result` | Результат теста |
| POST | `/drafts/{did}/publish` | Публикация проверенной версии в каталог |

