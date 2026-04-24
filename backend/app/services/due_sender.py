from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Event, Greeting
from app.services.sender import send_greeting

log = logging.getLogger(__name__)

_SENDABLE_STATUSES = {"generated", "approved"}
_CONSIDER_STATUSES = {"generated", "approved"}


def _event_priority(ev: Event) -> int:
    """Lower is higher priority."""
    et = (getattr(ev, "event_type", "") or "").lower()
    if et == "birthday":
        return 0
    if et == "manual":
        return 1
    if et == "holiday":
        tags = (getattr(ev, "details", None) or {}).get("holiday_tags", {}) or {}
        if (tags.get("type") or "").lower() == "professional":
            return 2
        return 3
    return 9


def _is_sendable_today(*, g: Greeting, c: Client) -> bool:  # noqa: ARG001
    """Whether greeting is eligible to be sent (ignoring date, which is handled by query)."""
    return g.status in _SENDABLE_STATUSES


async def send_due_greetings(
    session: AsyncSession,
    *,
    today: dt.date,
) -> dict:
    """Send greetings that are due today.

    Principles:
    - Greetings may be generated ahead of time (lookahead window).
    - Sends ONLY on the day of the event (Event.event_date == today).
    - One sendable greeting per client per day (priority: birthday > manual > holiday).

    Returns counts for reporting/UI.
    """
    sent = 0
    skipped = 0
    errors = 0
    suppressed = 0

    # Select due greetings with their event + client.
    stmt = (
        select(Greeting, Event, Client)
        .join(Event, Event.id == Greeting.event_id)
        .join(Client, Client.id == Greeting.client_id)
        .where(Greeting.status.in_(_CONSIDER_STATUSES))
    )
    stmt = stmt.where(Event.event_date == today)
    rows = (await session.execute(stmt)).all()

    # Group by client so we can enforce "1 message per client per day" with priority.
    by_client: dict[int, list[tuple[Greeting, Event, Client]]] = {}
    for g, ev, c in rows:
        by_client.setdefault(int(c.id), []).append((g, ev, c))

    for _client_id, items in by_client.items():
        # All items share the same client
        c = items[0][2]
        birthday_items = [t for t in items if (t[1].event_type or "").lower() == "birthday"]

        # Choose the winner: prefer sendable birthday; else best sendable by priority.
        winner: tuple[Greeting, Event, Client] | None = None
        if birthday_items:
            candidate = sorted(birthday_items, key=lambda t: _event_priority(t[1]))[0]
            if _is_sendable_today(g=candidate[0], c=c):
                winner = candidate
        if winner is None:
            sendable = [t for t in items if _is_sendable_today(g=t[0], c=c)]
            if sendable:
                winner = sorted(sendable, key=lambda t: (_event_priority(t[1]), t[0].id))[0]

        # Suppress other sendable greetings (so we never send multiple messages in one day).
        for g, _ev, _c in items:
            if winner is not None and g.id == winner[0].id:
                continue
            if _is_sendable_today(g=g, c=c):
                g.status = "skipped"
                suppressed += 1
        if suppressed:
            await session.commit()

        if winner is None:
            continue

        g, ev, _c = winner

        try:
            recipient = c.email or c.phone or ""
            delivery = await send_greeting(session, greeting=g, recipient=recipient, client=c)
            if delivery.status == "sent":
                g.status = "sent"
                await session.commit()
                sent += 1
            elif delivery.status == "skipped":
                # Safety outcome: don't retry automatically forever in regular mode.
                g.status = "skipped"
                await session.commit()
                skipped += 1
            else:
                g.status = "error"
                await session.commit()
                errors += 1
        except Exception as e:
            log.exception(
                "due send failed for greeting=%s event=%s client=%s: %s",
                getattr(g, "id", None),
                getattr(ev, "id", None),
                getattr(c, "id", None),
                e,
            )
            try:
                g.status = "error"
                await session.commit()
            except Exception:
                await session.rollback()
            errors += 1

    return {
        "sent": sent,
        "skipped": skipped,
        "suppressed": suppressed,
        "errors": errors,
        "due_total": len(rows),
        "clients_total": len(by_client),
    }
