"""Сервис для сохранения обратной связи"""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, Greeting, Client, Event
from app.services.vector_feedback import feedback_db

logger = logging.getLogger(__name__)


async def save_feedback(
    session: AsyncSession,
    *,
    greeting_id: int,
    score: int,
    notes: str = "",
) -> Feedback:
    """
    Сохраняет обратную связь в обычную БД и векторную БД.
    
    Args:
        session: Сессия БД
        greeting_id: ID поздравления
        score: Оценка от 1 до 5
        notes: Комментарий менеджера
    """
    # Проверяем, существует ли поздравление
    greeting = (
        await session.execute(select(Greeting).where(Greeting.id == greeting_id))
    ).scalar_one()
    
    # Валидация
    if not (1 <= score <= 5):
        raise ValueError("score must be between 1 and 5")

    # Сохраняем в обычную БД
    entry = Feedback(
        greeting_id=greeting.id,
        score=score,
        outcome="manual",
        notes=(notes or "").strip() or None,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    
    # Сохраняем в векторную БД (только оценки 4-5)
    try:
        if score >= 4:
            client = await session.get(Client, greeting.client_id)
            event = await session.get(Event, greeting.event_id)
            
            if client and event and client.profession:
                feedback_db.save_feedback_vector(
                    greeting_id=greeting_id,
                    greeting_text=greeting.body,
                    client_profession=client.profession,
                    holiday_title=event.title,
                    rating=score,
                    comment=notes
                )
                logger.info(f"Сохранено в векторную БД: greeting_id={greeting_id}, rating={score}")
    except Exception as e:
        logger.error(f"Ошибка сохранения в векторную БД: {e}")
    
    return entry
    
