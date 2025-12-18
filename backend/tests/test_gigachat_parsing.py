from __future__ import annotations

import datetime as dt

from app.agent.gigachat_client import _normalize_expires_at, extract_img_file_id


def test_extract_img_file_id():
    html = '<img src="27055233-d11d-4bab-af8e-8ce1b6b33bb0" fuse="true"/>'
    assert extract_img_file_id(html) == "27055233-d11d-4bab-af8e-8ce1b6b33bb0"


def test_extract_img_file_id_none():
    assert extract_img_file_id("no image here") is None


def test_normalize_expires_at_seconds():
    # 2023-03-22T... (seconds)
    d = _normalize_expires_at(1679471442)
    assert d.tzinfo is not None
    assert isinstance(d, dt.datetime)


def test_normalize_expires_at_millis():
    d = _normalize_expires_at(1706026848841)
    assert d.tzinfo is not None
    assert isinstance(d, dt.datetime)
