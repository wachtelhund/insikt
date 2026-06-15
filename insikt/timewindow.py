"""Parse the ``window`` argument used by the timeline and ``insikt_query_actions``.

Accepts: ``today``, ``yesterday``, ``7d``/``24h``/``30m`` (rolling), ``all``, or an
ISO range ``<start>/<end>``. Returns a ``(start, end)`` pair of timezone-aware
datetimes (end exclusive). ``now`` is injectable so tests are deterministic.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

_REL = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_UNIT = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def _parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_window(window: Optional[str], now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    w = (window or "all").strip().lower()

    if w in ("all", "", "*"):
        return datetime(1970, 1, 1, tzinfo=timezone.utc), now + timedelta(days=1)

    if w == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    if w == "yesterday":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        return start, start + timedelta(days=1)

    m = _REL.match(w)
    if m:
        qty, unit = int(m.group(1)), m.group(2).lower()
        return now - timedelta(**{_UNIT[unit]: qty}), now + timedelta(seconds=1)

    if "/" in (window or ""):
        a, b = window.split("/", 1)
        return _parse_iso(a), _parse_iso(b)

    raise ValueError(
        f"unrecognized window {window!r}; use today|yesterday|<N>[smhdw]|all|<ISO>/<ISO>"
    )


def in_window(ts: Optional[str], start: datetime, end: datetime) -> bool:
    if not ts:
        return False
    try:
        dt = _parse_iso(ts)
    except (ValueError, TypeError):
        return False
    return start <= dt < end
