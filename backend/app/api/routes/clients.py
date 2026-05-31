from __future__ import annotations

import datetime as dt
import random
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Client
from app.db.session import get_session
from app.schemas.clients import ClientCreate, ClientOut
from app.services.company_enrichment import (
    enrich_client_company_by_id,
    enrich_missing_clients,
)
from app.services.company_import import import_clients_from_company_csv

router = APIRouter(prefix="/clients")

_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s\-]{1,49}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PROFESSIONS = {
    "management",
    "finance",
    "accounting",
    "it",
    "hr",
    "marketing",
    "sales",
    "logistics",
    "construction",
    "medicine",
    "security",
}


def _validate_human_name(value: str | None, *, field: str) -> str:
    normalized = (value or "").strip()
    if not _NAME_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail=f"{field}: используйте 2-50 символов (буквы/пробел/дефис)",
        )
    return normalized


def _validate_email(value: str | None) -> str:
    normalized = (value or "").strip()
    if not _EMAIL_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="email: некорректный формат")
    lower = normalized.lower()
    if lower.endswith("@example.com") or lower.endswith(".invalid") or lower.endswith(".example"):
        raise HTTPException(
            status_code=400,
            detail="email: используйте реальный адрес (example.com запрещён)",
        )
    return normalized


@router.get("", response_model=list[ClientOut])
async def list_clients(session: AsyncSession = Depends(get_session)) -> list[Client]:
    return (await session.execute(select(Client).order_by(Client.id.desc()))).scalars().all()


@router.post("", response_model=ClientOut)
async def create_client(
    payload: ClientCreate, session: AsyncSession = Depends(get_session)
) -> Client:
    data = payload.model_dump()
    inn = re.sub(r"\D", "", data.get("inn") or "")
    if inn and len(inn) not in {10, 12}:
        raise HTTPException(status_code=400, detail="inn must contain 10 or 12 digits")

    first_name = _validate_human_name(data.get("first_name"), field="first_name")
    middle_name = _validate_human_name(data.get("middle_name"), field="middle_name")
    last_name = _validate_human_name(data.get("last_name"), field="last_name")
    profession = (data.get("profession") or "").strip().lower()
    if profession not in _PROFESSIONS:
        raise HTTPException(status_code=400, detail="profession: выберите значение из списка")

    preferred_channel = (data.get("preferred_channel") or "email").strip().lower()
    if preferred_channel not in {"email", "sms", "messenger"}:
        raise HTTPException(status_code=400, detail="preferred_channel: недопустимое значение")

    email = None
    if data.get("email"):
        email = _validate_email(data.get("email"))
    if preferred_channel == "email" and not email:
        raise HTTPException(status_code=400, detail="email: обязателен для preferred_channel=email")

    clients = (
        (await session.execute(select(Client).order_by(Client.created_at.asc(), Client.id.asc())))
        .scalars()
        .all()
    )
    if len(clients) >= 5:
        demo_client = next((client for client in clients if client.is_demo), None)
        if demo_client:
            await session.delete(demo_client)
            await session.commit()
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Лимит: уже 5 реальных клиентов. Удалите одного или используйте "
                    "Seed demo data."
                ),
            )

    data["inn"] = inn or None
    data["first_name"] = first_name
    data["middle_name"] = middle_name
    data["last_name"] = last_name
    data["profession"] = profession
    data["preferred_channel"] = preferred_channel
    data["email"] = email
    data["enrichment_status"] = data.get("enrichment_status") or (
        "pending" if inn else "not_requested"
    )
    data["company_name"] = (data.get("company_name") or "").strip() or None
    data["position"] = (data.get("position") or "").strip() or None
    data["phone"] = (data.get("phone") or "").strip() or None
    c = Client(**data)
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


@router.post("/enrich-missing")
async def enrich_all_pending(session: AsyncSession = Depends(get_session)) -> dict:
    return await enrich_missing_clients(session)


@router.post("/import-company-base")
async def import_company_base(session: AsyncSession = Depends(get_session)) -> dict:
    return await import_clients_from_company_csv(session)


