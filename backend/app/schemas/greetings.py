from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class GreetingOut(BaseModel):
    id: int
    event_id: int
    client_id: int | None
    tone: str
    subject: str
    body: str
    image_path: str | None
    status: str
    created_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)
