from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Event, Holiday
from app.services.dates import daterange_inclusive, next_occurrence


async def ensure_upcoming_events(
    session: AsyncSession,
    *,
    today: dt.date,
    lookahead_days: int,
) -> int:
    """Create missing Events in DB for upcoming birthdays and holidays.

    Idempotency is achieved by unique constraint on events.
    Returns number of newly created events (best-effort).
    """

    end = today + dt.timedelta(days=lookahead_days)
    window_days = daterange_inclusive(today, end)

    created = 0

    # Birthdays (per client)
    client_rows = (await session.execute(select(Client.id, Client.birth_date))).all()
    client_ids: list[int] = []
    for client_id, birth_date in client_rows:
        client_ids.append(client_id)
        if not birth_date:
            continue
        occ = next_occurrence(birth_date.month, birth_date.day, today=today)
        if occ not in window_days:
            continue
        title = "День рождения"
        ev = Event(
            client_id=client_id,
            event_type="birthday",
            event_date=occ,
            title=title,
            details={},
        )
        session.add(ev)
        try:
            await session.commit()
            created += 1
        except IntegrityError:
            await session.rollback()

    # Holidays (global → per client for MVP)
    holiday_rows = (
        await session.execute(
            select(Holiday.date, Holiday.title, Holiday.tags)
            .where(Holiday.date >= today)
            .where(Holiday.date <= end)
        )
    ).all()
    for h_date, h_title, h_tags in holiday_rows:
        for client_id in client_ids:
            title = h_title
            ev = Event(
                client_id=client_id,
                event_type="holiday",
                event_date=h_date,
                title=title,
                details={"holiday_tags": h_tags},
            )
            session.add(ev)
            try:
                await session.commit()
                created += 1
            except IntegrityError:
                await session.rollback()

    return created
