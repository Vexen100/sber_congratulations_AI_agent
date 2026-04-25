from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.autonomy import AutonomyStatusOut
from app.services.autonomy import get_or_create_state, next_daily_run_at, set_enabled

router = APIRouter(prefix="/autonomy")


@router.get("/status", response_model=AutonomyStatusOut)
async def autonomy_status(
    session: AsyncSession = Depends(get_session),
) -> AutonomyStatusOut:
    state = await get_or_create_state(session)
    now = dt.datetime.now(dt.timezone.utc)
    next_run = next_daily_run_at(now=now) if state.enabled else None
    return AutonomyStatusOut(enabled=state.enabled, next_run_at=next_run)


@router.post("/enable", response_model=AutonomyStatusOut)
async def autonomy_enable(
    session: AsyncSession = Depends(get_session),
) -> AutonomyStatusOut:
    state = await set_enabled(session, enabled=True)
    now = dt.datetime.now(dt.timezone.utc)
    return AutonomyStatusOut(enabled=state.enabled, next_run_at=next_daily_run_at(now=now))


@router.post("/disable", response_model=AutonomyStatusOut)
async def autonomy_disable(
    session: AsyncSession = Depends(get_session),
) -> AutonomyStatusOut:
    state = await set_enabled(session, enabled=False)
    return AutonomyStatusOut(enabled=state.enabled, next_run_at=None)
