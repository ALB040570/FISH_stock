@echo off
rem Start the web app and open http://127.0.0.1:8000
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
start "" http://127.0.0.1:8000
rem Reload only when code in app\ or core\ changes (not on pip installs into .venv or files in results\)
python -m uvicorn app.main:app --reload --reload-dir app --reload-dir core --host 127.0.0.1 --port 8000
pause
