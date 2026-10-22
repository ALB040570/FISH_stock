@echo off
REM Запуск FishStock без Docker (Windows): установите зависимости по README, затем запустите этот файл.
cd /d %~dp0
python deploy\run_local.py %*
pause
