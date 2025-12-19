from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Event, Holiday
from app.services.event_detector import ensure_upcoming_events


async def test_holiday_recipients_are_limited(db_session):
    today = dt.date.today()

    # Create many clients without birthdays to isolate holiday event creation
    for i in range(30):
        db_session.add(
            Client(
                first_name=f"Test{i}",
                last_name="User",
                segment="standard",
                email=f"test{i}@example.com",
                preferred_channel="email",
                birth_date=None,
            )
        )
    db_session.add(
        Holiday(
            date=today,
            title="Тестовый праздник",
            tags={},
            is_business_relevant=True,
        )
    )
    await db_session.commit()

    await ensure_upcoming_events(
        db_session, today=today, lookahead_days=1, max_holiday_recipients=7
    )

    holiday_events = (
        (await db_session.execute(select(Event).where(Event.event_type == "holiday")))
        .scalars()
        .all()
    )
    assert len(holiday_events) <= 7
