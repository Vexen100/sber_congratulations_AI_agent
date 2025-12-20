from __future__ import annotations

import datetime as dt

from app.core.config import settings
from app.db.models import Client, Event, Greeting
from app.services.sender import send_greeting


async def test_smtp_blocks_demo_client_even_if_email_looks_real(db_session, monkeypatch, tmp_path):
    # Force SMTP mode
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)
    # Keep tests hermetic: file fallback should write into a temp outbox.
    # (SMTP is never used for demo clients.)
    monkeypatch.setattr(settings, "outbox_dir", str(tmp_path / "outbox"), raising=False)

    c = Client(
        first_name="Демо",
        last_name="Клиент",
        segment="standard",
        email="real.user@real-domain.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id, event_type="manual", event_date=dt.date.today(), title="Тест", details={}
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

    d = await send_greeting(db_session, greeting=g, recipient=c.email or "", client=c)
    # Demo clients must never be sent via SMTP. When SEND_MODE=smtp, we fall back to file outbox.
    assert d.status == "sent"
    assert d.channel == "file"
    assert (d.provider_message or "").startswith("written:")


async def test_smtp_blocks_example_dot_com_recipients(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)

    c = Client(
        first_name="Тест",
        last_name="Клиент",
        segment="standard",
        email="demo_client_1@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=False,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id, event_type="manual", event_date=dt.date.today(), title="Тест", details={}
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

    d = await send_greeting(db_session, greeting=g, recipient=c.email or "", client=c)
    assert d.status == "skipped"
    assert d.provider_message == "blocked:test-recipient"


async def test_smtp_blocks_when_allowlist_empty_by_default(db_session, monkeypatch):
    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.local", raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", False, raising=False)
    monkeypatch.setattr(settings, "smtp_allowlist_domains", "", raising=False)

    c = Client(
        first_name="Реальный",
        last_name="Клиент",
        segment="standard",
        email="real.user@mycompany.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=False,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id, event_type="manual", event_date=dt.date.today(), title="Тест", details={}
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

    d = await send_greeting(db_session, greeting=g, recipient=c.email or "", client=c)
    assert d.status == "skipped"
    assert d.provider_message == "blocked:allowlist-empty"
