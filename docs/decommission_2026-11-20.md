# Вывод FishStock с сервера 89.218.32.75 (20.11.2026)

Решение № 78. По поручению заказчика FishStock и все его данные удалены с общего сервера организации
`89.218.32.75`; адрес https://fishstock.89-218-32-75.sslip.io больше не работает. Коллеги предупреждены заказчиком.
Другие приложения сервера (сайты aisilknet.kz в системном nginx, Docker-проект nir-analytics, задания cron
patent_system / mio_system / trends_app) не затрагивались.

## Где теперь данные

Архив — **только на Mac заказчика** (в Git его нет: в нём учётные записи коллег и секреты `.env`):

`~/Documents/2026/Рыба/FishStock_архив_сервера/fishstock_archive_20261120.tar` (111 МБ,
SHA-256 `17414fa3765e6eba4925da47e246b2606dbd1a5307d3d1a8132eb38a8c629fc2`)

| Файл внутри | Что это |
|---|---|
| `fishstock_20261120_042718.tar.gz` | резервная копия тома `fishstock_fishdata` (`deploy/backup.sh`): 6100 файлов — наборы данных 4 водоёмов, пользователи, комментарии коллег, параметры, расчёты и результаты, дашборды, справка. Снята после остановки шлюза и воркера; проверена (`backup.py verify` — «архив цел», число файлов совпало с томом). Не вошли только кэши (`.pytensor`, `__pycache__`, `*.lock`, `*.tmp`) |
| `.env` | настройки и секреты установки (ключ подписи токенов, пароль администратора и т. п.) — **не публиковать** |
| `backup.log` | журнал ежедневных копий |
| `fishstock_inventory.txt` | опись сервера перед удалением (контейнеры, образы, cron, nginx, сертификаты, соседи) |
| `nginx_fishstock.conf` | бывший `/etc/nginx/sites-available/fishstock` (с правками certbot) |
| `crontab_fishstock.txt` | бывшая строка cron ежедневной копии |
| `git_commit.txt` | версия кода на сервере: `41480f2` (develop) |
| `backup.py` | проверка и распаковка архива без репозитория |
| `SHA256SUMS` | контрольные суммы файлов |

Проверка на Mac: `tar -xf fishstock_archive_20261120.tar && cd fishstock_archive_20261120 && shasum -a 256 -c SHA256SUMS
&& python3 backup.py verify fishstock_20261120_042718.tar.gz`.

## Что удалено с сервера

1. Контейнеры (9), сеть `fishstock_default` и образы `fishstock-*` (9 образов, ~6,3 ГБ) —
   `docker compose down --rmi local` в `~/fishstock` и удаление по именам; общие команды `docker system/image/builder prune`
   не применялись (кэш сборки Docker общий для всех проектов сервера и оставлен).
2. Том `fishstock_fishdata` (1,6 ГБ).
3. Строка `crontab` с пометкой `# fishstock-backup` (остальные задания пользователя не менялись).
4. `/etc/nginx/sites-enabled/fishstock` и `/etc/nginx/sites-available/fishstock`; перед `systemctl reload nginx` — `nginx -t`.
5. Сертификат Let's Encrypt `fishstock.89-218-32-75.sslip.io` (`certbot delete --cert-name …`).
6. Папка `~/fishstock` (код, `.env`, `backups/`) и временные файлы архива.

## Как развернуть заново (на любом сервере с Docker)

1. `git clone https://github.com/ALB040570/FISH_stock.git ~/fishstock && cd ~/fishstock && git checkout main`
   (версия сервера — коммит `41480f2`; main содержит её).
2. Положить `.env` из архива в `~/fishstock/.env` (иначе `install.sh` создаст новый — со старыми данными тогда
   перестанут действовать выданные токены, пароли пользователей сохранятся в данных).
3. `./deploy/server/install.sh` — сборка и запуск.
4. `./deploy/restore.sh <путь>/fishstock_20261120_042718.tar.gz` — данные, пользователи, комментарии.
5. Адрес снаружи — `./deploy/server/nginx_site.sh <домен>` (справка «Доступ для коллег через интернет»).

Локально на Mac без сервера — `run_local.sh` (данные разработки); архивные данные можно развернуть в Docker Desktop
теми же шагами 1–4.

## Проверка после очистки (20.11.2026, 04:38 UTC)

Следов FishStock нет (контейнеры, образы, тома, сети, cron, nginx, сертификаты, домашняя папка). Соседи — как в
описи до очистки: nir-analytics 3 контейнера (`:8080` → 200), aisilknet.kz → 200, files → 302, nir → 200, ntz → 302,
trends → 200; cron — 7 заданий других систем; `nginx -t` успешна. Диск: свободно 17 ГБ (было 12).
Кэш сборки Docker (общий для всех проектов сервера) не очищался.
