"""Unit tests for Moscow time formatting."""

from __future__ import annotations

import datetime as dt

from app.services.dates import format_time_msk_hm


def test_format_time_msk_hm_converts_utc_to_moscow_clock():
    utc = dt.datetime(2026, 4, 24, 14, 30, 18, 400491, tzinfo=dt.timezone.utc)
    assert format_time_msk_hm(utc) == "17:30"
