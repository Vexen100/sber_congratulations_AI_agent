from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AutonomyState


def next_daily_run_at(*, now: dt.datetime) -> dt.datetime:
    tz = ZoneInfo(getattr(settings, "tz", "Europe/Moscow"))
    local_now = now.astimezone(tz)
    candidate = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
    if candidate <= local_now:
        candidate = candidate + dt.timedelta(days=1)
    return candidate


async def get_or_create_state(session: AsyncSession) -> AutonomyState:
    state = (
        await session.execute(select(AutonomyState).where(AutonomyState.id == 1))
    ).scalar_one_or_none()
    if state is None:
        state = AutonomyState(id=1, enabled=False)
        session.add(state)
        await session.commit()
        await session.refresh(state)
    return state


async def set_enabled(session: AsyncSession, *, enabled: bool) -> AutonomyState:
    state = await get_or_create_state(session)
    state.enabled = enabled
    state.updated_at = dt.datetime.now(dt.timezone.utc)
    await session.commit()
    await session.refresh(state)
    return state
