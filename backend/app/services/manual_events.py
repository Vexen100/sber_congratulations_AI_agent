from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Event


def _campaign_payload_for_client(client: Client, *, fallback_title: str) -> tuple[str, dict]:
    prof = (client.profession or "management").strip().lower()
    tone_hint = "warm"

    focus_map: dict[str, tuple[str, str]] = {
        "finance": ("finance", "Желаем финансовой устойчивости и уверенного роста"),
        "accounting": ("finance", "Желаем точных решений и устойчивого развития"),
        "logistics": ("operations", "Желаем устойчивых процессов и новых возможностей"),
        "sales": ("sales", "Желаем сильных продаж и новых клиентов"),
        "it": ("technology", "Желаем технологического роста и сильных решений"),
        "hr": ("team", "Желаем сильной команды и успешного развития"),
        "marketing": ("growth", "Желаем ярких идей и устойчивого роста"),
        "construction": (
            "operations",
            "Желаем надёжных проектов и стабильного развития",
        ),
        "medicine": ("care", "Желаем уверенного развития и значимых результатов"),
        "security": ("stability", "Желаем надёжности и уверенного развития"),
        "management": ("leadership", "Желаем уверенного развития бизнеса"),
    }
    focus_hint, suggested_title = focus_map.get(
        prof, ("growth", "Желаем новых успехов в развитии бизнеса")
    )

    title = fallback_title.strip()
    if not title or title.lower() == "персональное деловое поздравление":
        title = suggested_title

    metadata = {
        "source": "web-demo-campaign",
        "manual_kind": "business_touchpoint",
        "focus_hint": focus_hint,
        "tone_hint": tone_hint,
        "profession_snapshot": prof,
    }
    return title, metadata


async def create_manual_event_record(
    session: AsyncSession,
    *,
    client_id: int | None,
    event_date: dt.date,
    title: str,
    metadata: dict | None = None,
) -> Event:
    event = Event(
        client_id=client_id,
        event_type="manual",
        event_date=event_date,
        title=title.strip(),
        details=metadata or {},
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def seed_manual_campaign_for_real_clients(
    session: AsyncSession,
    *,
    event_date: dt.date,
    title: str,
    limit: int = 5,
) -> dict:
    clients = (
        (
            await session.execute(
                select(Client)
                .where(Client.is_demo.is_(False))
                .order_by(Client.id.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    created = 0
    duplicates = 0
    for client in clients:
        event_title, metadata = _campaign_payload_for_client(client, fallback_title=title)
        event = Event(
            client_id=client.id,
            event_type="manual",
            event_date=event_date,
            title=event_title,
            details=metadata,
        )
        session.add(event)
        try:
            await session.commit()
            created += 1
        except IntegrityError:
            await session.rollback()
            duplicates += 1

    return {
        "selected_clients": len(clients),
        "created": created,
        "duplicates": duplicates,
        "title": title.strip(),
        "event_date": event_date.isoformat(),
    }
