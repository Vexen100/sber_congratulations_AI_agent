from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.init_db import init_db
from app.db.models import AgentRun, AutonomyState
from app.db.session import create_engine


@pytest.mark.asyncio
async def test_scheduler_job_skips_when_autonomy_disabled(tmp_path, monkeypatch):
    db_path = tmp_path / "scheduler.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_engine(url)
    await init_db(engine)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as session:
        # Explicitly disable autonomy.
        state = AutonomyState(id=1, enabled=False, updated_at=dt.datetime.now(dt.timezone.utc))
        session.add(state)
        await session.commit()

    # Patch scheduler module to use our isolated DB sessionmaker.
    from app.worker import run_scheduler as sched  # imported after DB is ready

    monkeypatch.setattr(sched, "SessionLocal", SessionLocal, raising=True)

    await sched._job()

    async with SessionLocal() as session:
        runs = (await session.execute(select(AgentRun.id))).scalars().all()
        assert runs == []

    await engine.dispose()
