from __future__ import annotations

import httpx

from app.db.session import get_session
from app.main import create_app


async def test_autonomy_status_defaults_disabled(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/autonomy/status")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["next_run_at"] is None


async def test_autonomy_enable_sets_next_run(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/autonomy/enable")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["next_run_at"] is not None


async def test_runs_endpoint_exposes_autonomy_state(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ui/runs")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "autonomy" in data
    assert data["autonomy"]["enabled"] is False
    assert "runs" in data
