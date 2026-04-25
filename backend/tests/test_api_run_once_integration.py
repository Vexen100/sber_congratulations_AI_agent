"""HTTP + ASGI integration: API agent run against a real async DB session override."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest

from app.db.models import Client
from app.db.session import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


async def test_api_run_once_creates_greeting_and_delivery(db_session):
    today = dt.date.today()
    client_record = Client(
        first_name="Павел",
        middle_name="Иванович",
        last_name="Сидоров",
        company_name="ООО Вектор",
        email="pavel@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, today.month, today.day),
    )
    db_session.add(client_record)
    await db_session.commit()

    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.post("/api/agent/run-once")
        greetings_resp = await client.get("/api/greetings")
        deliveries_resp = await client.get("/api/deliveries")
    app.dependency_overrides.clear()

    assert run_resp.status_code == 200
    run_payload = run_resp.json()
    assert run_payload["generated_greetings"] >= 1
    assert run_payload["sent_deliveries"] >= 1

    assert greetings_resp.status_code == 200
    greetings_payload = greetings_resp.json()
    assert len(greetings_payload) >= 1
    assert any(item["client_id"] == client_record.id for item in greetings_payload)

    assert deliveries_resp.status_code == 200
    deliveries_payload = deliveries_resp.json()
    assert len(deliveries_payload) >= 1
