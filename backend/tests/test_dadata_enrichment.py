from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Client
from app.services.company_enrichment import enrich_client_company_by_id


async def test_enrich_client_via_dadata_provider(db_session, monkeypatch):
    async def fake_find_party_by_inn(_inn: str) -> dict:
        return {
            "value": 'ООО "Тест Авто"',
            "data": {
                "inn": "7701234567",
                "ogrn": "1027700000000",
                "kpp": "770101001",
                "okved": "45.20",
                "okveds": [{"code": "45.20", "name": "Техническое обслуживание автомобилей"}],
                "state": {"status": "ACTIVE"},
                "management": {
                    "name": "Иванов Иван Иванович",
                    "post": "Генеральный директор",
                },
                "name": {
                    "short_with_opf": 'ООО "Тест Авто"',
                    "full_with_opf": 'Общество с ограниченной ответственностью "Тест Авто"',
                },
                "address": {
                    "unrestricted_value": "г Москва, ул Тестовая, д 1",
                    "value": "г Москва, ул Тестовая, д 1",
                },
                "emails": [{"value": "info@test-auto.ru"}],
                "phones": [{"value": "+7 495 000-00-00"}],
            },
        }

    monkeypatch.setattr(settings, "company_enrichment_provider", "dadata", raising=False)
    monkeypatch.setattr("app.services.company_enrichment.find_party_by_inn", fake_find_party_by_inn)

    client = Client(
        first_name="Иван",
        middle_name="Иванович",
        last_name="Иванов",
        company_name="Тест Авто",
        profession="management",
        inn="7701234567",
        email="contact@local.test",
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
    assert refreshed.official_company_name == 'ООО "Тест Авто"'
    assert refreshed.ogrn == "1027700000000"
    assert refreshed.kpp == "770101001"
    assert refreshed.okved_name == "Техническое обслуживание автомобилей"
    assert refreshed.company_status == "ACTIVE"
    assert refreshed.company_address == "г Москва, ул Тестовая, д 1"
    assert refreshed.email == "info@test-auto.ru"
    assert refreshed.phone == "+7 495 000-00-00"
