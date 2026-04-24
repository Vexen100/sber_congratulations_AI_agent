from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import AgentRun, Client, Delivery, Event, Feedback, Greeting, Holiday
from app.services.feedback import save_feedback
from app.services.reset_runtime import reset_runtime_data


async def test_reset_runtime_keeps_clients_and_holidays(db_session, tmp_path, monkeypatch):
    today = dt.date.today()
    db_session.add(
        Client(
            first_name="A",
            last_name="B",
            email="ab@example.com",
            preferred_channel="email",
            birth_date=dt.date(1990, today.month, today.day),
        )
    )
    db_session.add(Holiday(date=today, title="Test holiday", tags={}, is_business_relevant=True))
    await db_session.commit()

    await run_once(db_session, today=today, lookahead_days=1, triggered_by="test")

    assert (await db_session.execute(select(Event))).scalars().all()

    await reset_runtime_data(db_session)

    assert (await db_session.execute(select(Client))).scalars().all()
    assert (await db_session.execute(select(Holiday))).scalars().all()
    assert (await db_session.execute(select(Event))).scalars().all() == []
    assert (await db_session.execute(select(Greeting))).scalars().all() == []
    assert (await db_session.execute(select(Delivery))).scalars().all() == []
    assert (await db_session.execute(select(AgentRun))).scalars().all() == []


async def test_reset_runtime_clears_feedback_and_can_remove_clients(db_session):
    today = dt.date.today()
    client = Client(
        first_name="Ирина",
        middle_name="Ивановна",
        last_name="Петрова",
        email="irina@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
        is_demo=True,
    )
    db_session.add(client)
    db_session.add(Holiday(date=today, title="Test holiday", tags={}, is_business_relevant=True))
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=today,
        title="Повод",
        details={},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    greeting = Greeting(
        event_id=event.id,
        client_id=client.id,
        tone="warm",
        subject="Поздравление",
        body="Достаточно длинный текст поздравления для сохранения в БД." * 5,
        image_path=None,
        status="generated",
    )
    db_session.add(greeting)
    await db_session.commit()
    await db_session.refresh(greeting)

    await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=5,
        outcome="opened",
        notes="Тестовый отзыв",
    )

    result = await reset_runtime_data(db_session, clear_clients=True)

    assert result["cleared_clients"] == 1
    assert (await db_session.execute(select(Client))).scalars().all() == []
    assert (await db_session.execute(select(Event))).scalars().all() == []
    assert (await db_session.execute(select(Greeting))).scalars().all() == []
    assert (await db_session.execute(select(Feedback))).scalars().all() == []
    assert (await db_session.execute(select(Holiday))).scalars().all()
