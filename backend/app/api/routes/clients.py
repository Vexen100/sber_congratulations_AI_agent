from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client
from app.db.session import get_session
from app.schemas.clients import ClientCreate, ClientOut

router = APIRouter(prefix="/clients")


@router.get("", response_model=list[ClientOut])
async def list_clients(session: AsyncSession = Depends(get_session)) -> list[Client]:
    return (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()


@router.post("", response_model=ClientOut)
async def create_client(
    payload: ClientCreate, session: AsyncSession = Depends(get_session)
) -> Client:
    c = Client(**payload.model_dump())
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


@router.post("/seed-demo")
async def seed_demo(session: AsyncSession = Depends(get_session)) -> dict:
    demo = [
        Client(
            first_name="Ирина",
            last_name="Соколова",
            company_name="ООО Альфа-Логистика",
            position="Генеральный директор",
            segment="vip",
            email="irina.sokolova@example.com",
            preferred_channel="email",
            birth_date=dt.date(1988, 12, 18),
            last_interaction_summary="обсуждали условия РКО и зарплатный проект",
        ),
        Client(
            first_name="Артём",
            last_name="Поляков",
            company_name="ЗАО ТехСтрой",
            position="Финансовый директор",
            segment="loyal",
            email="artem.polyakov@example.com",
            preferred_channel="email",
            birth_date=dt.date(1991, 12, 20),
            last_interaction_summary="планировали лимиты по кредитной линии",
        ),
        Client(
            first_name="Мария",
            last_name="Кузнецова",
            company_name="ИП Кузнецова М.А.",
            position="Владелец",
            segment="new",
            email="maria.kuznetsova@example.com",
            preferred_channel="email",
            birth_date=dt.date(1996, 12, 22),
            last_interaction_summary="первичное подключение эквайринга",
        ),
    ]
    added = 0
    for c in demo:
        session.add(c)
        try:
            await session.commit()
            added += 1
        except Exception:
            await session.rollback()
    return {"added": added}
