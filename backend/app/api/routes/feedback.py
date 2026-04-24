from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback
from app.db.session import get_session
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.feedback import save_feedback

router = APIRouter(prefix="/feedback")


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(session: AsyncSession = Depends(get_session)) -> list[Feedback]:
    return (await session.execute(select(Feedback).order_by(Feedback.id.desc()))).scalars().all()


@router.post("", response_model=FeedbackOut)
async def create_feedback(
    payload: FeedbackCreate, session: AsyncSession = Depends(get_session)
) -> Feedback:
    return await save_feedback(
        session,
        greeting_id=payload.greeting_id,
        score=payload.score,
        outcome=payload.outcome,
        notes=payload.notes,
        training_verdict=payload.training_verdict,
    )
