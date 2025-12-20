from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.api.routes.clients import seed_demo_clients
from app.db.models import Client
from app.services.dates import next_occurrence


async def test_seed_demo_creates_random_five_with_upcoming_birthdays(db_session):
    today = dt.date(2025, 12, 19)
    res = await seed_demo_clients(db_session, n=5, replace=True, today=today, rng_seed=123)
    assert res["added"] == 5

    clients = (await db_session.execute(select(Client))).scalars().all()
    assert len(clients) == 5

    # Ensure all next birthdays are today or in the future, and within lookahead window.
    lookahead_days = int(res["lookahead_days"])
    end = today + dt.timedelta(days=lookahead_days)
    for c in clients:
        assert c.birth_date is not None
        assert c.is_demo is True
        assert (c.email or "").endswith("@example.com")
        assert (getattr(c, "middle_name", "") or "").strip() != ""
        assert (getattr(c, "profession", "") or "").strip() != ""
        occ = next_occurrence(c.birth_date.month, c.birth_date.day, today=today)
        assert today <= occ <= end


async def test_seed_demo_replace_replaces_clients(db_session):
    today = dt.date(2025, 12, 19)
    await seed_demo_clients(db_session, n=5, replace=True, today=today, rng_seed=1)
    first = (await db_session.execute(select(Client))).scalars().all()
    first_names = {(c.first_name, c.last_name) for c in first}

    await seed_demo_clients(db_session, n=5, replace=True, today=today, rng_seed=2)
    second = (await db_session.execute(select(Client))).scalars().all()
    second_names = {(c.first_name, c.last_name) for c in second}

    assert len(first) == 5
    assert len(second) == 5
    assert first_names != second_names
