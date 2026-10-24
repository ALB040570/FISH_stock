#!/usr/bin/env bash
# Обновление FishStock на сервере — по команде:
#
#   ~/fishstock/deploy/server/update.sh            # показать, что нового, сделать копию, обновить
#   ~/fishstock/deploy/server/update.sh --check    # только показать, что нового
#   ~/fishstock/deploy/server/update.sh --force    # обновить, даже если идёт расчёт (он будет прерван)
#
# Если идёт расчёт, обновление его прервёт (контейнер воркера пересоздаётся). Поэтому скрипт сначала проверяет
# расчёты: при идущем расчёте спрашивает подтверждение (в фоне через nohup — останавливается, нужен --force).
# Запуски в очереди не теряются — их выполнит новый воркер.
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

# расчёты, которые идут сейчас (данные воркера — /data/algo_admin/calcs/*/meta.json; до решения № 66 — runs/*)
active_runs() {
  docker compose exec -T worker python - <<'PY' 2>/dev/null || true
import glob, json
from datetime import datetime, timezone
def ago(ts):
    try:
        m = int((datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() // 60)
    except Exception:
        return ""
    return f", {m // 60} ч {m % 60} мин назад" if m >= 60 else f", {m} мин назад"
rows = {"running": [], "queued": []}
for f in glob.glob("/data/algo_admin/calcs/*/meta.json") + glob.glob("/data/algo_admin/runs/*/meta.json"):
    try:
        m = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    st = m.get("state") or m.get("status")
    if st in rows and not m.get("deleted"):
        rows[st].append(f'{m.get("title") or m.get("calculation_title") or m.get("id")} [{m.get("water_body", "")}]{ago(m.get("started_at") or m.get("queued_at") or m.get("created_at") or "")}')
for x in rows["running"]:
    print("RUNNING  " + x)
for x in rows["queued"]:
    print("QUEUED   " + x)
PY
}
ACTIVE="$(active_runs)"
if [ -n "$ACTIVE" ]; then
  echo "== Расчёты сейчас:"
  echo "$ACTIVE" | sed -e 's/^RUNNING  /  выполняется: /' -e 's/^QUEUED   /  в очереди:   /'
fi
[ "${1:-}" = "--check" ] && exit 0

if echo "$ACTIVE" | grep -q '^RUNNING'; then
  echo "Обновление ПРЕРВЁТ выполняющийся расчёт (его придётся запустить заново). Запуски в очереди не теряются."
  if [ "${1:-}" = "--force" ]; then
    echo "Указан --force — продолжаю."
  elif [ -t 0 ]; then
    read -r -p "Прервать расчёт и обновить сейчас? Введите «да», чтобы продолжить: " ANSWER
    case "$ANSWER" in да|Да|ДА|yes|y) ;; *) echo "Обновление отменено. Повторите после окончания расчёта."; exit 1 ;; esac
  else
    echo "Обновление отменено (запуск без терминала). Дождитесь окончания расчёта или запустите с --force."
    exit 1
  fi
fi

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
# шлюз (nginx в web) узнаёт адреса сервисов только при запуске: после пересоздания сервисов — перезапуск
docker compose restart web

echo "== Проверка всех сервисов"
# shellcheck source=deploy/server/lib.sh
. "$DIR/deploy/server/lib.sh"
if wait_ready "$LOCAL_URL" 60; then
  git rev-parse HEAD > "$STAMP"
  echo "Готово: $(git log -1 --format='%h %s')"
  exit 0
fi
echo "Сервисы не ответили за 5 минут: docker compose ps; docker compose logs --tail 50"
exit 1
