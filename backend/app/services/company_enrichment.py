from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Client
from app.services.company_data_files import DEMO_REGISTRY_PATH
from app.services.dadata_client import (
    DadataConfigurationError,
    DadataRequestError,
    find_party_by_inn,
)


@dataclass(frozen=True)
class CompanyProfile:
    inn: str
    official_company_name: str
    ceo_name: str | None
    okved_code: str | None
    okved_name: str | None
    company_site: str | None
    source_url: str | None
    aliases: tuple[str, ...] = ()
    ogrn: str | None = None
    kpp: str | None = None
    company_status: str | None = None
    company_address: str | None = None
    email: str | None = None
    phone: str | None = None
    position: str | None = None


def _normalize_name(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


@lru_cache(maxsize=1)
def _demo_registry() -> list[CompanyProfile]:
    if not DEMO_REGISTRY_PATH.exists():
        return []
    raw_items = json.loads(DEMO_REGISTRY_PATH.read_text(encoding="utf-8"))
    return [
        CompanyProfile(
            inn=str(item["inn"]),
            official_company_name=str(item["official_company_name"]),
            ceo_name=item.get("ceo_name"),
            okved_code=item.get("okved_code"),
            okved_name=item.get("okved_name"),
            company_site=item.get("company_site"),
            source_url=item.get("source_url"),
            aliases=tuple(item.get("aliases", [])),
            ogrn=item.get("ogrn"),
            kpp=item.get("kpp"),
            company_status=item.get("company_status"),
            company_address=item.get("company_address"),
            email=item.get("email"),
            phone=item.get("phone"),
            position=item.get("position"),
        )
        for item in raw_items
    ]


def lookup_demo_company_profile(
    *, inn: str | None, company_name: str | None
) -> CompanyProfile | None:
    norm_inn = re.sub(r"\D", "", inn or "")
    norm_company = _normalize_name(company_name)
    for item in _demo_registry():
        if norm_inn and item.inn == norm_inn:
            return item
        alias_names = {
            _normalize_name(item.official_company_name),
            *(_normalize_name(a) for a in item.aliases),
        }
        if norm_company and norm_company in alias_names:
            return item
    return None


def _resolve_okved_name(party_data: dict) -> str | None:
    okved_code = party_data.get("okved")
    okveds = party_data.get("okveds") or []
    if okved_code and okveds:
        for item in okveds:
            if item.get("code") == okved_code:
                return item.get("name")
        main_okved = next((item for item in okveds if item.get("main")), None)
        if main_okved:
            return main_okved.get("name")
    return None


def _map_dadata_party_to_profile(suggestion: dict) -> CompanyProfile:
    data = suggestion.get("data") or {}
    management = data.get("management") or {}
    address = data.get("address") or {}
    emails = data.get("emails") or []
    phones = data.get("phones") or []
    return CompanyProfile(
        inn=str(data.get("inn") or ""),
        official_company_name=(
            data.get("name", {}).get("short_with_opf")
            or data.get("name", {}).get("full_with_opf")
            or suggestion.get("value")
            or ""
        ),
        ceo_name=management.get("name"),
        okved_code=data.get("okved"),
        okved_name=_resolve_okved_name(data),
        company_site=None,
        source_url="https://dadata.ru/api/find-party/",
        ogrn=data.get("ogrn"),
        kpp=data.get("kpp"),
        company_status=(data.get("state") or {}).get("status"),
        company_address=address.get("unrestricted_value") or address.get("value"),
        email=(emails[0] or {}).get("value") if emails else None,
        phone=(phones[0] or {}).get("value") if phones else None,
        position=management.get("post"),
    )


async def lookup_dadata_company_profile(*, inn: str | None) -> CompanyProfile | None:
    norm_inn = re.sub(r"\D", "", inn or "")
    if not norm_inn:
        return None
    suggestion = await find_party_by_inn(norm_inn)
    if suggestion is None:
        return None
    return _map_dadata_party_to_profile(suggestion)


async def lookup_company_profile(
    *,
    inn: str | None,
    company_name: str | None,
) -> tuple[CompanyProfile | None, str | None]:
    provider = (settings.company_enrichment_provider or "demo").strip().lower()
    if provider not in {"demo", "dadata", "hybrid"}:
        provider = "demo"

    if provider == "demo":
        profile = lookup_demo_company_profile(inn=inn, company_name=company_name)
        return profile, (None if profile else "Организация не найдена в локальном demo-реестре.")

    if provider == "dadata":
        try:
            profile = await lookup_dadata_company_profile(inn=inn)
        except (DadataConfigurationError, DadataRequestError) as exc:
            return None, str(exc)
        if profile is None:
            return None, "Организация не найдена в DaData по указанному ИНН."
        return profile, None

    # hybrid
    try:
        dadata_profile = await lookup_dadata_company_profile(inn=inn)
    except DadataConfigurationError:
        dadata_profile = None
    except DadataRequestError as exc:
        demo_profile = lookup_demo_company_profile(inn=inn, company_name=company_name)
        if demo_profile is not None:
            return demo_profile, None
        return None, str(exc)
    if dadata_profile is not None:
        return dadata_profile, None

    demo_profile = lookup_demo_company_profile(inn=inn, company_name=company_name)
    if demo_profile is not None:
        return demo_profile, None
    return None, "Организация не найдена ни в DaData, ни в локальном demo-реестре."


def _apply_profile_to_client(client: Client, profile: CompanyProfile) -> None:
    client.inn = profile.inn or client.inn
    client.official_company_name = profile.official_company_name or client.official_company_name
    client.ceo_name = profile.ceo_name or client.ceo_name
    client.okved_code = profile.okved_code or client.okved_code
    client.okved_name = profile.okved_name or client.okved_name
    client.company_site = profile.company_site or client.company_site
    client.source_url = profile.source_url or client.source_url
    client.ogrn = profile.ogrn or client.ogrn
    client.kpp = profile.kpp or client.kpp
    client.company_status = profile.company_status or client.company_status
    client.company_address = profile.company_address or client.company_address
    client.email = profile.email or client.email
    client.phone = profile.phone or client.phone
    client.position = client.position or profile.position


async def enrich_client_company(
    session: AsyncSession,
    *,
    client: Client,
) -> dict:
    if not client.inn and not client.company_name:
        client.enrichment_status = "error"
        client.enrichment_error = "Для enrichment нужен хотя бы ИНН или название компании."
        await session.commit()
        return {
            "status": "error",
            "client_id": client.id,
            "reason": client.enrichment_error,
        }

    client.enrichment_status = "pending"
    client.enrichment_error = None
    await session.commit()

    profile, error = await lookup_company_profile(inn=client.inn, company_name=client.company_name)
    if profile is None:
        client.enrichment_status = "error"
        client.enrichment_error = error or "Не удалось обогатить профиль компании."
        await session.commit()
        return {
            "status": "error",
            "client_id": client.id,
            "reason": client.enrichment_error,
        }

    _apply_profile_to_client(client, profile)
    client.enrichment_status = "enriched"
    client.enrichment_error = None
    client.enriched_at = dt.datetime.now(dt.timezone.utc)
    await session.commit()
    return {"status": "enriched", "client_id": client.id, "inn": client.inn}


async def enrich_client_company_by_id(session: AsyncSession, *, client_id: int) -> dict:
    client = (await session.execute(select(Client).where(Client.id == client_id))).scalar_one()
    return await enrich_client_company(session, client=client)


async def enrich_missing_clients(session: AsyncSession, *, force: bool = False) -> dict:
    clients = (await session.execute(select(Client).order_by(Client.id.asc()))).scalars().all()
    processed = 0
    enriched = 0
    errors = 0
    for client in clients:
        if not client.inn and not client.company_name:
            continue
        if client.enrichment_status == "enriched" and not force:
            continue
        processed += 1
        result = await enrich_client_company(session, client=client)
        if result["status"] == "enriched":
            enriched += 1
        else:
            errors += 1
    return {
        "processed": processed,
        "enriched": enriched,
        "errors": errors,
    }
