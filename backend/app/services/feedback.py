from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Event, Feedback, Greeting

log = logging.getLogger(__name__)

VALID_OUTCOMES = {"opened", "replied", "ignored", "unknown"}
VALID_TRAINING_VERDICTS = {"accepted", "rejected"}


def _should_save_to_vector_db(*, training_verdict: str | None, score: int | None) -> bool:
    """Rules for persisting examples for future few-shot retrieval.

    We only save *accepted* feedback with strong ratings to avoid polluting retrieval.
    """
    if training_verdict != "accepted":
        return False
    if score is None:
        return False
    return int(score) >= 4


def _auto_training_verdict(score: int) -> str:
    return "accepted" if int(score) >= 4 else "rejected"


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

    # Auto-verdict: if caller did not provide it, infer from score.
    if norm_verdict is None and score is not None:
        norm_verdict = _auto_training_verdict(int(score))

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

    if _should_save_to_vector_db(training_verdict=entry.training_verdict, score=entry.score):
        try:
            # Optional dependency. Must never break core save_feedback flow.
            from app.core.config import settings

            if not bool(getattr(settings, "vector_feedback_enabled", False)):
                return entry

            from app.services.vector_feedback import feedback_db

            client = await session.get(Client, greeting.client_id)
            event = await session.get(Event, greeting.event_id)
            if client and event and getattr(client, "profession", None):
                feedback_db.save_feedback_vector(
                    greeting_id=greeting_id,
                    greeting_text=greeting.body,
                    client_profession=str(client.profession),
                    holiday_title=event.title,
                    rating=int(entry.score or 0),
                    comment=(entry.notes or ""),
                )
        except Exception as e:
            log.warning("vector db save failed for greeting=%s: %s", greeting_id, e)

    return entry
