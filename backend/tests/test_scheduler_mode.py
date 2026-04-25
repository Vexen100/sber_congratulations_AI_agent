from __future__ import annotations

import datetime as dt

import httpx
import pytest
from sqlalchemy import select

from app.db.models import AgentRun, AutonomyState, Client, Event, Greeting
from app.db.session import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


async def test_inprocess_scheduler_does_not_start_when_mode_off(db_session, monkeypatch):
    # If scheduler mistakenly starts, this test will fail fast.
    import app.main as main_mod

    monkeypatch.setattr(main_mod.settings, "scheduler_mode", "off", raising=False)

    class _BoomScheduler:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("AsyncIOScheduler must not be constructed in mode=off")

    monkeypatch.setattr(main_mod, "AsyncIOScheduler", _BoomScheduler, raising=True)

    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    app.dependency_overrides.clear()

    assert resp.status_code == 200


async def test_worker_scheduler_exits_when_mode_not_worker(monkeypatch):
    import app.worker.run_scheduler as sched

    monkeypatch.setattr(sched.settings, "scheduler_mode", "off", raising=False)

    # If it tries to start the scheduler loop, we'd hang; instead, main() should return quickly.
    await sched.main()


async def test_manual_run_works_when_autonomy_disabled(db_session, monkeypatch):
    # Make autonomy explicitly disabled in DB.
    state = AutonomyState(id=1, enabled=False, updated_at=dt.datetime.now(dt.timezone.utc))
    db_session.add(state)
    await db_session.commit()

    c = Client(
        first_name="Ирина",
        middle_name="Олеговна",
        last_name="Орлова",
        profession="it",
        email="irina@company.test",
        preferred_channel="email",
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    ev = Event(
        client_id=c.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Ручной повод",
        details={},
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    g = Greeting(
        event_id=ev.id,
        client_id=c.id,
        subject="Поздравление",
        body="Текст поздравления",
        status="generated",
    )
    db_session.add(g)
    await db_session.commit()

    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/actions/run-agent")
    app.dependency_overrides.clear()

    assert resp.status_code in (200, 303)

    runs = (await db_session.execute(select(AgentRun.id))).scalars().all()
    assert len(runs) >= 1
