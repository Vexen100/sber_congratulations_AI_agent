from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.logging import configure_logging
from app.db.init_db import create_dirs, init_db, seed_holidays_if_empty
from app.db.session import SessionLocal
from app.web.router import router as web_router


def create_app() -> FastAPI:
    configure_logging()
    log = logging.getLogger("app")

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        await create_dirs()
        await init_db()
        async with SessionLocal() as session:
            added = await seed_holidays_if_empty(session)
            if added:
                log.info("Seeded holidays: %s", added)
        yield

    app = FastAPI(title="Sber Congratulations AI Agent (MVP)", lifespan=lifespan)

    app.include_router(api_router)
    app.include_router(web_router)

    # Serve generated artifacts for demo convenience (cards/outbox)
    # NOTE: With uvicorn --reload on Windows, the app can be imported before startup hooks run.
    # StaticFiles by default checks directory existence at mount time, so we disable the check
    # and create the directory in the startup event.
    app.mount("/data", StaticFiles(directory="data", check_dir=False), name="data")

    return app


app = create_app()
