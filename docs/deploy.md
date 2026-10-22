# Установка, внешний доступ, резервное копирование

> **Рабочая установка с 23.10.2026 — сервер https://fishstock.89-218-32-75.sslip.io** (решение № 49): установлена
> скриптами `deploy/server/` (справка «Доступ для коллег через интернет»), обновляется по команде
> `~/fishstock/deploy/server/update.sh`. Правила для разработки — `CLAUDE.md`.

## Сервер

Linux (Ubuntu 22.04+), Docker 24+ с Compose. Ресурсы: 4 ядра / 8 ГБ — минимум; 8 ядер / 16 ГБ — рекомендуется
(байесовская модель одного вида — 15 мин – 2 ч; число одновременных расчётов — `FISH_WORKERS`). Диск — 20 ГБ+.
Доступ в интернет нужен для подложки карты (OpenStreetMap) и выпуска HTTPS-сертификата.

```bash
git clone https://github.com/ALB040570/FISH_stock.git /opt/fishstock && cd /opt/fishstock
cp .env.example .env && nano .env        # FISH_JWT_SECRET, FISH_SERVICE_TOKEN, FISH_ADMIN_PASSWORD, FISH_WORKERS
docker compose up -d --build
docker compose ps                        # все сервисы healthy
python3 tools/seed_samples.py --password <пароль admin>
```

Обновление: `git pull && docker compose up -d --build` — данные в томе `fishdata` сохраняются; системные шаблоны
дашбордов обновляются, если их не меняли пользователи.

## Внешний доступ коллегам (HTTPS)

1. DNS-запись A домена (например, `fish.example.kz`) → IP сервера; открыть порты 80 и 443.
2. В `.env`: `FISH_DOMAIN=fish.example.kz`.
3. `docker compose -f docker-compose.yml -f docker-compose.public.yml up -d --build` — Caddy выпустит сертификат.
4. Коллегам для просмотра — учётные записи с ролью **«Наблюдатель»**.

Временно, без сервера: на компьютере с запущенным приложением `cloudflared tunnel --url http://localhost:8080`
даёт адрес вида `https://….trycloudflare.com` (работает, пока компьютер включён).

## Резервное копирование и восстановление

```bash
./deploy/backup.sh                                   # архив тома в ./backups, хранятся последние 30
./deploy/restore.sh backups/fishstock_20261024_030000.tar.gz
```

Ежедневно по cron: `0 3 * * * cd /opt/fishstock && ./deploy/backup.sh >> backups/backup.log 2>&1`.
Архив содержит контрольные суммы всех файлов (`python3 tools/backup.py verify <архив>`); восстановление сохраняет
предыдущее состояние тома в `/data/.before_restore`. Храните копии вне сервера. Без Docker:
`python tools/backup.py create --data ./data --out ./backups` и `restore … --force`.

## Безопасность

- Секреты только в `.env` (в Git не попадает). Пароли — argon2; токены — JWT (60 мин) и обновление (14 дней);
  блокировка, смена роли и смена пароля аннулируют токены обновления.
- Код алгоритмов выполняется в отдельных процессах воркеров; публиковать алгоритмы могут только математик и администратор.
- Маршруты `/internal/*` недоступны снаружи.
