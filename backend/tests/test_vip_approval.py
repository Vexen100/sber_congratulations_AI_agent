from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import Client, Delivery, Greeting
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
