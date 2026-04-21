from __future__ import annotations

import datetime as dt

import httpx
import pytest
from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import AgentRun, Client, Delivery, Event, Feedback, Greeting
from app.db.session import get_session
from app.main import create_app

pytestmark = pytest.mark.integration


async def test_dashboard_page_renders_new_presentation_layout(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "Конвейер поздравлений Сбера" in resp.text
    assert "Рабочее пространство для презентации" in resp.text
    assert "Как показать демо" in resp.text
    assert "Воронка после запуска" in resp.text
    assert "Операционное здоровье" in resp.text


async def test_clients_page_renders_enrichment_ui(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/clients")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "Качество данных" in resp.text
    assert "Импортировать базу компаний" in resp.text
    assert "Обогатить профили компаний" in resp.text
    assert "Добавить клиента вручную" in resp.text


async def test_events_page_renders_manual_event_controls(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/events")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "Создать ручное событие" in resp.text
    assert "Быстрая demo-кампания" in resp.text
    assert "Подготовить события для реальной базы" in resp.text


async def test_run_detail_page_renders_greetings_for_selected_run(db_session):
    client_record = Client(
        first_name="Анна",
        middle_name="Игоревна",
        last_name="Соколова",
        company_name="ООО Спектр",
        segment="standard",
        email="anna@company.ru",
        preferred_channel="email",
        birth_date=dt.date.today(),
    )
    db_session.add(client_record)
    await db_session.commit()
    await run_once(db_session, today=dt.date.today(), lookahead_days=1, triggered_by="test-web")
    run = (
        (await db_session.execute(select(AgentRun).order_by(AgentRun.id.desc()))).scalars().first()
    )
    assert run is not None

    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/runs/{run.id}")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert f"Детали запуска #{run.id}" in resp.text
    assert "Анна" in resp.text
    assert "ООО Спектр" in resp.text


async def test_dashboard_page_shows_pipeline_metrics_from_runtime_data(db_session):
    client_record = Client(
        first_name="Ирина",
        middle_name="Олеговна",
        last_name="Орлова",
        company_name="ООО Аналитика",
        segment="vip",
        email="irina@company.ru",
        preferred_channel="email",
    )
    db_session.add(client_record)
    await db_session.commit()

    event = Event(
        client_id=client_record.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Тестовая воронка",
        details={"source": "test"},
    )
    db_session.add(event)
    await db_session.commit()

    greeting = Greeting(
        event_id=event.id,
        client_id=client_record.id,
        subject="Поздравление",
        body="Текст поздравления",
        status="needs_approval",
    )
    db_session.add(greeting)
    await db_session.commit()

    delivery = Delivery(
        greeting_id=greeting.id,
        channel="file",
        recipient="irina@company.ru",
        status="error",
        provider_message="smtp:error:Timeout",
        sent_at=dt.datetime.now(dt.timezone.utc),
        idempotency_key="delivery-test-key",
    )
    feedback = Feedback(greeting_id=greeting.id, score=4, outcome="opened", notes="ok")
    problematic_run = AgentRun(triggered_by="test", status="partial", errors=1)
    db_session.add_all([delivery, feedback, problematic_run])
    await db_session.commit()

    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "Ждут согласования" in resp.text
    assert "Ошибки доставки" in resp.text
    assert "Запуски с проблемами" in resp.text
    assert "Средняя оценка" in resp.text
    assert ">100%<" in resp.text
    assert ">4<" in resp.text or ">4.0<" in resp.text
