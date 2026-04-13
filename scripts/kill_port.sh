#!/usr/bin/env bash

# Usage:
#   ./scripts/kill_port.sh 8000

PORT=$1
if [ -z "$PORT" ]; then
  echo "Usage: scripts/kill_port.sh <port>"
  exit 1
fi

echo "[*] Finding processes on port $PORT..."

# lsof -i :<port> -t возвращает только PID процессов
PIDS=$(lsof -i :"$PORT" -t 2>/dev/null)

if [ -z "$PIDS" ]; then
  echo "[*] No processes found on port $PORT."
  exit 0
fi

for PID in $PIDS; do
  echo "[*] Killing PID $PID on port $PORT..."
  kill -9 "$PID" 2>/dev/null || echo "[!] Failed to kill PID $PID (permission denied or already exited)."
done

echo "[*] Done."