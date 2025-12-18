from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.base import Base
from app.db.models import Holiday
from app.db.session import engine

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"


async def create_dirs() -> None:
    (DATA_DIR / "outbox").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "cards").mkdir(parents=True, exist_ok=True)


async def init_db(db_engine: AsyncEngine | None = None) -> None:
    db_engine = db_engine or engine
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_holidays_if_empty(session: AsyncSession) -> int:
    existing = (await session.execute(select(Holiday.id).limit(1))).first()
    if existing:
        return 0

    sample_path = RESOURCES_DIR / "holidays_ru_sample.json"
    if not sample_path.exists():
        return 0

    items = json.loads(sample_path.read_text(encoding="utf-8"))
    added = 0
    for item in items:
        # stored as ISO date string in resources
        date_str = item["date"]
        date_val = date_str
        try:
            from datetime import date as _date

            if isinstance(date_str, str):
                date_val = _date.fromisoformat(date_str)
        except Exception:
            date_val = date_str
        session.add(
            Holiday(
                date=date_val,
                title=item["title"],
                tags=item.get("tags", {}),
                is_business_relevant=bool(item.get("is_business_relevant", True)),
            )
        )
        added += 1
    await session.commit()
    return added
