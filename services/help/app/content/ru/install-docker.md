# Установка с Docker

1. Установите Docker и Docker Compose (на macOS и Windows — Docker Desktop).
2. Скачайте приложение:

   ```bash
   git clone -b develop https://github.com/ALB040570/FISH_stocke.git
   cd FISH_stocke
   ```

3. Создайте файл настроек:

   ```bash
   cp .env.example .env
   python3 -c "import secrets;print(secrets.token_urlsafe(48))"   # выполните дважды
   ```

   Откройте `.env` в текстовом редакторе и задайте:

   | Переменная | Значение |
   |---|---|
   | `FISH_JWT_SECRET` | первая случайная строка (секрет подписи токенов входа) |
   | `FISH_SERVICE_TOKEN` | вторая случайная строка (токен вызовов между сервисами) |
   | `FISH_ADMIN_PASSWORD` | пароль первого администратора (логин `admin`) |
   | `FISH_WORKERS` | число одновременных расчётов (по умолчанию 2) |
   | `FISH_HTTP_PORT` | порт приложения (по умолчанию 8080) |

   Файл `.env` содержит секреты: не пересылайте его и не добавляйте в Git.

4. Соберите и запустите:

   ```bash
   docker compose up -d --build      # первая сборка — 10–20 минут
   docker compose ps                 # все сервисы должны быть в состоянии running / healthy
   ```

5. Откройте `http://<адрес сервера>:8080` и войдите: `admin` и пароль из `FISH_ADMIN_PASSWORD`.

Данные хранятся в томе Docker `fishdata` и сохраняются при перезапуске и обновлении.

Остановить: `docker compose down` (данные сохраняются). Журналы сервиса: `docker compose logs -f algo_admin`.

Дальше — [Первый запуск и загрузка данных](help:first-start).
