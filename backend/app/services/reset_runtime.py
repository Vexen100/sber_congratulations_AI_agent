from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, Delivery, Event, Greeting


async def reset_runtime_data(session: AsyncSession) -> dict:
    """Reset runtime-generated data for clean demos.

    - Keeps Clients and Holidays
    - Clears Events, Greetings, Deliveries, AgentRuns
    - Clears artifacts in data/outbox, data/cards, data/smoke
    """
    await session.execute(delete(Delivery))
    await session.execute(delete(Greeting))
    await session.execute(delete(Event))
    await session.execute(delete(AgentRun))
    await session.commit()

    base = Path(__file__).resolve().parents[2] / "data"
    cleared_files = 0
    for sub in ("outbox", "cards", "smoke"):
        d = base / sub
        if not d.exists():
            continue
        for p in d.glob("*"):
            if p.is_file():
                try:
                    p.unlink()
                    cleared_files += 1
                except Exception:
                    pass

    return {"ok": True, "cleared_files": cleared_files}
