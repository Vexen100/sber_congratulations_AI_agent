#!/bin/bash

# Получаем абсолютный путь к директории, где находится скрипт
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Переходим в папку backend
cd "$SCRIPT_DIR/../backend" || { echo "[!] Не удалось перейти в директорию backend."; exit 1; }

echo "[*] Creating venv (backend/.venv)..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
  echo "[!] Failed to create venv. Ensure Python 3 is installed and on PATH."
  exit 1
fi

# Активируем виртуальное окружение (macOS/Linux путь)
source .venv/bin/activate

echo "[*] Upgrading pip..."
python -m pip install --upgrade pip

echo "[*] Installing dependencies..."
pip install -r requirements.txt -r requirements-dev.txt
if [ $? -ne 0 ]; then
  echo "[!] Dependency installation failed."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "[*] Creating .env from env.example..."
  cp env.example .env
fi

echo "[*] Done."
echo "    Next:"
echo "      cd .. && ./scripts/run_backend.sh"