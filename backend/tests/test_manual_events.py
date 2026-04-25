from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.agent.orchestrator import run_once
from app.db.models import Client, Event, Greeting
from app.services.manual_events import (
    create_manual_event_record,
    seed_manual_campaign_for_real_clients,
)


async def test_create_manual_event_record_persists_event(db_session):
    client = Client(
        first_name="Ирина",
        middle_name="Ивановна",
        last_name="Петрова",
        company_name="ООО Партнер",
        profession="management",
        email="partner@company.test",
        preferred_channel="email",
        is_demo=False,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = await create_manual_event_record(
        db_session,
        client_id=client.id,
        event_date=dt.date.today(),
        title="Спасибо за партнёрство",
        metadata={"source": "test"},
    )

    assert event.event_type == "manual"
    assert event.client_id == client.id
    assert event.title == "Спасибо за партнёрство"


async def test_seed_manual_campaign_for_real_clients_generates_agent_input(db_session):
    today = dt.date.today()
    clients = [
        ("sales", "ООО Компания Продаж"),
        ("finance", "ООО Компания Финансы"),
        ("it", "ООО Компания Тех"),
    ]
    for idx, (profession, company) in enumerate(clients):
        db_session.add(
            Client(
                first_name=f"Клиент{idx}",
                middle_name="Иванович",
                last_name="Тестов",
                company_name=company,
                profession=profession,
                email=f"real{idx}@company.test",
                preferred_channel="email",
                is_demo=False,
            )
        )
    await db_session.commit()

    result = await seed_manual_campaign_for_real_clients(
        db_session,
        event_date=today,
        title="Персональное деловое поздравление",
        limit=3,
    )
    assert result["created"] == 3

    events = (
        (await db_session.execute(select(Event).where(Event.event_type == "manual")))
        .scalars()
        .all()
    )
    assert len(events) == 3
    assert any(e.title == "Желаем сильных продаж и новых клиентов" for e in events)
    assert any(e.title == "Желаем финансовой устойчивости и уверенного роста" for e in events)
    assert any((e.details or {}).get("focus_hint") == "technology" for e in events)

    summary = await run_once(db_session, today=today, lookahead_days=1, triggered_by="test")
    assert summary.generated_greetings >= 3

    greetings = (await db_session.execute(select(Greeting))).scalars().all()
    assert len(greetings) >= 3
