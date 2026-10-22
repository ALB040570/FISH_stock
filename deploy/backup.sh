#!/usr/bin/env sh
# Резервная копия тома данных Docker Compose: ./deploy/backup.sh [каталог]  (по умолчанию ./backups)
# Рекомендуется по cron ежедневно, например: 0 3 * * * cd /opt/fishstock && ./deploy/backup.sh >> backups/backup.log 2>&1
set -e
OUT="${1:-backups}"
mkdir -p "$OUT"
docker compose cp tools/backup.py users:/tmp/backup.py >/dev/null
docker compose exec -T users python /tmp/backup.py create --data /data --out /tmp/fsbackup
F=$(docker compose exec -T users sh -c 'ls -t /tmp/fsbackup/*.tar.gz | head -1' | tr -d '\r')
docker compose cp "users:$F" "$OUT/"
docker compose exec -T users rm -rf /tmp/fsbackup
echo "Готово: $OUT/$(basename "$F")"
# хранить последние FISH_BACKUP_KEEP копий (по умолчанию 30)
KEEP="${FISH_BACKUP_KEEP:-30}"
ls -t "$OUT"/fishstock*_*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
