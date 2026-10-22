# Установка без Docker

Подходит для Windows, macOS и Linux.

## Подготовка

- **Python 3.11, 3.12 или 3.13** (python.org). На macOS проверьте: `python3 --version`.
- **Node.js 20 или новее** (nodejs.org) — для сборки интерфейса.
- **Git** — для загрузки приложения (или скачайте архив с GitHub).
- На macOS желательно выполнить `xcode-select --install` (компилятор C++ ускоряет байесовскую модель в разы); на Linux — установить `g++`.

## Установка

```bash
git clone -b develop https://github.com/ALB040570/FISH_stock.git
cd FISH_stock
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cd frontend && npm ci && npm run build && cd ..
```

## Запуск

```bash
source .venv/bin/activate
FISH_ADMIN_PASSWORD='пароль-администратора' python deploy/run_local.py
```

На Windows: `set FISH_ADMIN_PASSWORD=пароль-администратора` и затем `python deploy\run_local.py` (или `run_local.bat`).

Когда появится строка `FishStock: http://127.0.0.1:8080`, откройте этот адрес. Окно терминала не закрывайте — в нём работает приложение; остановить — **Ctrl+C**.

- Данные — в папке `data` рядом с приложением (переменная `FISH_DATA_DIR` меняет место).
- Ключи `FISH_JWT_SECRET` и `FISH_SERVICE_TOKEN`, если не заданы, создаются автоматически и хранятся в `data/.secrets.json`.
- Пароль администратора задаётся только при первом запуске; дальше достаточно `python deploy/run_local.py`.
- Параметры: `--port 9000` (другой порт), `--workers 1` (число воркеров), `--host 0.0.0.0` (доступ с других компьютеров сети), `--port-base 9100` (другие порты сервисов, если 8001–8007 заняты).

Дальше — [Первый запуск и загрузка данных](help:first-start).
