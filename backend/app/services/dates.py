from __future__ import annotations

import datetime as dt


def next_occurrence(month: int, day: int, *, today: dt.date) -> dt.date:
    """Return next date (>= today) with given month/day, handling year wrap."""
    year = today.year
    candidate = dt.date(year, month, day)
    if candidate < today:
        candidate = dt.date(year + 1, month, day)
    return candidate


def daterange_inclusive(start: dt.date, end: dt.date) -> set[dt.date]:
    out: set[dt.date] = set()
    cur = start
    while cur <= end:
        out.add(cur)
        cur += dt.timedelta(days=1)
    return out
