from __future__ import annotations

import asyncio
import datetime as dt
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.agent.orchestrator import run_once
from app.core.logging import configure_logging
from app.db.session import SessionLocal


async def _job() -> None:
    async with SessionLocal() as session:
        summary = await run_once(session, today=dt.date.today())
        logging.getLogger(__name__).info("agent run summary: %s", summary.as_dict())


async def main() -> None:
    configure_logging()
    scheduler = AsyncIOScheduler()
    # MVP: every day at 09:00 local time (can be made configurable)
    scheduler.add_job(_job, "cron", hour=9, minute=0)
    scheduler.start()

    logging.getLogger(__name__).info("scheduler started; press Ctrl+C to stop")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
