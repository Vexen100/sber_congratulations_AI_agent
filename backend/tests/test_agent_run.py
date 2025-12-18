from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import Client, Delivery, Greeting


async def test_agent_generates_and_sends_for_birthday(db_session):
    today = dt.date.today()
    c = Client(
        first_name="Тест",
        last_name="Клиент",
        segment="standard",
        email="test@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
        company_name="Тест ООО",
        position="Директор",
        last_interaction_summary="обсуждали демо",
    )
    db_session.add(c)
    await db_session.commit()

    summary = await run_once(db_session, today=today, lookahead_days=1)
    assert summary.generated_greetings >= 1
    assert summary.sent_deliveries >= 1

    greetings = (await db_session.execute(select(Greeting))).scalars().all()
    deliveries = (await db_session.execute(select(Delivery))).scalars().all()
    assert len(greetings) >= 1
    assert len(deliveries) >= 1
