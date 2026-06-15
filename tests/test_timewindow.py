from datetime import datetime, timezone

import pytest

from insikt.timewindow import in_window, parse_window

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_yesterday():
    start, end = parse_window("yesterday", now=NOW)
    assert start == datetime(2026, 6, 14, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)


def test_today():
    start, end = parse_window("today", now=NOW)
    assert start == datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc)


def test_relative():
    start, end = parse_window("24h", now=NOW)
    assert start == datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def test_all():
    start, end = parse_window("all", now=NOW)
    assert start.year == 1970 and end > NOW


def test_iso_range():
    start, end = parse_window("2026-06-14/2026-06-15", now=NOW)
    assert start == datetime(2026, 6, 14, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 15, tzinfo=timezone.utc)


def test_bad_window():
    with pytest.raises(ValueError):
        parse_window("last fortnight", now=NOW)


def test_in_window_handles_z_suffix():
    start, end = parse_window("yesterday", now=NOW)
    assert in_window("2026-06-14T09:30:00Z", start, end)
    assert not in_window("2026-06-13T09:30:00Z", start, end)
    assert not in_window(None, start, end)
    assert not in_window("not-a-date", start, end)
