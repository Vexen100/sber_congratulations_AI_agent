@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
  echo [!] Virtual environment not found at backend\.venv
  echo     Run: scripts\setup_backend.cmd
  exit /b 1
)

call .venv\Scripts\activate
set PYTHONPATH=%cd%

echo [*] Running GigaChat end-to-end smoke test...
python -m app.worker.smoke_gigachat


