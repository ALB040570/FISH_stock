# Docker-сіз орнату

Windows, macOS және Linux үшін жарамды.

## Дайындық

- **Python 3.11, 3.12 немесе 3.13** (python.org). macOS-та тексеріңіз: `python3 --version`.
- **Node.js 20 немесе жаңарақ** (nodejs.org) — интерфейсті жинау үшін.
- **Git** — қосымшаны жүктеу үшін (немесе GitHub-тан мұрағатты жүктеп алыңыз).
- macOS-та `xcode-select --install` орындаған жөн (C++ компиляторы байестік модельді бірнеше есе жылдамдатады); Linux-та — `g++` орнатыңыз.

## Орнату

```bash
git clone -b develop https://github.com/ALB040570/FISH_stock.git
cd FISH_stock
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cd frontend && npm ci && npm run build && cd ..
```

## Іске қосу

```bash
source .venv/bin/activate
FISH_ADMIN_PASSWORD='әкімші-құпиясөзі' python deploy/run_local.py
```

Windows-та: `set FISH_ADMIN_PASSWORD=әкімші-құпиясөзі`, содан кейін `python deploy\run_local.py` (немесе `run_local.bat`).

`FishStock: http://127.0.0.1:8080` жолы шыққанда осы мекенжайды ашыңыз. Терминал терезесін жаппаңыз — қосымша сонда жұмыс істейді; тоқтату — **Ctrl+C**.

- Деректер — қосымшаның жанындағы `data` қалтасында (`FISH_DATA_DIR` айнымалысы орнын өзгертеді).
- `FISH_JWT_SECRET` және `FISH_SERVICE_TOKEN` кілттері берілмесе, автоматты түрде жасалып, `data/.secrets.json` ішінде сақталады.
- Әкімшінің құпиясөзі тек алғаш іске қосқанда беріледі; әрі қарай `python deploy/run_local.py` жеткілікті.
- Параметрлер: `--port 9000` (басқа порт), `--workers 1` (воркерлер саны), `--host 0.0.0.0` (желідегі басқа компьютерлерден қолжетімділік), `--port-base 9100` (8001–8007 бос болмаса, қызметтердің басқа порттары).

Әрі қарай — [Алғашқы іске қосу және деректерді жүктеу](help:first-start).
