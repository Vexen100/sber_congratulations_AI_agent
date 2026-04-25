"""Unit tests for web router time formatting (kept separate from ASGI integration tests)."""

from __future__ import annotations

import datetime as dt

from app.web.router import _format_time_msk_hm


def test_format_time_msk_hm_converts_utc_to_moscow_clock():
    utc = dt.datetime(2026, 4, 24, 14, 30, 18, 400491, tzinfo=dt.timezone.utc)
    assert _format_time_msk_hm(utc) == "17:30"
