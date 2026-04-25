from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Client
from app.services.company_import import import_clients_from_company_csv


async def test_import_clients_from_company_csv_creates_clients(db_session, monkeypatch, tmp_path):
    csv_path = tmp_path / "companies.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(
            [
                "Название компании",
                "Стационарный телефон компании",
                "Мобильный телефон компании",
                "Бесплатный номер компании",
                "Whatsapp компании",
                "Telegram компании",
                "Viber компании",
                "ИНН",
                "ОГРН",
                "Руководитель (по ЕГРЮЛ)",
                "Заголовок сайта (title)",
                "Тип компании",
                "Город",
                "Район города",
                "Регион",
                "Федеральный округ",
                "Рубрика",
                "Подрубрика",
                "Тип подрубрики *",
                "Координаты(x, y)",
                "Часы работы компании по местному времени",
                "Часовой пояс",
                "Статус",
                "Рейтинг компании в Интернете",
                "Примерное число отзывов в Интернете",
                "Адрес компании",
                "Адрес и почтовый индекс компании",
                "Email компании",
                "Сайт",
                "Социальные сети",
                "Численность сотрудников (чел.) *",
                "Выручка (тыс. руб.) *",
                "Главный ОКВЭД (код)",
                "Главный ОКВЭД (название)",
            ]
        )
        writer.writerow(
            [
                "Тестовая Компания",
                "+7 (495) 000-00-00",
                "",
                "",
                "",
                "",
                "",
                "7701234567",
                "1027700000000",
                "Иванов Иван Иванович",
                "Тестовый сайт",
                "Дилер",
                "Москва",
                "",
                "Московская область",
                "ЦФО",
                "Авто",
                "Автосервис",
                "Главная",
                "",
                "",
                "",
                "Действующая",
                "",
                "",
                "Москва, ул. Тестовая, д. 1",
                "",
                "ceo@test-company.ru",
                "https://test-company.ru",
                "",
                "120",
                "50000",
                "45.20",
                "Техническое обслуживание и ремонт автотранспортных средств",
            ]
        )

    monkeypatch.setattr(settings, "company_import_csv_path", str(csv_path), raising=False)

    result = await import_clients_from_company_csv(db_session)
    assert result["added"] == 1
    assert result["updated"] == 0

    client = (await db_session.execute(select(Client))).scalars().one()
    assert client.inn == "7701234567"
    assert client.ogrn == "1027700000000"
    assert client.email == "ceo@test-company.ru"
    assert client.phone == "+7 (495) 000-00-00"
    assert client.company_site == "https://test-company.ru"
    assert client.okved_code == "45.20"
    assert client.company_status == "Действующая"
    assert client.position == "Руководитель организации"
    assert client.profession == "sales"
    assert client.enrichment_status == "enriched"
    assert client.enriched_at is not None
    assert client.preferences["import_source"] == "company_base_csv"


async def test_import_clients_from_company_csv_updates_existing_by_inn(
    db_session, monkeypatch, tmp_path
):
    existing = Client(
        first_name="Иван",
        middle_name="Иванович",
        last_name="Иванов",
        company_name="Старая компания",
        profession="management",
        email="old@test.ru",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        inn="7701234567",
        is_demo=False,
    )
    db_session.add(existing)
    await db_session.commit()

    csv_path = tmp_path / "companies.csv"
    csv_path.write_text(
        '"Название компании";"Стационарный телефон компании";"Мобильный телефон компании";"Бесплатный номер компании";"Whatsapp компании";"Telegram компании";"Viber компании";ИНН;ОГРН;"Руководитель (по ЕГРЮЛ)";"Заголовок сайта (title)";"Тип компании";Город;"Район города";Регион;"Федеральный округ";Рубрика;Подрубрика;"Тип подрубрики *";"Координаты(x, y)";"Часы работы компании по местному времени";"Часовой пояс";Статус;"Рейтинг компании в Интернете";"Примерное число отзывов в Интернете";"Адрес компании";"Адрес и почтовый индекс компании";"Email компании";Сайт;"Социальные сети";"Численность сотрудников (чел.) *";"Выручка (тыс. руб.) *";"Главный ОКВЭД (код)";"Главный ОКВЭД (название)"\n"Новая компания";"+7 (495) 111-11-11";"";"";"";"";"";7701234567;1027700000001;"Петров Петр Петрович";"";"";Москва;"";"";"";"";"";"";"";"";"";Действующая;"";"";"Москва";"";"new@test.ru";"https://new.ru";"";"";"";47.91;"Торговля розничная"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "company_import_csv_path", str(csv_path), raising=False)

    result = await import_clients_from_company_csv(db_session)
    assert result["added"] == 0
    assert result["updated"] == 1

    refreshed = (await db_session.execute(select(Client))).scalars().one()
    assert refreshed.company_name == "Новая компания"
    assert refreshed.ogrn == "1027700000001"
    assert refreshed.email == "new@test.ru"
    assert refreshed.profession == "management"
    assert refreshed.enrichment_status == "enriched"


async def test_import_clients_from_real_demo_csv_handles_bom_header(db_session, monkeypatch):
    csv_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "company_data"
        / "export-base_demo_takbup.csv"
    )
    monkeypatch.setattr(settings, "company_import_csv_path", str(csv_path), raising=False)

    result = await import_clients_from_company_csv(db_session)

    assert result["added"] > 0 or result["updated"] > 0
    assert result["processed"] > 0
