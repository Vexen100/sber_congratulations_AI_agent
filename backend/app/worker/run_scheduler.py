from __future__ import annotations

import asyncio
import datetime as dt
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.autonomy import get_or_create_state


async def _autonomy_enabled(session) -> bool:
    state = await get_or_create_state(session)
    return bool(state.enabled)


async def _job() -> None:
    async with SessionLocal() as session:
        if not await _autonomy_enabled(session):
            logging.getLogger(__name__).info("autonomy disabled; skipping scheduler job")
            return
        summary = await run_once(session, today=dt.date.today(), triggered_by="scheduler")
        logging.getLogger(__name__).info("agent run summary: %s", summary.as_dict())


async def main() -> None:
    configure_logging()
    mode = (getattr(settings, "scheduler_mode", "off") or "off").strip().lower()
    if mode != "worker":
        logging.getLogger(__name__).info("scheduler process disabled (mode=%s); exiting", mode)
        return
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(getattr(settings, "tz", "Europe/Moscow")))
    # Regular mode: every day at 09:00 in configured timezone
    scheduler.add_job(_job, "cron", hour=9, minute=0)
    scheduler.start()

    # Demo-friendly: run once on start (so you don't have to wait for 09:00).
    async with SessionLocal() as session:
        if await _autonomy_enabled(session):
            await _job()
        else:
            logging.getLogger(__name__).info("autonomy disabled; skipping run-on-start")

    logging.getLogger(__name__).info("scheduler started; press Ctrl+C to stop")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
