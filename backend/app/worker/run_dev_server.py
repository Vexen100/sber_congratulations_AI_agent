from __future__ import annotations

import os
import socket
from typing import Iterable

import uvicorn


def _iter_ports(preferred: int) -> Iterable[int]:
    # Try preferred first, then a small range, then common dev ports.
    yield preferred
    for p in range(preferred + 1, preferred + 21):
        yield p
    for p in (8080, 8888, 5000, 3000):
        if p != preferred:
            yield p


def _can_bind(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Ensure we really test binding availability
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    preferred_port = int(os.getenv("PORT", "8001"))

    chosen: int | None = None
    for port in _iter_ports(preferred_port):
        if _can_bind(host, port):
            chosen = port
            break

    if chosen is None:
        raise RuntimeError(
            f"Could not bind to any port near {preferred_port}. "
            f"Try setting PORT to another value or check Windows excluded port ranges."
        )

    print(f"[*] Starting server on http://{host}:{chosen}/ (preferred={preferred_port})")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=chosen,
        reload=True,
    )


if __name__ == "__main__":
    main()
