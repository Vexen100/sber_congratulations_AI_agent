#!/usr/bin/env bash

# Переходим в папку backend относительно расположения скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../backend" || { echo "[!] Не удалось перейти в директорию backend."; exit 1; }

# Проверка наличия виртуального окружения
if [ ! -f ".venv/bin/python" ]; then
  echo "[!] Virtual environment not found at backend/.venv"
  echo "    Create it and install deps:"
  echo "    cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt"
  exit 1
fi

# Активируем окружение
source .venv/bin/activate

# Устанавливаем PYTHONPATH в текущую директорию
export PYTHONPATH="$(pwd)"

# Default port (8001). If binding is not allowed or busy, the runner will pick next available.
if [ -z "$HOST" ]; then
  HOST="127.0.0.1"
fi
if [ -z "$PORT" ]; then
  PORT=8001
fi

echo "[*] Starting dev server (HOST=$HOST, preferred PORT=$PORT)..."
python -m app.worker.run_dev_server