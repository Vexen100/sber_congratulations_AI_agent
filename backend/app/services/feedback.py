from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, Greeting

VALID_OUTCOMES = {"opened", "replied", "ignored", "unknown"}
VALID_TRAINING_VERDICTS = {"accepted", "rejected"}


async def save_feedback(
    session: AsyncSession,
    *,
    greeting_id: int,
    score: int | None,
    outcome: str = "unknown",
    notes: str | None = None,
    training_verdict: str | None = None,
) -> Feedback:
    greeting = (
        await session.execute(select(Greeting).where(Greeting.id == greeting_id))
    ).scalar_one()
    norm_verdict = (training_verdict or "").strip().lower() or None
    if norm_verdict is not None and norm_verdict not in VALID_TRAINING_VERDICTS:
        raise ValueError("training_verdict must be 'accepted' or 'rejected'")
    if norm_verdict is not None:
        if score is None:
            raise ValueError("score is required when training_verdict is set")
        if not (1 <= int(score) <= 5):
            raise ValueError("score must be between 1 and 5")
    elif score is not None and not (1 <= int(score) <= 5):
        raise ValueError("score must be between 1 and 5")
    norm_outcome = (outcome or "unknown").strip().lower()
    if norm_outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of: {', '.join(sorted(VALID_OUTCOMES))}")

    entry = Feedback(
        greeting_id=greeting.id,
        score=int(score) if score is not None else None,
        outcome=norm_outcome,
        notes=(notes or "").strip() or None,
        training_verdict=norm_verdict,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry
