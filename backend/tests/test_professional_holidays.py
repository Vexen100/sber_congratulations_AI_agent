from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Event
from app.services.event_detector import ensure_upcoming_events


async def test_event_detector_creates_professional_holiday_for_accountant(db_session):
    # Accountant day in our built-in rules: Nov 21
    today = dt.date(2025, 11, 20)
    c = Client(
        first_name="Илья",
        middle_name="Денисович",
        last_name="Захаров",
        profession="accounting",
        segment="standard",
        email="demo_client_1@example.com",
        preferred_channel="email",
        birth_date=None,
        is_demo=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    created = await ensure_upcoming_events(db_session, today=today, lookahead_days=2)
    assert created >= 1

    events = (
        (
            await db_session.execute(
                select(Event).where(Event.client_id == c.id).order_by(Event.event_date.asc())
            )
        )
        .scalars()
        .all()
    )
    assert any(
        e.title == "День бухгалтера" and e.event_date == dt.date(2025, 11, 21) for e in events
    )


async def test_event_detector_creates_professional_holiday_for_security_on_dec_20(db_session):
    today = dt.date(2025, 12, 20)
    c = Client(
        first_name="Наталья",
        middle_name="Олеговна",
        last_name="Морозова",
        profession="security",
        segment="vip",
        email="demo_client_1@example.com",
        preferred_channel="email",
        birth_date=None,
        is_demo=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    created = await ensure_upcoming_events(db_session, today=today, lookahead_days=0)
    assert created >= 1

    events = (
        (
            await db_session.execute(
                select(Event).where(Event.client_id == c.id).order_by(Event.event_date.asc())
            )
        )
        .scalars()
        .all()
    )
    assert any(
        e.title == "День специалиста по безопасности" and e.event_date == dt.date(2025, 12, 20)
        for e in events
    )
