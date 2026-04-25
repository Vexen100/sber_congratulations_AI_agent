from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, Client, Delivery, Event, Feedback, Greeting


async def reset_runtime_data(
    session: AsyncSession,
    *,
    clear_clients: bool = False,
    demo_clients_only: bool = False,
) -> dict:
    """Reset runtime-generated data for clean demos.

    - By default keeps Clients and Holidays
    - Clears Feedback, Events, Greetings, Deliveries, AgentRuns
    - Optionally clears clients as well
    - Clears artifacts in data/outbox, data/cards, data/smoke
    """
    await session.execute(delete(Feedback))
    await session.execute(delete(Delivery))
    await session.execute(delete(Greeting))
    await session.execute(delete(Event))
    await session.execute(delete(AgentRun))
    cleared_clients = 0
    if clear_clients:
        if demo_clients_only:
            demo_ids = (
                await session.execute(delete(Client).where(Client.is_demo.is_(True)))
            ).rowcount
            cleared_clients = int(demo_ids or 0)
        else:
            deleted = (await session.execute(delete(Client))).rowcount
            cleared_clients = int(deleted or 0)
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

    return {
        "ok": True,
        "cleared_files": cleared_files,
        "cleared_clients": cleared_clients,
    }
