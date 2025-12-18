from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Greeting
from app.db.session import get_session
from app.schemas.greetings import GreetingOut

router = APIRouter(prefix="/greetings")


@router.get("", response_model=list[GreetingOut])
async def list_greetings(session: AsyncSession = Depends(get_session)) -> list[Greeting]:
    return (await session.execute(select(Greeting).order_by(Greeting.id.desc()))).scalars().all()
