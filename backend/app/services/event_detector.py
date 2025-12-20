from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Client, Event, Holiday
from app.services.dates import daterange_inclusive, next_occurrence


def _builtin_holidays_in_window(*, today: dt.date, end: dt.date) -> list[tuple[dt.date, str, dict]]:
    """Recurring holidays (month/day based), generated dynamically for the current/next year."""
    rules: list[tuple[int, int, str, dict]] = [
        (1, 1, "Новый год", {"type": "holiday", "tone_hint": "warm", "source": "builtin"}),
        (2, 23, "23 Февраля", {"type": "holiday", "tone_hint": "official", "source": "builtin"}),
        (3, 8, "8 Марта", {"type": "holiday", "tone_hint": "warm", "source": "builtin"}),
        (5, 1, "1 Мая", {"type": "holiday", "tone_hint": "warm", "source": "builtin"}),
        (5, 9, "9 Мая", {"type": "holiday", "tone_hint": "official", "source": "builtin"}),
        (6, 12, "День России", {"type": "holiday", "tone_hint": "official", "source": "builtin"}),
        (
            11,
            4,
            "День народного единства",
            {"type": "holiday", "tone_hint": "official", "source": "builtin"},
        ),
        (
            12,
            31,
            "С наступающим Новым годом!",
            {"type": "holiday", "tone_hint": "warm", "source": "builtin"},
        ),
    ]

    years = {today.year, end.year}
    out: list[tuple[dt.date, str, dict]] = []
    for y in sorted(years):
        for m, d, title, tags in rules:
            try:
                date_val = dt.date(y, m, d)
            except ValueError:
                continue
            if today <= date_val <= end:
                out.append((date_val, title, tags))
    return out


def _programmer_day(year: int) -> dt.date:
    """256th day of the year (Programmer's Day)."""
    return dt.date(year, 1, 1) + dt.timedelta(days=255)


def _professional_holidays_for_client(
    *, profession: str, today: dt.date, end: dt.date
) -> list[tuple[dt.date, str, dict]]:
    prof = (profession or "").strip().lower()
    if not prof:
        return []

    # Fixed professional holidays (simple MVP set).
    fixed: dict[str, tuple[int, int, str, str]] = {
        "accounting": (11, 21, "День бухгалтера", "official"),
        "it": (0, 0, "День программиста", "warm"),  # computed via 256th day
        "hr": (5, 24, "День кадровика", "official"),
        "marketing": (10, 25, "День маркетолога", "warm"),
        "sales": (7, 23, "День работника торговли", "warm"),
        "logistics": (11, 28, "День логиста", "official"),
        "construction": (8, 11, "День строителя", "official"),
        "medicine": (6, 16, "День медицинского работника", "warm"),
        "finance": (9, 8, "День финансиста", "official"),
        "management": (9, 27, "День руководителя", "official"),
        # Demo-friendly: Dec 20 (today for the current workshop date)
        "security": (12, 20, "День специалиста по безопасности", "official"),
    }
    if prof not in fixed:
        return []

    m, d, title, tone_hint = fixed[prof]

    years = {today.year, end.year}
    out: list[tuple[dt.date, str, dict]] = []
    for y in sorted(years):
        if prof == "it":
            date_val = _programmer_day(y)
        else:
            try:
                date_val = dt.date(y, m, d)
            except ValueError:
                continue
        if today <= date_val <= end:
            out.append(
                (
                    date_val,
                    title,
                    {
                        "type": "professional",
                        "profession": prof,
                        "tone_hint": tone_hint,
                        "source": "builtin",
                    },
                )
            )
    return out


async def ensure_upcoming_events(
    session: AsyncSession,
    *,
    today: dt.date,
    lookahead_days: int,
    max_holiday_recipients: int | None = None,
) -> int:
    """Create missing Events in DB for upcoming birthdays and holidays.

    Idempotency is achieved by unique constraint on events.
    Returns number of newly created events (best-effort).
    """

    end = today + dt.timedelta(days=lookahead_days)
    window_days = daterange_inclusive(today, end)

    created = 0
    max_holiday_recipients = (
        int(max_holiday_recipients)
        if max_holiday_recipients is not None
        else int(settings.max_holiday_recipients)
    )

    # Birthdays (per client)
    client_rows = (
        await session.execute(select(Client.id, Client.birth_date, Client.profession))
    ).all()
    client_ids: list[int] = []
    prof_by_client: dict[int, str] = {}
    for client_id, birth_date, profession in client_rows:
        client_ids.append(client_id)
        if profession:
            prof_by_client[int(client_id)] = str(profession)
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
        for client_id in client_ids[:max_holiday_recipients]:
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

    # Built-in recurring holidays (month/day), so the product can поздравлять не только с ДР
    for h_date, h_title, h_tags in _builtin_holidays_in_window(today=today, end=end):
        for client_id in client_ids[:max_holiday_recipients]:
            ev = Event(
                client_id=client_id,
                event_type="holiday",
                event_date=h_date,
                title=h_title,
                details={"holiday_tags": h_tags},
            )
            session.add(ev)
            try:
                await session.commit()
                created += 1
            except IntegrityError:
                await session.rollback()

    # Professional holidays (per client)
    for client_id, profession in prof_by_client.items():
        for h_date, h_title, h_tags in _professional_holidays_for_client(
            profession=profession, today=today, end=end
        ):
            ev = Event(
                client_id=client_id,
                event_type="holiday",
                event_date=h_date,
                title=h_title,
                details={"holiday_tags": h_tags},
            )
            session.add(ev)
            try:
                await session.commit()
                created += 1
            except IntegrityError:
                await session.rollback()

    return created
