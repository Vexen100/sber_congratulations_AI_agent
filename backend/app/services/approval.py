from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Event, Greeting
from app.services.sender import send_greeting


async def approve_greeting(
    session: AsyncSession,
    *,
    greeting_id: int,
    approved_by: str = "operator",
    review_comment: str | None = None,
    today: dt.date | None = None,
) -> dict:
    """Approve a greeting and send it (MVP sender).

    Returns a small summary dict for UI.
    """
    g = (await session.execute(select(Greeting).where(Greeting.id == greeting_id))).scalar_one()
    if g.status not in {"needs_approval", "generated"}:
        return {"status": "ignored", "reason": f"cannot approve from status={g.status}"}

    g.status = "approved"
    g.approved_at = dt.datetime.now(dt.timezone.utc)
    g.approved_by = approved_by
    if review_comment:
        g.review_comment = review_comment
    await session.commit()
    await session.refresh(g)

    today = today or dt.date.today()

    # Find client/recipient
    c = None
    recipient = "unknown"
    if g.client_id is not None:
        c = (
            await session.execute(select(Client).where(Client.id == g.client_id))
        ).scalar_one_or_none()
        if c:
            recipient = c.email or c.phone or f"client:{c.id}"

    # Do NOT send earlier than the event date. We generate/approve ahead of time, but deliver on due day.
    ev = (await session.execute(select(Event).where(Event.id == g.event_id))).scalar_one_or_none()
    if ev is not None and ev.event_date != today:
        return {
            "status": "approved",
            "reason": "scheduled",
            "scheduled_for": ev.event_date.isoformat(),
        }

    delivery = await send_greeting(
        session, greeting=g, recipient=recipient, client=c if g.client_id else None
    )
    if delivery.status == "sent":
        g.status = "sent"
        await session.commit()
        return {"status": "sent", "delivery_id": delivery.id}

    # "skipped" is a deliberate safety outcome (demo client, allowlist, test recipient, etc).
    # Do NOT mark the greeting as "error" in this case.
    if delivery.status == "skipped":
        g.status = "skipped"
        await session.commit()
        return {
            "status": "skipped",
            "delivery_id": delivery.id,
            "reason": delivery.provider_message,
        }

    g.status = "error"
    await session.commit()
    return {"status": "error", "reason": delivery.provider_message}


async def reject_greeting(
    session: AsyncSession,
    *,
    greeting_id: int,
    rejected_by: str = "operator",
    review_comment: str | None = None,
) -> dict:
    g = (await session.execute(select(Greeting).where(Greeting.id == greeting_id))).scalar_one()
    if g.status not in {"needs_approval", "generated"}:
        return {"status": "ignored", "reason": f"cannot reject from status={g.status}"}

    g.status = "rejected"
    g.approved_at = dt.datetime.now(dt.timezone.utc)
    g.approved_by = rejected_by
    if review_comment:
        g.review_comment = review_comment
    await session.commit()
    return {"status": "rejected"}
