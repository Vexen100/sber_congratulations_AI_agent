from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Delivery, Greeting


def _idempotency_key(*, greeting_id: int, channel: str, recipient: str) -> str:
    raw = f"{greeting_id}:{channel}:{recipient}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:40]


async def send_greeting_file(
    session: AsyncSession,
    *,
    greeting: Greeting,
    recipient: str,
    outbox_dir: str | Path | None = None,
) -> Delivery:
    """MVP sender: writes a .txt message into outbox directory.

    Idempotent by (greeting_id, channel, recipient).
    """
    channel = "file"
    out_dir = Path(outbox_dir or settings.outbox_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    key = _idempotency_key(greeting_id=greeting.id, channel=channel, recipient=recipient)
    existing = (
        await session.execute(select(Delivery).where(Delivery.idempotency_key == key))
    ).scalar_one_or_none()
    if existing:
        return existing

    filename = f"delivery_{greeting.id}_{key}.txt"
    path = out_dir / filename
    payload = "\n".join(
        [
            f"TO: {recipient}",
            f"SUBJECT: {greeting.subject}",
            "",
            greeting.body,
            "",
            f"IMAGE: {greeting.image_path or ''}",
        ]
    )
    path.write_text(payload, encoding="utf-8")

    delivery = Delivery(
        greeting_id=greeting.id,
        channel=channel,
        recipient=recipient,
        status="sent",
        provider_message=f"written:{path.name}",
        sent_at=dt.datetime.now(dt.timezone.utc),
        idempotency_key=key,
    )
    session.add(delivery)
    await session.commit()
    return delivery
