from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AutonomyStatusOut(BaseModel):
    enabled: bool
    next_run_at: dt.datetime | None = None
