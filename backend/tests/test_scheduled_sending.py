from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Delivery, Event, Greeting
from app.services.approval import approve_greeting
from app.services.due_sender import send_due_greetings


async def test_approve_does_not_send_before_event_date(db_session):
    today = dt.date(2025, 12, 20)
    tomorrow = today + dt.timedelta(days=1)

    c = Client(
        first_name="Вип",
        middle_name="Тестович",
        last_name="Клиент",
        profession="management",
        segment="vip",
        email="vip.real@mycompany.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=False,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id,
        event_type="manual",
        event_date=tomorrow,
        title="Праздник завтра",
        details={},
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    g = Greeting(
        event_id=ev.id,
        client_id=c.id,
        tone="official",
        subject="Тестовое поздравление",
        body="Достаточно длинный текст поздравления для прохождения валидации." * 3,
        image_path=None,
        status="needs_approval",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    res = await approve_greeting(db_session, greeting_id=g.id, approved_by="test", today=today)
    assert res["status"] == "approved"

    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert deliveries == []


async def test_due_sender_sends_on_event_day(db_session):
    today = dt.date(2025, 12, 20)
    tomorrow = today + dt.timedelta(days=1)

    c = Client(
        first_name="Иван",
        middle_name="Иванович",
        last_name="Петров",
        profession="accounting",
        segment="standard",
        email="user@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=False,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id,
        event_type="manual",
        event_date=tomorrow,
        title="Событие завтра",
        details={},
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    g = Greeting(
        event_id=ev.id,
        client_id=c.id,
        tone="warm",
        subject="Тестовое поздравление",
        body="Достаточно длинный текст поздравления для прохождения валидации." * 3,
        image_path=None,
        status="generated",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    # Not due yet
    res0 = await send_due_greetings(db_session, today=today)
    assert res0["sent"] == 0

    # Due tomorrow
    res1 = await send_due_greetings(db_session, today=tomorrow)
    assert res1["sent"] == 1

    await db_session.refresh(g)
    assert g.status == "sent"
