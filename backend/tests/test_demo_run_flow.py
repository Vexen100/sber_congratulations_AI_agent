from __future__ import annotations

import datetime as dt

from app.agent.orchestrator import run_once
from app.api.routes.clients import seed_demo_clients


async def test_demo_seed_creates_presentation_ready_run(db_session):
    today = dt.date(2025, 12, 19)
    res = await seed_demo_clients(db_session, n=5, replace=True, today=today, rng_seed=123)
    assert res["added"] == 5

    summary = await run_once(db_session, today=today, lookahead_days=1, triggered_by="test")
    assert summary.generated_greetings >= 5
    assert summary.sent_deliveries >= 5
