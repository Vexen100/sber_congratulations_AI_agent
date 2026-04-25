from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app.db.models import Client, Event, Feedback, Greeting
from app.services.feedback import save_feedback


async def test_save_feedback_persists_entry(db_session):
    client = Client(
        first_name="Ирина",
        middle_name="Владимировна",
        last_name="Соколова",
        company_name="ООО Альфа-Логистика",
        profession="logistics",
        email="irina@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Тестовый повод",
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

    feedback = await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=5,
        outcome="opened",
        notes="Хорошая персонализация по отрасли.",
    )
    assert feedback.score == 5
    assert feedback.outcome == "opened"

    saved = (await db_session.execute(select(Feedback))).scalars().all()
    assert len(saved) == 1
    assert saved[0].notes == "Хорошая персонализация по отрасли."


async def test_save_feedback_rejects_invalid_score(db_session):
    client = Client(
        first_name="Анна",
        middle_name="Михайловна",
        last_name="Романова",
        company_name="ООО Альфа-Логистика",
        profession="management",
        email="anna@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Тестовый повод",
        details={},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    greeting = Greeting(
        event_id=event.id,
        client_id=client.id,
        tone="official",
        subject="Поздравление",
        body="Достаточно длинный текст поздравления для сохранения в БД." * 5,
        image_path=None,
        status="generated",
    )
    db_session.add(greeting)
    await db_session.commit()
    await db_session.refresh(greeting)

    with pytest.raises(ValueError):
        await save_feedback(db_session, greeting_id=greeting.id, score=7, outcome="opened")


async def test_save_feedback_training_verdict_requires_score(db_session):
    client = Client(
        first_name="Пётр",
        middle_name="Иванович",
        last_name="Новиков",
        profession="it",
        email="petr@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
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

    with pytest.raises(ValueError, match="score is required"):
        await save_feedback(
            db_session,
            greeting_id=greeting.id,
            score=None,
            outcome="unknown",
            training_verdict="accepted",
        )


async def test_save_feedback_training_verdict_rejects_invalid(db_session):
    client = Client(
        first_name="Ольга",
        middle_name="Сергеевна",
        last_name="Ким",
        profession="hr",
        email="olga@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
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

    with pytest.raises(ValueError, match="training_verdict"):
        await save_feedback(
            db_session,
            greeting_id=greeting.id,
            score=3,
            outcome="unknown",
            training_verdict="maybe",
        )


async def test_save_feedback_accepts_training_verdict(db_session):
    client = Client(
        first_name="Дмитрий",
        middle_name="Олегович",
        last_name="Волков",
        profession="sales",
        email="dmitry@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
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

    fb = await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=4,
        outcome="unknown",
        notes="норм",
        training_verdict="accepted",
    )
    assert fb.training_verdict == "accepted"
    assert fb.score == 4

    fb2 = await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=2,
        outcome="unknown",
        training_verdict="rejected",
    )
    assert fb2.training_verdict == "rejected"


async def test_save_feedback_auto_sets_training_verdict_from_score(db_session):
    client = Client(
        first_name="Елена",
        middle_name="Сергеевна",
        last_name="АвтоВердикт",
        profession="finance",
        email="elena@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
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

    fb_ok = await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=4,
        outcome="unknown",
        notes="хорошо",
        training_verdict=None,
    )
    assert fb_ok.training_verdict == "accepted"

    fb_bad = await save_feedback(
        db_session,
        greeting_id=greeting.id,
        score=3,
        outcome="unknown",
        notes="так себе",
        training_verdict=None,
    )
    assert fb_bad.training_verdict == "rejected"
