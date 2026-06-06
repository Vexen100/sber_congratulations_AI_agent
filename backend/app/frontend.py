from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = _PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

_SPA_ROUTES = (
    "/",
    "/clients",
    "/events",
    "/greetings",
    "/deliveries",
    "/runs",
    "/runs/{path:path}",
    "/project-planner",
)


def mount_react_frontend(app: FastAPI, log: logging.Logger) -> None:
    has_frontend_build = FRONTEND_INDEX.exists()
    if has_frontend_build and FRONTEND_ASSETS_DIR.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_ASSETS_DIR), check_dir=True),
            name="react-assets",
        )
        log.info("serving React build from %s", FRONTEND_DIST_DIR)
    elif has_frontend_build:
        log.warning("React assets directory is missing: %s", FRONTEND_ASSETS_DIR)
    else:
        log.warning("React build is missing: %s", FRONTEND_INDEX)

    router = APIRouter()

    async def react_index() -> Response:
        if has_frontend_build:
            return FileResponse(FRONTEND_INDEX)
        return HTMLResponse(
            """
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>React build не найден</title>
    <style>
      body { font-family: sans-serif; padding: 40px; line-height: 1.5; }
      code, pre { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; }
      pre { padding: 12px; }
    </style>
  </head>
  <body>
    <h1>React build не найден</h1>
    <p>Backend отдаёт React UI, но <code>frontend/dist/index.html</code> пока отсутствует.</p>
    <p>Соберите frontend:</p>
    <pre>cd frontend
npm install
npm run build</pre>
    <p>Или запустите Vite dev server и откройте <code>http://127.0.0.1:5173</code>.</p>
  </body>
</html>
            """.strip()
        )

    for route in _SPA_ROUTES:
        router.add_api_route(
            route,
            react_index,
            methods=["GET"],
            include_in_schema=False,
            response_model=None,
        )

    app.include_router(router)
