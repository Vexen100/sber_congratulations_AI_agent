from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import AgentRun, Client


async def test_agent_run_is_logged(db_session):
    today = dt.date.today()
    c = Client(
        first_name="Тест",
        last_name="Клиент",
        segment="standard",
        email="test@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
    )
    db_session.add(c)
    await db_session.commit()

    summary = await run_once(db_session, today=today, lookahead_days=1, triggered_by="test")
    assert summary.scanned_events >= 0

    runs = (await db_session.execute(select(AgentRun).order_by(AgentRun.id.desc()))).scalars().all()
    assert len(runs) >= 1
    r = runs[0]
    assert r.triggered_by == "test"
    assert r.finished_at is not None
    assert r.status in {"success", "partial", "error"}
    assert r.lookahead_days == 1
    assert r.scanned_events == summary.scanned_events
    assert r.generated_greetings == summary.generated_greetings
    assert r.sent_deliveries == summary.sent_deliveries
    assert r.skipped_existing == summary.skipped_existing
    assert r.errors == summary.errors
