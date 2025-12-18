from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Delivery
from app.db.session import get_session

router = APIRouter(prefix="/deliveries")


@router.get("")
async def list_deliveries(session: AsyncSession = Depends(get_session)) -> list[dict]:
    deliveries = (
        (await session.execute(select(Delivery).order_by(Delivery.id.desc()))).scalars().all()
    )
    return [
        {
            "id": d.id,
            "greeting_id": d.greeting_id,
            "channel": d.channel,
            "recipient": d.recipient,
            "status": d.status,
            "provider_message": d.provider_message,
            "sent_at": d.sent_at,
            "idempotency_key": d.idempotency_key,
        }
        for d in deliveries
    ]