@router.post("/{client_id}/enrich")
async def enrich_client(client_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    return await enrich_client_company_by_id(session, client_id=client_id)


def _demo_pool() -> list[dict]:
    """A diverse pool to sample from. We always seed only a small subset for token safety."""
    return [
        {
            "first_name": "Наталья",
            "middle_name": "Олеговна",
            "last_name": "Морозова",
            "company_name": "ООО Безопасность+",
            "inn": "7701122334",
            "position": "Руководитель службы безопасности",
            "profession": "security",
        },
        {
            "first_name": "Алина",
            "middle_name": "Сергеевна",
            "last_name": "Громова",
            "company_name": "ООО Логистика-Профи",
            "inn": "7802456789",
            "position": "Операционный директор",
            "profession": "logistics",
        },
        {
            "first_name": "Руслан",
            "middle_name": "Андреевич",
            "last_name": "Мельников",
            "company_name": "АО ПромИнжиниринг",
            "inn": "7723456781",
            "position": "Технический директор",
            "profession": "it",
        },
        {
            "first_name": "Ксения",
            "middle_name": "Павловна",
            "last_name": "Воронова",
            "company_name": "ООО Ритейл-Плюс",
            "inn": "7712450099",
            "position": "Коммерческий директор",
            "profession": "sales",
        },
        {
            "first_name": "Павел",
            "middle_name": "Игоревич",
            "last_name": "Сафронов",
            "company_name": "ЗАО ТехСтрой",
            "inn": "7812001122",
            "position": "Финансовый директор",
            "profession": "finance",
        },
        {
            "first_name": "Мария",
            "middle_name": "Алексеевна",
            "last_name": "Кузнецова",
            "company_name": "ИП Кузнецова М.А.",
            "inn": "7701987654",
            "position": "Владелец",
            "profession": "management",
        },
        {
            "first_name": "Екатерина",
            "middle_name": "Олеговна",
            "last_name": "Николаева",
            "company_name": "АО МедТех",
            "inn": "7733557799",
            "position": "Руководитель проектов",
            "profession": "medicine",
        },
        {
            "first_name": "Дмитрий",
            "middle_name": "Викторович",
            "last_name": "Орлов",
            "company_name": "ООО АгроПром",
            "inn": "7722884400",
            "position": "Директор по развитию",
            "profession": "marketing",
        },
        {
            "first_name": "Анна",
            "middle_name": "Михайловна",
            "last_name": "Романова",
            "company_name": "ООО Альфа-Логистика",
            "inn": "7811882201",
            "position": "Генеральный директор",
            "profession": "management",
        },
        {
            "first_name": "Сергей",
            "middle_name": "Николаевич",
            "last_name": "Волков",
            "company_name": "ООО СеверЭнерго",
            "inn": "7701228899",
            "position": "Коммерческий директор",
            "profession": "sales",
        },
        {
            "first_name": "Ольга",
            "middle_name": "Ивановна",
            "last_name": "Фёдорова",
            "company_name": "АО ТрансЛайн",
            "inn": "7813445500",
            "position": "Директор по персоналу",
            "profession": "hr",
        },
        {
            "first_name": "Илья",
            "middle_name": "Денисович",
            "last_name": "Захаров",
            "company_name": "ООО ФинСервис",
            "inn": "7701664400",
            "position": "Главный бухгалтер",
            "profession": "accounting",
        },
        {
            "first_name": "Никита",
            "middle_name": "Сергеевич",
            "last_name": "Смирнов",
            "company_name": "ООО ДевСтудио",
            "inn": "7801223300",
            "position": "CTO",
            "profession": "it",
        },
        {
            "first_name": "Людмила",
            "middle_name": "Петровна",
            "last_name": "Сергеева",
            "company_name": "ООО ТурбоМаркет",
            "inn": "7712334401",
            "position": "Директор по маркетингу",
            "profession": "marketing",
        },
        {
            "first_name": "Артём",
            "middle_name": "Евгеньевич",
            "last_name": "Поляков",
            "company_name": "ООО СтройПроект",
            "inn": "7714556677",
            "position": "Руководитель финансов",
            "profession": "construction",
        },
        {
            "first_name": "Ирина",
            "middle_name": "Владимировна",
            "last_name": "Соколова",
            "company_name": "ООО Альфа-Логистика",
            "inn": "7811882201",
            "position": "Генеральный директор",
            "profession": "logistics",
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

    Presentation-oriented behavior:
    - Randomly samples n clients from a fixed pool (diverse professions).
    - Sets birthdays to *today* so one agent run immediately demonstrates deliveries.
    - If replace=True, clears runtime data and replaces all clients with a new random set.
    """
    today = today or dt.date.today()
    n = int(n)
    if n < 1:
        return {"added": 0, "reason": "n must be >= 1"}

    if replace:
        # Ensure a clean demo: remove runtime artifacts and replace clients.
        from app.services.reset_runtime import reset_runtime_data

        await reset_runtime_data(session, clear_clients=True)

    pool = _demo_pool()
    if n > len(pool):
        return {"added": 0, "reason": f"n too large (max {len(pool)})"}

    rng: random.Random = random.Random(rng_seed) if rng_seed is not None else random.SystemRandom()  # type: ignore[assignment]
    chosen = rng.sample(pool, k=n)

    # Put birthdays on today so one demo run immediately sends a visible batch.
    lookahead_days = int(getattr(settings, "lookahead_days", 7))
    offsets = [0 for _ in range(n)]

    # Use a single commit (faster, fewer partial states).
    clients: list[Client] = []
    for i, (row, offset) in enumerate(zip(chosen, offsets, strict=True)):
        upcoming = today + dt.timedelta(days=int(offset))
        year = int(rng.choice(list(range(1980, 2002))))
        birth_date = dt.date(year, upcoming.month, upcoming.day)
        email = f"demo_client_{i + 1}@example.com"
        clients.append(
            Client(
                first_name=row["first_name"],
                middle_name=row.get("middle_name"),
                last_name=row["last_name"],
                company_name=row["company_name"],
                official_company_name=None,
                position=row["position"],
                profession=row.get("profession"),
                inn=row.get("inn"),
                email=email,
                preferred_channel="email",
                birth_date=birth_date,
                last_interaction_summary="",
                enrichment_status="pending" if row.get("inn") else "not_requested",
                is_demo=True,
            )
        )

    session.add_all(clients)
    await session.commit()
    return {
        "added": len(clients),
        "replaced": replace,
        "lookahead_days": lookahead_days,
    }
