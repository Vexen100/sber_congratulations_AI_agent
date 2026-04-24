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
        # Lightweight SQLite migration for existing local demo DBs (no Alembic in MVP).
        await _migrate_sqlite(conn)


async def _migrate_sqlite(conn) -> None:
    """Best-effort migration for SQLite demo DB.

    Adds new columns when upgrading MVP without requiring users to delete app.db.
    """
    try:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        # 1) greetings table migrations
        res = await conn.exec_driver_sql("PRAGMA table_info(greetings)")
        rows = res.fetchall()
        existing = {r[1] for r in rows}
        alter_stmts: list[str] = []
        if "approved_at" not in existing:
            alter_stmts.append("ALTER TABLE greetings ADD COLUMN approved_at DATETIME")
        if "approved_by" not in existing:
            alter_stmts.append("ALTER TABLE greetings ADD COLUMN approved_by VARCHAR(120)")
        if "review_comment" not in existing:
            alter_stmts.append("ALTER TABLE greetings ADD COLUMN review_comment TEXT")
        if "agent_run_id" not in existing:
            alter_stmts.append("ALTER TABLE greetings ADD COLUMN agent_run_id INTEGER")
        for stmt in alter_stmts:
            await conn.exec_driver_sql(stmt)

        # 2) clients table migrations
        res = await conn.exec_driver_sql("PRAGMA table_info(clients)")
        rows = res.fetchall()
        existing = {r[1] for r in rows}
        alter_stmts = []
        if "is_demo" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN is_demo BOOLEAN DEFAULT 0")
        if "middle_name" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN middle_name VARCHAR(100)")
        if "profession" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN profession VARCHAR(80)")
        if "official_company_name" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN official_company_name VARCHAR(255)")
        if "inn" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN inn VARCHAR(12)")
        if "ogrn" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN ogrn VARCHAR(15)")
        if "kpp" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN kpp VARCHAR(9)")
        if "ceo_name" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN ceo_name VARCHAR(200)")
        if "okved_code" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN okved_code VARCHAR(32)")
        if "okved_name" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN okved_name VARCHAR(255)")
        if "company_status" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN company_status VARCHAR(50)")
        if "company_address" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN company_address TEXT")
        if "company_site" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN company_site VARCHAR(255)")
        if "source_url" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN source_url VARCHAR(500)")
        if "enrichment_status" not in existing:
            alter_stmts.append(
                "ALTER TABLE clients ADD COLUMN enrichment_status VARCHAR(50) DEFAULT 'not_requested'"
            )
        if "enrichment_error" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN enrichment_error TEXT")
        if "enriched_at" not in existing:
            alter_stmts.append("ALTER TABLE clients ADD COLUMN enriched_at DATETIME")
        for stmt in alter_stmts:
            await conn.exec_driver_sql(stmt)

        # 3) feedback.training_verdict (дообучение)
        res = await conn.exec_driver_sql("PRAGMA table_info(feedback)")
        fb_cols = {r[1] for r in res.fetchall()}
        if "training_verdict" not in fb_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE feedback ADD COLUMN training_verdict VARCHAR(20)"
            )

        # 4) Legacy VIP queue: treat as generated so due_sender can send on event day
        await conn.exec_driver_sql(
            "UPDATE greetings SET status = 'generated' WHERE status = 'needs_approval'"
        )

        # 5) Drop clients.segment (SQLite 3.35+). Older SQLite: delete backend/data/app.db or upgrade SQLite.
        res = await conn.exec_driver_sql("PRAGMA table_info(clients)")
        client_cols = {r[1] for r in res.fetchall()}
        if "segment" in client_cols:
            ver_row = (await conn.exec_driver_sql("SELECT sqlite_version()")).fetchone()
            ver_str = str(ver_row[0]) if ver_row else "0.0.0"
            parts = [int(x) for x in ver_str.split(".") if x.isdigit()]
            while len(parts) < 3:
                parts.append(0)
            major, minor, patch = parts[0], parts[1], parts[2]
            if (major, minor, patch) >= (3, 35, 0):
                await conn.exec_driver_sql("ALTER TABLE clients DROP COLUMN segment")
    except Exception:
        # For non-sqlite dialects or first-time DB, ignore.
        return


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
