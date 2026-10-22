#!/usr/bin/env bash
# Обновление FishStock на сервере — по команде:
#
#   ~/fishstock/deploy/server/update.sh            # показать, что нового, сделать копию, обновить
#   ~/fishstock/deploy/server/update.sh --check    # только показать, что нового
#
# Порядок: резервная копия данных -> git pull (ветка, на которой стоит копия, обычно develop) -> пересборка.
# Если сборка не удалась, продолжают работать прежние контейнеры. Данные (том fishstock_fishdata) сохраняются.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DIR"
[ -f .env ] || { echo "Сначала выполните deploy/server/install.sh"; exit 1; }
# shellcheck disable=SC1091
set -a; . ./.env; set +a
case "$FISH_HTTP_PORT" in *:*) LOCAL_URL="http://${FISH_HTTP_PORT}" ;; *) LOCAL_URL="http://127.0.0.1:${FISH_HTTP_PORT}" ;; esac
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
# последняя версия, успешно собранная и запущенная (пишут install.sh и этот скрипт)
STAMP=.fishstock_deployed
DEPLOYED="$(cat "$STAMP" 2>/dev/null || git rev-parse HEAD)"

echo "== Работает версия: $(git log -1 --format='%h %ad %s' --date=format:'%d.%m.%Y %H:%M' "$DEPLOYED")"
git fetch -q origin "$BRANCH"
TARGET="$(git rev-parse "origin/$BRANCH")"
if [ "$DEPLOYED" = "$TARGET" ]; then
  echo "Обновлений нет (ветка $BRANCH)."
  exit 0
fi
echo "== Новое в $BRANCH:"
git log --format='  %h %ad %s' --date=format:'%d.%m %H:%M' "$DEPLOYED..$TARGET"
[ "${1:-}" = "--check" ] && exit 0

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "В папке $DIR есть изменённые файлы — обновление остановлено:"
  git status --short --untracked-files=no
  exit 1
fi

echo "== Резервная копия данных"
mkdir -p backups
FISH_BACKUP_KEEP=7 ./deploy/backup.sh backups

echo "== Загрузка обновлений"
git pull -q --ff-only origin "$BRANCH"

echo "== Сборка и перезапуск"
if ! docker compose up -d --build; then
  echo "Сборка не удалась — работают прежние контейнеры. Журнал выше."
  exit 1
fi

echo "== Проверка"
for _ in $(seq 1 60); do
  if curl -fsS "$LOCAL_URL/api/users/health" >/dev/null 2>&1 \
     && curl -fsS "$LOCAL_URL/api/dashboards/health" >/dev/null 2>&1; then
    git rev-parse HEAD > "$STAMP"
    echo "Готово: $(git log -1 --format='%h %s')"
    exit 0
  fi
  sleep 5
done
echo "Приложение не ответило за 5 минут: docker compose ps; docker compose logs --tail 50"
exit 1
