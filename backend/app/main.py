from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent.orchestrator import run_once
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import create_dirs, init_db, seed_holidays_if_empty
from app.db.session import SessionLocal
from app.services.autonomy import get_or_create_state
from app.web.router import router as web_router

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = str((_BACKEND_ROOT / "data").resolve())
_WEB_STATIC_DIR = str((_BACKEND_ROOT / "app" / "web" / "static").resolve())


def create_app() -> FastAPI:
    configure_logging()
    log = logging.getLogger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        scheduler: AsyncIOScheduler | None = None
        await create_dirs()
        await init_db()
        async with SessionLocal() as session:
            added = await seed_holidays_if_empty(session)
            if added:
                log.info("Seeded holidays: %s", added)

        async def _autonomy_job() -> None:
            async with SessionLocal() as session:
                state = await get_or_create_state(session)
                if not state.enabled:
                    return
                summary = await run_once(session, triggered_by="scheduler")
                log.info("autonomy run summary: %s", summary.as_dict())

        # In-process scheduler for autonomous mode (daily 09:00 in configured timezone).
        scheduler = AsyncIOScheduler(timezone=ZoneInfo(getattr(settings, "tz", "Europe/Moscow")))
        scheduler.add_job(_autonomy_job, "cron", hour=9, minute=0)
        scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Sber Congratulations AI Agent (MVP)", lifespan=lifespan)

    app.include_router(api_router)
    app.include_router(web_router)

    # Bundled UI assets (CSS/SVG) must be versioned in git and not live in gitignored backend/data/.
    app.mount("/static", StaticFiles(directory=_WEB_STATIC_DIR, check_dir=True), name="static")

    # Serve generated artifacts for demo convenience (cards/outbox)
    # NOTE: With uvicorn --reload on Windows, the app can be imported before startup hooks run.
    # StaticFiles by default checks directory existence at mount time, so we disable the check
    # and create the directory in the startup event.
    app.mount("/data", StaticFiles(directory=_DATA_DIR, check_dir=False), name="data")

    return app


app = create_app()
