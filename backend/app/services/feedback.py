"""Сервис для сохранения обратной связи"""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, Greeting, Client, Event
from app.services.vector_feedback import feedback_db

logger = logging.getLogger(__name__)

VALID_OUTCOMES = {"approve", "reject"}


async def save_feedback(
    session: AsyncSession,
    *,
    greeting_id: int,
    score: int | None,
    outcome: str = "approve",
    notes: str | None = None,
) -> Feedback:
    
    greeting = (
        await session.execute(select(Greeting).where(Greeting.id == greeting_id))
    ).scalar_one()
    
    norm_outcome = (outcome or "approve").strip().lower()
    
    # Валидация
    if norm_outcome == 'approve' and score is None:
        raise ValueError("Для approve необходимо указать оценку")
    
    if score is not None and not (1 <= int(score) <= 5):
        raise ValueError("score must be between 1 and 5")
    
    if norm_outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of: {', '.join(sorted(VALID_OUTCOMES))}")

    # Сохраняем в обычную БД (всегда)
    entry = Feedback(
        greeting_id=greeting.id,
        score=int(score) if score is not None else None,
        outcome=norm_outcome,
        notes=(notes or "").strip() or None,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    
    # Сохраняем в векторную БД (только approve с хорошей оценкой)
    try:
        if norm_outcome == 'approve' and score is not None and score >= 4:
            client = await session.get(Client, greeting.client_id)
            event = await session.get(Event, greeting.event_id)
            
            if client and event and client.profession:
                feedback_db.save_feedback_vector(
                    greeting_id=greeting_id,
                    greeting_text=greeting.body,
                    client_profession=client.profession,
                    holiday_title=event.title,
                    rating=score,
                    comment=notes or ""
                )
                logger.info(f"Сохранено в векторную БД: greeting_id={greeting_id}, rating={score}")
    except Exception as e:
        logger.error(f"Ошибка сохранения в векторную БД: {e}")
    
    return entry
