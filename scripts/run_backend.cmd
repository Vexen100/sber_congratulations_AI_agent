@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
  echo [!] Virtual environment not found at backend\.venv
  echo     Create it and install deps:
  echo     cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt -r requirements-dev.txt
  exit /b 1
)

call .venv\Scripts\activate
set PYTHONPATH=%cd%

REM Default port (8001). If binding is not allowed (WinError 10013) or busy, the runner will pick next available.
if "%HOST%"=="" set HOST=127.0.0.1
if "%PORT%"=="" set PORT=8001

echo [*] Starting dev server (HOST=%HOST%, preferred PORT=%PORT%)...
python -m app.worker.run_dev_server


