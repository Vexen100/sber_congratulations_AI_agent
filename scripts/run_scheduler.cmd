@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
  echo [!] Virtual environment not found at backend\.venv
  exit /b 1
)

call .venv\Scripts\activate
set PYTHONPATH=%cd%

python -m app.worker.run_scheduler


