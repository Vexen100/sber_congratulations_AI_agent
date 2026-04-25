from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client, Delivery, Event, Greeting
from app.services.due_sender import send_due_greetings


async def test_generated_does_not_send_before_event_date(db_session):
    today = dt.date(2025, 12, 20)
    tomorrow = today + dt.timedelta(days=1)

    c = Client(
        first_name="Вип",
        middle_name="Тестович",
        last_name="Клиент",
        profession="management",
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
        status="generated",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    res = await send_due_greetings(db_session, today=today)
    assert res["sent"] == 0

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


async def test_legacy_approved_status_waits_for_event_day(db_session):
    """Older rows may still use status=approved; sending still waits for event_date."""
    today = dt.date(2025, 12, 20)
    tomorrow = today + dt.timedelta(days=1)

    c = Client(
        first_name="Мария",
        middle_name="Петровна",
        last_name="Клиент",
        profession="management",
        email="m@mycompany.test",
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
        title="Праздник позже",
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
        status="approved",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    res = await send_due_greetings(db_session, today=today)
    assert res["sent"] == 0
    await db_session.refresh(g)
    assert g.status == "approved"


async def test_due_sender_can_send_future_greeting_immediately(db_session, monkeypatch):
    today = dt.date(2025, 12, 20)
    future_day = today + dt.timedelta(days=5)

    c = Client(
        first_name="Иван",
        middle_name="Иванович",
        last_name="Петров",
        profession="accounting",
        email="real.user@mycompany.test",
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
        event_date=future_day,
        title="Событие позже",
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

    res = await send_due_greetings(db_session, today=today)
    assert res["sent"] == 0

    await db_session.refresh(g)
    assert g.status == "generated"


async def test_due_sender_in_smtp_mode_without_email_uses_file_fallback(
    db_session, monkeypatch, tmp_path
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"), raising=False)

    today = dt.date(2025, 12, 20)
    c = Client(
        first_name="Без",
        middle_name="Почтыч",
        last_name="Клиент",
        profession="accounting",
        email=None,
        phone=None,
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
        event_date=today,
        title="Событие сегодня",
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

    res = await send_due_greetings(db_session, today=today)
    assert res["sent"] == 1
    assert res["errors"] == 0

    await db_session.refresh(g)
    assert g.status == "sent"

    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(deliveries) == 1
    assert deliveries[0].channel == "file"
    assert deliveries[0].recipient == f"client:{c.id}"
