from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ManualEventCreate(BaseModel):
    client_id: int | None = None
    event_date: dt.date
    title: str = Field(min_length=1, max_length=250)
    metadata: dict = Field(default_factory=dict)


class EventOut(BaseModel):
    id: int
    client_id: int | None
    event_type: str
    event_date: dt.date
    title: str
    metadata: dict = Field(validation_alias="details")

    model_config = ConfigDict(from_attributes=True)
