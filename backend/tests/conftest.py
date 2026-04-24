from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.init_db import create_dirs, init_db  # noqa: E402
from app.db.session import create_engine  # noqa: E402


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch, tmp_path):
    """Make tests hermetic regardless of developer's local .env.

    Many dev setups enable real providers (SMTP/GigaChat). Tests must never depend
    on those external services; force safe offline modes by default.
    """
    outbox = tmp_path / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)

    # Offline, deterministic defaults for the test suite.
    monkeypatch.setattr(settings, "send_mode", "file", raising=False)
    monkeypatch.setattr(settings, "llm_mode", "template", raising=False)
    monkeypatch.setattr(settings, "image_mode", "pillow", raising=False)
    monkeypatch.setattr(settings, "outbox_dir", str(outbox), raising=False)
    monkeypatch.setattr(settings, "company_enrichment_provider", "demo", raising=False)
    monkeypatch.setattr(settings, "company_import_csv_path", "", raising=False)

    # Avoid accidental external provider usage through leaked credentials.
    monkeypatch.setattr(settings, "openai_api_key", None, raising=False)
    monkeypatch.setattr(settings, "gigachat_credentials", None, raising=False)
    monkeypatch.setattr(settings, "dadata_api_key", None, raising=False)

    return outbox


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
