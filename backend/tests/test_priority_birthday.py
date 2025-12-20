from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Delivery, Event, Greeting
from app.services.due_sender import send_due_greetings


async def test_birthday_has_priority_over_professional_holiday_same_day(db_session):
    today = dt.date(2025, 12, 20)

    c = Client(
        first_name="Тест",
        middle_name="Тестович",
        last_name="Клиент",
        profession="security",
        segment="standard",
        email="demo_client_1@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
        is_demo=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev_bday = Event(
        client_id=c.id,
        event_type="birthday",
        event_date=today,
        title="День рождения",
        details={},
    )
    ev_prof = Event(
        client_id=c.id,
        event_type="holiday",
        event_date=today,
        title="День специалиста по безопасности",
        details={"holiday_tags": {"type": "professional", "profession": "security"}},
    )
    db_session.add_all([ev_bday, ev_prof])
    await db_session.commit()
    await db_session.refresh(ev_bday)
    await db_session.refresh(ev_prof)

    g_bday = Greeting(
        event_id=ev_bday.id,
        client_id=c.id,
        tone="warm",
        subject="С днём рождения!",
        body="Достаточно длинный текст поздравления для прохождения валидации." * 3,
        image_path=None,
        status="generated",
    )
    g_prof = Greeting(
        event_id=ev_prof.id,
        client_id=c.id,
        tone="official",
        subject="С профессиональным праздником!",
        body="Достаточно длинный текст поздравления для прохождения валидации." * 3,
        image_path=None,
        status="generated",
    )
    db_session.add_all([g_bday, g_prof])
    await db_session.commit()
    await db_session.refresh(g_bday)
    await db_session.refresh(g_prof)

    res = await send_due_greetings(db_session, today=today)
    assert res["sent"] == 1
    assert res["suppressed"] == 1

    await db_session.refresh(g_bday)
    await db_session.refresh(g_prof)
    assert g_bday.status == "sent"
    assert g_prof.status == "skipped"

    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(deliveries) == 1
