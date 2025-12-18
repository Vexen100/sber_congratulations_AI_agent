from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.init_db import create_dirs, init_db
from app.db.session import create_engine


@pytest.fixture()
async def db_session(tmp_path) -> AsyncSession:
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_engine(url)
    await create_dirs()
    await init_db(engine)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
def set_outbox_tmp(tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OUTBOX_DIR", str(outbox))
    return outbox
