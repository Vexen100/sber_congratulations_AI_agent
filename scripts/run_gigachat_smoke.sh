#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR/../backend" || { echo "[!] Не удалось перейти в директорию backend."; exit 1; }

if [ ! -f ".venv/bin/python" ]; then
  echo "[!] Virtual environment not found at backend/.venv"
  echo "    Run: scripts/setup_backend.sh"
  exit 1
fi

source .venv/bin/activate

export PYTHONPATH="$(pwd)"

echo "[*] Running GigaChat end-to-end smoke test..."
python -m app.worker.smoke_gigachat