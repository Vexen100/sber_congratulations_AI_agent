from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import AgentRun, Client, Delivery, Event, Greeting, Holiday
from app.services.reset_runtime import reset_runtime_data


async def test_reset_runtime_keeps_clients_and_holidays(db_session, tmp_path, monkeypatch):
    today = dt.date.today()
    db_session.add(
        Client(
            first_name="A",
            last_name="B",
            segment="standard",
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
