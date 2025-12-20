from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import Client, Delivery, Event, Greeting
from app.services.approval import approve_greeting


async def test_vip_requires_approval_and_sends_after_approve(db_session, monkeypatch, tmp_path):
    # Keep tests hermetic: write outbox to a temp folder and avoid external image providers.
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"))
    monkeypatch.setattr(settings, "image_mode", "pillow")

    today = dt.date.today()
    c = Client(
        first_name="Вип",
        last_name="Клиент",
        segment="vip",
        email="vip@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
    )
    db_session.add(c)
    await db_session.commit()

    summary = await run_once(db_session, today=today, lookahead_days=1)
    assert summary.generated_greetings >= 1
    assert summary.sent_deliveries == 0

    greeting = (
        (await db_session.execute(select(Greeting).order_by(Greeting.id.desc()))).scalars().first()
    )
    assert greeting is not None
    assert greeting.status == "needs_approval"

    deliveries_before = (await db_session.execute(select(Delivery))).scalars().all()
    assert deliveries_before == []

    res = await approve_greeting(db_session, greeting_id=greeting.id, approved_by="test")
    assert res["status"] == "sent"

    await db_session.refresh(greeting)
    assert greeting.status == "sent"

    deliveries_after = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(deliveries_after) == 1


async def test_vip_demo_client_in_smtp_mode_falls_back_to_file_and_is_sent(
    db_session, monkeypatch, tmp_path
):
    # SMTP enabled globally, but demo clients must never get real emails.
    # We still want the VIP approve demo flow to "send" (to outbox files).
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"), raising=False)
    monkeypatch.setattr(settings, "image_mode", "pillow", raising=False)

    today = dt.date.today()
    c = Client(
        first_name="Демо",
        last_name="VIP",
        segment="vip",
        email="demo.vip@gmail.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
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
        status="needs_approval",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    res = await approve_greeting(db_session, greeting_id=g.id, approved_by="test")
    assert res["status"] == "sent"
    await db_session.refresh(g)
    assert g.status == "sent"

    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(deliveries) == 1
    assert deliveries[0].status == "sent"
    assert deliveries[0].channel == "file"


async def test_vip_approve_in_smtp_mode_skipped_is_not_error(db_session, monkeypatch):
    # If SMTP safety blocks sending (e.g. allowlist empty), approval should not turn into "error".
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", False, raising=False)
    monkeypatch.setattr(settings, "smtp_allowlist_domains", "", raising=False)

    today = dt.date.today()
    c = Client(
        first_name="Реальный",
        last_name="VIP",
        segment="vip",
        email="real.vip@mycompany.test",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
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
        status="needs_approval",
    )
    db_session.add(g)
    await db_session.commit()
    await db_session.refresh(g)

    res = await approve_greeting(db_session, greeting_id=g.id, approved_by="test")
    assert res["status"] == "skipped"
    await db_session.refresh(g)
    assert g.status == "skipped"
