from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import run_once
from app.db.session import get_session
from app.schemas.agent import AgentRunResult

router = APIRouter(prefix="/agent")


@router.post("/run-once", response_model=AgentRunResult)
async def run_agent_once(session: AsyncSession = Depends(get_session)) -> dict:
    summary = await run_once(session, triggered_by="api")
    return summary.as_dict()
