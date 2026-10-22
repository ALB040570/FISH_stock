#!/usr/bin/env bash
# Установка FishStock на общий Linux-сервер рядом с другими сайтами (без sudo).
#
#   git clone -b develop https://github.com/ALB040570/FISH_stock.git ~/fishstock
#   ~/fishstock/deploy/server/install.sh
#
# Что делает:
#   - создаёт .env с секретами и паролем администратора (только на сервере, в Git не попадает);
#   - собирает и запускает контейнеры; приложение слушает только 127.0.0.1:<порт> (по умолчанию 8095),
#     снаружи его открывает системный nginx — см. deploy/server/nginx_site.sh;
#   - загружает образцы данных из samples/ и запускает быстрый расчёт запаса;
#   - добавляет в crontab ежедневную резервную копию (хранятся последние 7).
# Повторный запуск безопасен: существующий .env, данные и задания cron не меняются.
#
# Параметры (переменные окружения): FISH_PORT=8095  FISH_WORKERS=4  FISH_SEED=stock|full|none
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"
PORT="${FISH_PORT:-8095}"
WORKERS="${FISH_WORKERS:-4}"
SEED="${FISH_SEED:-stock}"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nОШИБКА: %s\n' "$*" >&2; exit 1; }

say "Проверка"
command -v docker >/dev/null || die "не найден Docker"
docker compose version >/dev/null 2>&1 || die "не найден Docker Compose (docker compose)"
docker info >/dev/null 2>&1 || die "нет доступа к Docker: пользователь должен быть в группе docker"
command -v git >/dev/null || die "не найден git"
command -v curl >/dev/null || die "не найден curl"

if [ ! -f .env ]; then
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${PORT}\$"; then
    die "порт ${PORT} занят; задайте другой: FISH_PORT=8096 $0"
  fi
  say "Создаю .env (секреты — только на этом сервере)"
  rnd() { head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
  umask 077
  cat > .env <<EOF
# FishStock на сервере. Создано deploy/server/install.sh $(date '+%Y-%m-%d %H:%M'). Не добавлять в Git.
COMPOSE_PROJECT_NAME=fishstock
FISH_JWT_SECRET=$(rnd 64)
FISH_SERVICE_TOKEN=$(rnd 64)
FISH_ADMIN_LOGIN=admin
FISH_ADMIN_PASSWORD=$(rnd 16)
FISH_WORKERS=${WORKERS}
# только внутри сервера: снаружи — через системный nginx
FISH_HTTP_PORT=127.0.0.1:${PORT}
EOF
  umask 022
  FIRST=1
else
  say "Файл .env уже есть — оставляю как есть"
  FIRST=0
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a
case "$FISH_HTTP_PORT" in *:*) LOCAL_URL="http://${FISH_HTTP_PORT}" ;; *) LOCAL_URL="http://127.0.0.1:${FISH_HTTP_PORT}" ;; esac

say "Сборка и запуск контейнеров (первый раз — 10–20 минут)"
docker compose up -d --build
# шлюз (nginx в web) узнаёт адреса сервисов только при запуске: после пересоздания сервисов — перезапуск
docker compose restart web

say "Жду готовности всех сервисов"
# shellcheck source=deploy/server/lib.sh
. "$DIR/deploy/server/lib.sh"
wait_ready "$LOCAL_URL" 90 || die "сервисы не ответили за 7,5 минут; журнал: docker compose ps; docker compose logs --tail 50"
echo "Приложение отвечает: ${LOCAL_URL}"
git rev-parse HEAD > .fishstock_deployed

SEED_OK=1
if [ ! -f .fishstock_seeded ] && [ "$SEED" != "none" ]; then
  say "Загрузка образцов данных (samples/) и расчёт: ${SEED}"
  SEED_OK=0
  for attempt in 1 2 3; do
    if docker compose run --rm --no-deps -T \
         -v "$DIR/tools:/repo/tools:ro" -v "$DIR/samples:/repo/samples:ro" -w /repo \
         users python tools/seed_samples.py --url http://web --login "$FISH_ADMIN_LOGIN" \
           --password "$FISH_ADMIN_PASSWORD" --run "$SEED"; then
      date '+%Y-%m-%d %H:%M' > .fishstock_seeded; SEED_OK=1; break
    fi
    [ "$attempt" = 3 ] || { echo "Повтор через 30 секунд (попытка $((attempt + 1)) из 3)"; sleep 30; wait_ready "$LOCAL_URL" 24 || true; }
  done
  [ "$SEED_OK" = 1 ] || echo "Образцы загрузить не удалось — повторите позже: $DIR/deploy/server/install.sh"
fi

say "Ежедневная резервная копия (cron, 03:17, хранятся 7)"
mkdir -p backups
CRON_LINE="17 3 * * * cd $DIR && FISH_BACKUP_KEEP=7 ./deploy/backup.sh backups >> backups/backup.log 2>&1 # fishstock-backup"
if crontab -l 2>/dev/null | grep -q 'fishstock-backup'; then
  echo "уже настроена"
else
  (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
  echo "добавлена"
fi

say "Готово"
echo "Внутри сервера: ${LOCAL_URL}"
echo "Логин администратора: ${FISH_ADMIN_LOGIN}"
if [ "$FIRST" = 1 ]; then
  echo "Пароль администратора: ${FISH_ADMIN_PASSWORD}"
fi
echo "Начальный пароль администратора хранится в $DIR/.env (строка FISH_ADMIN_PASSWORD); после входа смените его в приложении."
[ "$SEED_OK" = 1 ] || echo "ВНИМАНИЕ: образцы данных не загружены — запустите install.sh ещё раз."
echo
echo "Дальше — открыть адрес снаружи через nginx (нужен пароль sudo):"
echo "  $DIR/deploy/server/nginx_site.sh"
