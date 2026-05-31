from __future__ import annotations

import datetime as dt

import httpx
import pytest
from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import Client, Delivery, Event, Feedback, Greeting
from app.db.session import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


def _build_test_client(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def test_root_serves_react_shell_or_build_hint(db_session):
    app, client = _build_test_client(db_session)
    async with client:
        resp = await client.get("/")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert '<div id="root"></div>' in resp.text or "React build not found" in resp.text


async def test_ui_dashboard_endpoint_returns_metrics(db_session):
    app, client = _build_test_client(db_session)
    async with client:
        resp = await client.get("/api/ui/dashboard")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["clients_count"] == 0
    assert "last_runs" in payload
    assert "delivery_success_rate" in payload


async def test_ui_clients_and_events_endpoints_return_structured_payloads(db_session):
    client_record = Client(
        first_name="Ирина",
        middle_name="Олеговна",
        last_name="Орлова",
        company_name="ООО Аналитика",
        profession="it",
        email="irina@company.ru",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client_record)
    await db_session.commit()
    await db_session.refresh(client_record)

    event = Event(
        client_id=client_record.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Тестовое событие",
        details={"source": "test"},
    )
    db_session.add(event)
    await db_session.commit()

    app, client = _build_test_client(db_session)
    async with client:
        clients_resp = await client.get("/api/ui/clients")
        events_resp = await client.get("/api/ui/events")
    app.dependency_overrides.clear()

    assert clients_resp.status_code == 200
    assert events_resp.status_code == 200

    clients_payload = clients_resp.json()
    events_payload = events_resp.json()
    assert clients_payload["company_enrichment_provider"]
    assert clients_payload["clients"][0]["is_demo"] is False
    assert events_payload["events"][0]["title"] == "Тестовое событие"
    assert events_payload["events"][0]["client"]["id"] == client_record.id


async def test_ui_runs_and_run_detail_endpoints_return_linked_greetings(db_session):
    client_record = Client(
        first_name="Анна",
        middle_name="Игоревна",
        last_name="Соколова",
        company_name="ООО Спектр",
        profession="it",
        email="anna@company.ru",
        preferred_channel="email",
        birth_date=dt.date.today(),
    )
    db_session.add(client_record)
    await db_session.commit()

    await run_once(db_session, today=dt.date.today(), lookahead_days=1, triggered_by="test-ui")
    run = (
        (
            await db_session.execute(
                select(Greeting.agent_run_id).where(Greeting.agent_run_id.is_not(None))
            )
        )
        .scalars()
        .first()
    )
    assert run is not None

    app, client = _build_test_client(db_session)
    async with client:
        runs_resp = await client.get("/api/ui/runs")
        detail_resp = await client.get(f"/api/ui/runs/{run}")
    app.dependency_overrides.clear()

    assert runs_resp.status_code == 200
    assert detail_resp.status_code == 200

    runs_payload = runs_resp.json()
    detail_payload = detail_resp.json()
    assert runs_payload["runs"][0]["id"] == run
    assert detail_payload["run"]["id"] == run
    assert detail_payload["greetings"]
    assert detail_payload["greetings"][0]["client"]["first_name"] == "Анна"


async def test_ui_deliveries_endpoint_returns_nested_greeting_and_feedback(db_session):
    client_record = Client(
        first_name="Доставка",
        middle_name="Тестович",
        last_name="Время",
        profession="it",
        email="d@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    db_session.add(client_record)
    await db_session.commit()
    await db_session.refresh(client_record)

    event = Event(
        client_id=client_record.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Повод",
        details={},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    greeting = Greeting(
        event_id=event.id,
        client_id=client_record.id,
        tone="warm",
        subject="Тема",
        body="Текст поздравления достаточной длины." * 3,
        status="sent",
    )
    db_session.add(greeting)
    await db_session.commit()
    await db_session.refresh(greeting)

    feedback = Feedback(
        greeting_id=greeting.id,
        score=5,
        outcome="opened",
        notes="Отлично",
        training_verdict="accepted",
    )
    delivery = Delivery(
        greeting_id=greeting.id,
        channel="file",
        recipient="d@company.test",
        status="sent",
        provider_message="ok",
        sent_at=dt.datetime(2026, 4, 24, 14, 30, 18, tzinfo=dt.timezone.utc),
        idempotency_key="test-ui-delivery-key",
    )
    db_session.add_all([feedback, delivery])
    await db_session.commit()

    app, client = _build_test_client(db_session)
    async with client:
        resp = await client.get("/api/ui/deliveries")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["deliveries"][0]["sent_at"].startswith("2026-04-24T14:30:18")
    assert payload["deliveries"][0]["greeting"]["client"]["email"] == "d@company.test"
