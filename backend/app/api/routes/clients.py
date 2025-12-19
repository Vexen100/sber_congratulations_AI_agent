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
    # Moderate dataset for demos: diverse, but not too large (to avoid token burn).
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
            last_interaction_summary="",
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
            last_interaction_summary="",
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
            last_interaction_summary="",
        ),
        Client(
            first_name="Сергей",
            last_name="Волков",
            company_name="ООО СеверЭнерго",
            position="Коммерческий директор",
            segment="standard",
            email="sergey.volkov@example.com",
            preferred_channel="email",
            birth_date=dt.date(1985, 12, 21),
        ),
        Client(
            first_name="Екатерина",
            last_name="Николаева",
            company_name="АО МедТех",
            position="Руководитель проектов",
            segment="standard",
            email="ekaterina.nikolaeva@example.com",
            preferred_channel="email",
            birth_date=dt.date(1992, 12, 19),
        ),
        Client(
            first_name="Дмитрий",
            last_name="Орлов",
            company_name="ООО АгроПром",
            position="Директор по развитию",
            segment="loyal",
            email="dmitry.orlov@example.com",
            preferred_channel="email",
            birth_date=dt.date(1989, 12, 23),
        ),
        Client(
            first_name="Анна",
            last_name="Романова",
            company_name="ООО Ритейл-Плюс",
            position="Исполнительный директор",
            segment="vip",
            email="anna.romanova@example.com",
            preferred_channel="email",
            birth_date=dt.date(1987, 12, 24),
        ),
        Client(
            first_name="Илья",
            last_name="Захаров",
            company_name="ООО ФинСервис",
            position="Главный бухгалтер",
            segment="standard",
            email="ilya.zakharov@example.com",
            preferred_channel="email",
            birth_date=None,  # to reduce event volume
        ),
        Client(
            first_name="Ольга",
            last_name="Фёдорова",
            company_name="АО ТрансЛайн",
            position="Директор по персоналу",
            segment="new",
            email="olga.fedorova@example.com",
            preferred_channel="email",
            birth_date=None,
        ),
        Client(
            first_name="Никита",
            last_name="Смирнов",
            company_name="ООО ДевСтудио",
            position="CTO",
            segment="standard",
            email="nikita.smirnov@example.com",
            preferred_channel="email",
            birth_date=dt.date(1993, 12, 25),
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
