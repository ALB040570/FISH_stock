# Резервное копирование и восстановление

Все данные приложения — один каталог (том) данных. Копия этого каталога — полная резервная копия.

## С Docker

```bash
./deploy/backup.sh                                          # архив в ./backups, хранятся последние 30
./deploy/restore.sh backups/fishstocke_20261024_030000.tar.gz
```

Ежедневная копия в 3:00 (cron): `0 3 * * * cd /opt/fishstocke && ./deploy/backup.sh >> backups/backup.log 2>&1`

## Без Docker

```bash
python tools/backup.py create --data ./data --out ./backups
python tools/backup.py verify backups/<архив>.tar.gz
python tools/backup.py restore backups/<архив>.tar.gz --data ./data --force
```

Перед восстановлением остановите приложение.

## Проверка и хранение

- Архив содержит контрольные суммы всех файлов; `verify` проверяет целостность.
- При восстановлении прежнее состояние сохраняется: в Docker — в `/data/.before_restore` внутри тома, без Docker — в папку `data.before_restore_<дата_время>` рядом с каталогом данных.
- Храните копии **вне сервера** (другой диск, сетевое хранилище).
- Файл `.env` с секретами в архив не входит — храните его отдельно и надёжно.
