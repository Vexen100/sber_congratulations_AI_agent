#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR/../backend" || { echo "[!] Не удалось перейти в директорию backend."; exit 1; }

if [ ! -f ".venv/bin/python" ]; then
  echo "[!] Virtual environment not found at backend/.venv"
  exit 1
fi

source .venv/bin/activate

export PYTHONPATH="$(pwd)"

python -m app.worker.run_scheduler