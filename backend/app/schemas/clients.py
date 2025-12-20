from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    company_name: str | None = Field(default=None, max_length=200)
    position: str | None = Field(default=None, max_length=200)
    profession: str | None = Field(default=None, max_length=80)
    segment: str = Field(default="standard", max_length=50)

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
    position: str | None
    profession: str | None
    segment: str
    email: str | None
    phone: str | None
    preferred_channel: str
    birth_date: dt.date | None
    preferences: dict
    last_interaction_summary: str | None

    model_config = ConfigDict(from_attributes=True)
