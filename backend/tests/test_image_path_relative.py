from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.core.config import settings
from app.db.models import Client, Greeting


async def test_greeting_image_path_is_relative(db_session, tmp_path, monkeypatch):
    # Force pillow mode to avoid external calls.
    monkeypatch.setattr(settings, "image_mode", "pillow")
    # Ensure cards directory exists under tmp data path if needed.
    today = dt.date.today()
    c = Client(
        first_name="Test",
        last_name="User",
        segment="standard",
        email="test@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
    )
    db_session.add(c)
    await db_session.commit()

    summary = await run_once(db_session, today=today, lookahead_days=1, triggered_by="test")
    assert summary.generated_greetings >= 1

    g = (await db_session.execute(select(Greeting).order_by(Greeting.id.desc()))).scalars().first()
    assert g is not None
    assert g.image_path
    assert g.image_path.startswith("cards/")
