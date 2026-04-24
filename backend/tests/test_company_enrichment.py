from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Client
from app.services.company_enrichment import enrich_client_company_by_id, enrich_missing_clients


async def test_enrich_client_by_inn(db_session):
    client = Client(
        first_name="Наталья",
        middle_name="Олеговна",
        last_name="Морозова",
        company_name="ООО Безопасность+",
        position="Руководитель службы безопасности",
        profession="security",
        inn="7701122334",
        email="natalia@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        enrichment_status="pending",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    result = await enrich_client_company_by_id(db_session, client_id=client.id)
    assert result["status"] == "enriched"

    refreshed = (
        await db_session.execute(select(Client).where(Client.id == client.id))
    ).scalar_one()
    assert refreshed.official_company_name == 'ООО "Безопасность Плюс"'
    assert refreshed.okved_code == "80.10"
    assert refreshed.okved_name
    assert refreshed.ceo_name == "Морозова Наталья Олеговна"
    assert refreshed.enrichment_status == "enriched"
    assert refreshed.enriched_at is not None


async def test_bulk_enrichment_can_match_by_company_name(db_session):
    client = Client(
        first_name="Никита",
        middle_name="Сергеевич",
        last_name="Смирнов",
        company_name="ООО ДевСтудио",
        position="CTO",
        profession="it",
        email="nikita@company.test",
        preferred_channel="email",
        birth_date=dt.date(1991, 5, 10),
        enrichment_status="not_requested",
    )
    db_session.add(client)
    await db_session.commit()

    result = await enrich_missing_clients(db_session)
    assert result["processed"] == 1
    assert result["enriched"] == 1
    assert result["errors"] == 0

    refreshed = (await db_session.execute(select(Client))).scalars().one()
    assert refreshed.inn == "7801223300"
    assert refreshed.okved_name == "Разработка компьютерного программного обеспечения"
