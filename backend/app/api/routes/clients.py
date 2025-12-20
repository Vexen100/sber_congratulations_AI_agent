from __future__ import annotations

import datetime as dt
import random

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    # API endpoint: keep behavior simple (seed only if table is empty-ish).
    existing = (await session.execute(select(Client.id).limit(1))).first()
    if existing:
        return {"added": 0, "reason": "clients already exist"}
    return await seed_demo_clients(session, n=5, replace=False)


def _demo_pool() -> list[dict]:
    """A diverse pool to sample from. We always seed only a small subset for token safety."""
    return [
        {
            "first_name": "Наталья",
            "middle_name": "Олеговна",
            "last_name": "Морозова",
            "company_name": "ООО Безопасность+",
            "position": "Руководитель службы безопасности",
            "profession": "security",
            "segment": "vip",
        },
        {
            "first_name": "Алина",
            "middle_name": "Сергеевна",
            "last_name": "Громова",
            "company_name": "ООО Логистика-Профи",
            "position": "Операционный директор",
            "profession": "logistics",
            "segment": "loyal",
        },
        {
            "first_name": "Руслан",
            "middle_name": "Андреевич",
            "last_name": "Мельников",
            "company_name": "АО ПромИнжиниринг",
            "position": "Технический директор",
            "profession": "it",
            "segment": "standard",
        },
        {
            "first_name": "Ксения",
            "middle_name": "Павловна",
            "last_name": "Воронова",
            "company_name": "ООО Ритейл-Плюс",
            "position": "Коммерческий директор",
            "profession": "sales",
            "segment": "vip",
        },
        {
            "first_name": "Павел",
            "middle_name": "Игоревич",
            "last_name": "Сафронов",
            "company_name": "ЗАО ТехСтрой",
            "position": "Финансовый директор",
            "profession": "finance",
            "segment": "loyal",
        },
        {
            "first_name": "Мария",
            "middle_name": "Алексеевна",
            "last_name": "Кузнецова",
            "company_name": "ИП Кузнецова М.А.",
            "position": "Владелец",
            "profession": "management",
            "segment": "new",
        },
        {
            "first_name": "Екатерина",
            "middle_name": "Олеговна",
            "last_name": "Николаева",
            "company_name": "АО МедТех",
            "position": "Руководитель проектов",
            "profession": "medicine",
            "segment": "standard",
        },
        {
            "first_name": "Дмитрий",
            "middle_name": "Викторович",
            "last_name": "Орлов",
            "company_name": "ООО АгроПром",
            "position": "Директор по развитию",
            "profession": "marketing",
            "segment": "loyal",
        },
        {
            "first_name": "Анна",
            "middle_name": "Михайловна",
            "last_name": "Романова",
            "company_name": "ООО Альфа-Логистика",
            "position": "Генеральный директор",
            "profession": "management",
            "segment": "vip",
        },
        {
            "first_name": "Сергей",
            "middle_name": "Николаевич",
            "last_name": "Волков",
            "company_name": "ООО СеверЭнерго",
            "position": "Коммерческий директор",
            "profession": "sales",
            "segment": "standard",
        },
        {
            "first_name": "Ольга",
            "middle_name": "Ивановна",
            "last_name": "Фёдорова",
            "company_name": "АО ТрансЛайн",
            "position": "Директор по персоналу",
            "profession": "hr",
            "segment": "new",
        },
        {
            "first_name": "Илья",
            "middle_name": "Денисович",
            "last_name": "Захаров",
            "company_name": "ООО ФинСервис",
            "position": "Главный бухгалтер",
            "profession": "accounting",
            "segment": "standard",
        },
        {
            "first_name": "Никита",
            "middle_name": "Сергеевич",
            "last_name": "Смирнов",
            "company_name": "ООО ДевСтудио",
            "position": "CTO",
            "profession": "it",
            "segment": "standard",
        },
        {
            "first_name": "Людмила",
            "middle_name": "Петровна",
            "last_name": "Сергеева",
            "company_name": "ООО ТурбоМаркет",
            "position": "Директор по маркетингу",
            "profession": "marketing",
            "segment": "new",
        },
        {
            "first_name": "Артём",
            "middle_name": "Евгеньевич",
            "last_name": "Поляков",
            "company_name": "ООО СтройПроект",
            "position": "Руководитель финансов",
            "profession": "construction",
            "segment": "loyal",
        },
        {
            "first_name": "Ирина",
            "middle_name": "Владимировна",
            "last_name": "Соколова",
            "company_name": "ООО Альфа-Логистика",
            "position": "Генеральный директор",
            "profession": "logistics",
            "segment": "vip",
        },
    ]


async def seed_demo_clients(
    session: AsyncSession,
    *,
    n: int = 5,
    replace: bool = False,
    today: dt.date | None = None,
    rng_seed: int | None = None,
) -> dict:
    """Seed demo Clients.

    - Picks a RANDOM subset of N clients from a diverse pool.
    - Ensures their next birthday falls within the next lookahead window (today..today+lookahead_days),
      so events are always today or in the future (no "past" demo events).
    - If replace=True, clears runtime data and replaces all clients with a new random set.
    """
    today = today or dt.date.today()
    n = int(n)
    if n < 1:
        return {"added": 0, "reason": "n must be >= 1"}

    if replace:
        # Ensure a clean demo: remove runtime artifacts and replace clients.
        from app.services.reset_runtime import reset_runtime_data

        await reset_runtime_data(session)
        await session.execute(delete(Client))
        await session.commit()

    pool = _demo_pool()
    if n > len(pool):
        return {"added": 0, "reason": f"n too large (max {len(pool)})"}

    rng: random.Random = random.Random(rng_seed) if rng_seed is not None else random.SystemRandom()  # type: ignore[assignment]
    chosen = rng.sample(pool, k=n)

    # Demo showpiece: ensure at least one client has a profession with a professional holiday today.
    # (This helps demonstrate "не только день рождения".)
    if not any((row.get("profession") == "security") for row in chosen):
        spotlight = next((r for r in pool if r.get("profession") == "security"), None)
        if spotlight is not None:
            chosen[0] = spotlight

    # Put birthdays inside the lookahead window so generated Events are never in the past.
    lookahead_days = int(getattr(settings, "lookahead_days", 7))
    window = max(1, min(lookahead_days, 14))
    offsets = rng.sample(range(0, window), k=n)

    # Use a single commit (faster, fewer partial states).
    clients: list[Client] = []
    for i, (row, offset) in enumerate(zip(chosen, offsets, strict=True)):
        upcoming = today + dt.timedelta(days=int(offset))
        year = int(rng.choice(list(range(1980, 2002))))
        birth_date = dt.date(year, upcoming.month, upcoming.day)
        email = f"demo_client_{i+1}@example.com"
        clients.append(
            Client(
                first_name=row["first_name"],
                middle_name=row.get("middle_name"),
                last_name=row["last_name"],
                company_name=row["company_name"],
                position=row["position"],
                profession=row.get("profession"),
                segment=row["segment"],
                email=email,
                preferred_channel="email",
                birth_date=birth_date,
                last_interaction_summary="",
                is_demo=True,
            )
        )

    session.add_all(clients)
    await session.commit()
    return {"added": len(clients), "replaced": replace, "lookahead_days": lookahead_days}
