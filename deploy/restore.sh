#!/usr/bin/env sh
# Восстановление тома данных из архива: ./deploy/restore.sh backups/fishstocke_YYYYMMDD_HHMMSS.tar.gz
# Сервисы останавливаются; текущие данные сохраняются в /data.before_restore_* внутри тома.
set -e
[ -f "$1" ] || { echo "Укажите архив"; exit 1; }
python3 tools/backup.py verify "$1"
docker compose stop web worker algo_admin algo_model dashboards data_admin data_model
docker compose cp tools/backup.py users:/tmp/backup.py
docker compose cp "$1" users:/tmp/restore.tar.gz
docker compose exec -T users sh -c 'mkdir -p /tmp/r && python /tmp/backup.py restore /tmp/restore.tar.gz --data /tmp/r/data && \
  mkdir -p /data/.before_restore && find /data -mindepth 1 -maxdepth 1 ! -name .before_restore -exec mv {} /data/.before_restore/ \; && \
  cp -a /tmp/r/data/. /data/ && rm -rf /tmp/r /tmp/restore.tar.gz'
docker compose restart users
docker compose start data_model data_admin algo_model algo_admin dashboards worker web
echo "Восстановлено. Предыдущие данные — в томе, каталог /data/.before_restore"
