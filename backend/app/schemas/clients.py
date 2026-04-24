from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    official_company_name: str | None = Field(default=None, max_length=255)
    position: str | None = Field(default=None, max_length=200)
    profession: str | None = Field(default=None, max_length=80)
    inn: str | None = Field(default=None, min_length=10, max_length=12)
    ogrn: str | None = Field(default=None, max_length=15)
    kpp: str | None = Field(default=None, max_length=9)
    ceo_name: str | None = Field(default=None, max_length=200)
    okved_code: str | None = Field(default=None, max_length=32)
    okved_name: str | None = Field(default=None, max_length=255)
    company_status: str | None = Field(default=None, max_length=50)
    company_address: str | None = None
    company_site: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=500)
    enrichment_status: str = Field(default="not_requested", max_length=50)
    enrichment_error: str | None = None

    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    preferred_channel: str = Field(default="email", max_length=20)

    birth_date: dt.date | None = None
    preferences: dict = Field(default_factory=dict)
    last_interaction_summary: str | None = None


class ClientOut(BaseModel):
    id: int
    first_name: str
    middle_name: str | None
    last_name: str
    company_name: str | None
    official_company_name: str | None
    position: str | None
    profession: str | None
    inn: str | None
    ogrn: str | None
    kpp: str | None
    ceo_name: str | None
    okved_code: str | None
    okved_name: str | None
    company_status: str | None
    company_address: str | None
    company_site: str | None
    source_url: str | None
    enrichment_status: str
    enrichment_error: str | None
    enriched_at: dt.datetime | None
    email: str | None
    phone: str | None
    preferred_channel: str
    birth_date: dt.date | None
    preferences: dict
    last_interaction_summary: str | None

    model_config = ConfigDict(from_attributes=True)
