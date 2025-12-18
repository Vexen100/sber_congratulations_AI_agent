from __future__ import annotations

from pydantic import BaseModel


class AgentRunResult(BaseModel):
    scanned_events: int
    generated_greetings: int
    sent_deliveries: int
    skipped_existing: int
    errors: int
