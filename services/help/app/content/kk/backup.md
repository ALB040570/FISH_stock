# Сақтық көшірме жасау және қалпына келтіру

Қосымшаның барлық деректері — бір деректер каталогы (томы). Осы каталогтың көшірмесі — толық сақтық көшірме.

## Docker-мен

```bash
./deploy/backup.sh                                          # ./backups ішіндегі мұрағат, соңғы 30-ы сақталады
./deploy/restore.sh backups/fishstock_20261024_030000.tar.gz
```

Сағат 3:00-де күнделікті көшірме (cron): `0 3 * * * cd /opt/fishstock && ./deploy/backup.sh >> backups/backup.log 2>&1`

## Docker-сіз

```bash
python tools/backup.py create --data ./data --out ./backups
python tools/backup.py verify backups/<мұрағат>.tar.gz
python tools/backup.py restore backups/<мұрағат>.tar.gz --data ./data --force
```

Қалпына келтірмес бұрын қосымшаны тоқтатыңыз.

## Тексеру және сақтау

- Мұрағатта барлық файлдардың бақылау сомалары бар; `verify` тұтастығын тексереді.
- Қалпына келтіргенде бұрынғы күй сақталады: Docker-де — том ішіндегі `/data/.before_restore` ішінде, Docker-сіз — деректер каталогының жанындағы `data.before_restore_<күні_уақыты>` қалтасында.
- Көшірмелерді **серверден тыс** сақтаңыз (басқа диск, желілік қойма).
- Құпиялары бар `.env` файлы мұрағатқа кірмейді — оны бөлек және сенімді сақтаңыз.
