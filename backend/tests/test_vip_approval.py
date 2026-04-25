from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import Client, Delivery, Event, Greeting
from app.services.due_sender import send_due_greetings


async def test_run_once_generates_and_sends_on_event_day_without_manual_approval(
    db_session, monkeypatch, tmp_path
):
    """Birthday today: agent creates a sendable greeting; due sender runs in same pass (no approve step)."""
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    monkeypatch.setattr(settings, "image_mode", "pillow")

    today = dt.date.today()
    c = Client(
        first_name="Клиент",
        middle_name="Тестович",
        last_name="ДеньРождения",
        profession="management",
        email="vip@mycompany.test",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
        is_demo=False,
    )
    db_session.add(c)
    await db_session.commit()

    summary = await run_once(db_session, today=today, lookahead_days=1)
    assert summary.generated_greetings >= 1
    assert summary.sent_deliveries >= 1

    greeting = (
        (await db_session.execute(select(Greeting).order_by(Greeting.id.desc()))).scalars().first()
    )
    assert greeting is not None
    assert greeting.status == "sent"


async def test_smtp_mode_demo_client_sends_via_file_outbox(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"), raising=False)
    monkeypatch.setattr(settings, "image_mode", "pillow", raising=False)

    today = dt.date.today()
    c = Client(
        first_name="Демо",
        middle_name="Тестович",
        last_name="Клиент",
        profession="management",
        email="demo.vip@gmail.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id,
        event_type="manual",
        event_date=today,
        title="Тест",
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
    await db_session.refresh(g)
    assert g.status == "sent"

    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(deliveries) == 1
    assert deliveries[0].status == "sent"
    assert deliveries[0].channel == "file"


async def test_send_due_in_smtp_mode_allowlist_empty_skips_not_error(db_session, monkeypatch):
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", False, raising=False)
    monkeypatch.setattr(settings, "smtp_allowlist_domains", "", raising=False)

    today = dt.date.today()
    c = Client(
        first_name="Реальный",
        middle_name="Тестович",
        last_name="Клиент",
        profession="management",
        email="real.vip@mycompany.test",
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
        title="Тест",
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
    assert res["errors"] == 0
    await db_session.refresh(g)
    assert g.status == "skipped"
