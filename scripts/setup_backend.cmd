@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0..\backend"

echo [*] Creating venv (backend\.venv)...
python -m venv .venv
if errorlevel 1 (
  echo [!] Failed to create venv. Ensure Python is installed and on PATH.
  exit /b 1
)

call .venv\Scripts\activate

echo [*] Upgrading pip...
python -m pip install --upgrade pip

echo [*] Installing dependencies...
pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 (
  echo [!] Dependency installation failed.
  exit /b 1
)

if not exist ".env" (
  echo [*] Creating .env from env.example...
  copy /y env.example .env >nul
)

echo [*] Done.
echo     Next:
echo       cd .. ^&^& scripts\run_backend.cmd


