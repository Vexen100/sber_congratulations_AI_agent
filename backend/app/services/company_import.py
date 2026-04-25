from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Client
from app.services.company_data_files import DEFAULT_COMPANY_IMPORT_CSV_PATH

_EMPTY_MARKERS = {
    "",
    "-",
    "—",
    "не выбрано в конфигураторе",
}


def _clean_cell(value: str | None) -> str | None:
    text = (value or "").replace("\ufeff", "").strip()
    if not text:
        return None
    if text.lower() in _EMPTY_MARKERS:
        return None
    return text


def _normalize_header(value: str | None) -> str:
    text = (value or "").replace("\ufeff", "").strip()
    text = text.strip('"').strip("'").strip()
    return unicodedata.normalize("NFKC", text)


def _split_contact_values(value: str | None) -> list[str]:
    text = (value or "").replace("\r", "\n")
    text = text.replace(";", ",").replace("\n", ",")
    parts = [re.sub(r"\s+", " ", chunk).strip(" ,") for chunk in text.split(",")]
    cleaned = [part for part in parts if part]
    # Preserve order but deduplicate exact duplicates.
    return list(dict.fromkeys(cleaned))


def _parse_int_value(value: str | None) -> int | None:
    text = _clean_cell(value)
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _infer_profession(row: dict[str, str]) -> str:
    context = " ".join(
        filter(
            None,
            [
                _clean_cell(row.get("Рубрика")),
                _clean_cell(row.get("Подрубрика")),
                _clean_cell(row.get("Главный ОКВЭД (название)")),
                _clean_cell(row.get("Заголовок сайта (title)")),
                _clean_cell(row.get("Тип компании")),
            ],
        )
    ).lower()
    rules = [
        ("security", ("охран", "безопас", "security")),
        ("accounting", ("бухгалтер", "учет", "налог")),
        ("finance", ("финанс", "банк", "лизинг", "страх")),
        ("it", ("программ", "it", "айти", "цифр", "технолог", "software")),
        ("hr", ("персонал", "кадр", "hr", "рекрут")),
        ("marketing", ("маркет", "реклам", "бренд", "pr")),
        ("sales", ("торгов", "магазин", "дилер", "продаж", "retail", "автосалон")),
        ("logistics", ("логист", "перевоз", "склад", "транспорт", "достав")),
        ("construction", ("строит", "проектир", "ремонт здан", "девелоп")),
        ("medicine", ("мед", "клиник", "фарма", "здрав")),
    ]
    for profession, keywords in rules:
        if any(keyword in context for keyword in keywords):
            return profession
    return "management"


def _csv_path() -> Path:
    raw = (settings.company_import_csv_path or "").strip()
    if not raw:
        return DEFAULT_COMPANY_IMPORT_CSV_PATH
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / raw
    return path


def _parse_person_name(full_name: str | None) -> tuple[str, str | None, str] | None:
    text = _clean_cell(full_name)
    if not text:
        return None
    parts = [p for p in re.split(r"\s+", text) if p]
    if len(parts) >= 3 and parts[-1].endswith("."):
        first_name, middle_name, last_name = parts[0], parts[1], parts[2]
        return first_name, middle_name, last_name
    if len(parts) >= 3:
        last_name, first_name, middle_name = parts[0], parts[1], parts[2]
        return first_name, middle_name, last_name
    if len(parts) == 2:
        first_name, last_name = parts[0], parts[1]
        return first_name, None, last_name
    return None


def _pick_contact(row: dict[str, str]) -> tuple[str | None, str | None, str]:
    email = _clean_cell(row.get("Email компании"))
    phone_candidates = (
        _split_contact_values(row.get("Мобильный телефон компании"))
        or _split_contact_values(row.get("Стационарный телефон компании"))
        or _split_contact_values(row.get("Бесплатный номер компании"))
    )
    phone = phone_candidates[0] if phone_candidates else None
    preferred_channel = "email" if email else "messenger"
    return email, phone, preferred_channel


def _build_preferences(row: dict[str, str]) -> dict:
    preferences = {
        "import_source": "company_base_csv",
        "city": _clean_cell(row.get("Город")),
        "district": _clean_cell(row.get("Район города")),
        "region": _clean_cell(row.get("Регион")),
        "federal_district": _clean_cell(row.get("Федеральный округ")),
        "rubric": _clean_cell(row.get("Рубрика")),
        "subrubric": _clean_cell(row.get("Подрубрика")),
        "company_status_raw": _clean_cell(row.get("Статус")),
        "employee_count": _clean_cell(row.get("Численность сотрудников (чел.) *")),
        "revenue_thousand_rub": _clean_cell(row.get("Выручка (тыс. руб.) *")),
    }
    return {key: value for key, value in preferences.items() if value}


async def import_clients_from_company_csv(session: AsyncSession) -> dict:
    path = _csv_path()
    if not path.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {path}")

    added = 0
    updated = 0
    skipped = 0

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        reader.fieldnames = [_normalize_header(name) for name in (reader.fieldnames or [])]
        for row in reader:
            row = {_normalize_header(key): value for key, value in row.items()}
            company_name = _clean_cell(row.get("Название компании"))
            inn = re.sub(r"\D", "", row.get("ИНН") or "")
            if not company_name or not inn:
                skipped += 1
                continue

            name_parts = _parse_person_name(row.get("Руководитель (по ЕГРЮЛ)"))
            if name_parts:
                first_name, middle_name, last_name = name_parts
            else:
                first_name, middle_name, last_name = "Контакт", None, company_name[:96]

            email, phone, preferred_channel = _pick_contact(row)
            existing = (
                await session.execute(select(Client).where(Client.inn == inn).limit(1))
            ).scalar_one_or_none()

            target = existing or Client(
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                profession=_infer_profession(row),
                preferred_channel="email",
                is_demo=False,
            )

            target.company_name = company_name
            target.official_company_name = company_name
            target.inn = inn
            target.ogrn = re.sub(r"\D", "", row.get("ОГРН") or "") or None
            inferred_profession = _infer_profession(row)
            target.profession = target.profession or inferred_profession
            target.ceo_name = _clean_cell(row.get("Руководитель (по ЕГРЮЛ)"))
            target.okved_code = _clean_cell(row.get("Главный ОКВЭД (код)"))
            target.okved_name = _clean_cell(row.get("Главный ОКВЭД (название)"))
            target.company_status = _clean_cell(row.get("Статус"))
            target.position = target.position or (
                "Руководитель организации" if target.ceo_name else None
            )
            target.company_address = _clean_cell(row.get("Адрес компании")) or _clean_cell(
                row.get("Адрес и почтовый индекс компании")
            )
            target.company_site = _clean_cell(row.get("Сайт"))
            target.source_url = target.source_url or f"import://{path.name}"
            target.email = email or target.email
            target.phone = phone or target.phone
            target.preferred_channel = preferred_channel if (email or phone) else "email"
            target.preferences = {
                **(target.preferences or {}),
                **_build_preferences(row),
            }
            target.enrichment_status = "enriched"
            target.enrichment_error = None
            target.enriched_at = dt.datetime.now(dt.timezone.utc)

            if existing is None:
                session.add(target)
                added += 1
            else:
                updated += 1

    await session.commit()
    return {
        "path": str(path),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "processed": added + updated,
    }
