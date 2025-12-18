from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Greeting
from app.services.sender import send_greeting_file


async def approve_greeting(
    session: AsyncSession,
    *,
    greeting_id: int,
    approved_by: str = "operator",
    review_comment: str | None = None,
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

    # Send once approved
    recipient = "unknown"
    if g.client_id is not None:
        c = (await session.execute(select(Client).where(Client.id == g.client_id))).scalar_one_or_none()
        if c:
            recipient = c.email or c.phone or f"client:{c.id}"

    delivery = await send_greeting_file(session, greeting=g, recipient=recipient)
    if delivery.status == "sent":
        g.status = "sent"
        await session.commit()
        return {"status": "sent", "delivery_id": delivery.id}

    g.status = "error"
    await session.commit()
    return {"status": "error"}


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


