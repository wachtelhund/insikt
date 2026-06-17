"""Tests for insikt.history (persistent host-metric log) + the MCP history tool."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from insikt import history, mcp_server

NOW = datetime(2026, 6, 17, 7, 0, 0, tzinfo=timezone.utc)


def _seed(path, n=30, step_min=10):
    for i in range(n):
        history.append(
            {"t": (NOW - timedelta(minutes=(n - i) * step_min)).isoformat(),
             "temp": 40 + i, "cpu": i % 50, "mem": 60.0, "disk": 86.0},
            path,
        )


def test_append_and_load_roundtrip(tmp_path):
    p = tmp_path / "m.jsonl"
    _seed(p, n=10, step_min=1)
    rows = history.load(p)
    assert len(rows) == 10
    assert rows[0]["temp"] == 40 and rows[-1]["temp"] == 49


def test_load_window_filter(tmp_path):
    p = tmp_path / "m.jsonl"
    _seed(p, n=30, step_min=10)  # spans ~5h
    recent = history.load(p, since=NOW - timedelta(hours=1))
    assert all(history._parse_ts(r["t"]) >= NOW - timedelta(hours=1) for r in recent)
    assert 0 < len(recent) < 30


def test_load_downsample_limit(tmp_path):
    p = tmp_path / "m.jsonl"
    _seed(p, n=100, step_min=1)
    assert len(history.load(p, limit=20)) == 20


def test_summarize(tmp_path):
    p = tmp_path / "m.jsonl"
    _seed(p, n=11, step_min=1)  # temp 40..50
    s = history.summarize(history.load(p), "temp")
    assert s == {"min": 40.0, "max": 50.0, "avg": 45.0, "count": 11}
    assert history.summarize([], "temp") is None


def test_append_never_raises_on_bad_path():
    history.append({"t": "x"}, Path("/nonexistent-dir-xyz/деep/m.jsonl"))  # no exception


def test_mcp_history_impl(tmp_path):
    p = tmp_path / "m.jsonl"
    _seed(p, n=24, step_min=15)  # 6h of samples
    prof = {"server": {"history_file": str(p)}}
    out = mcp_server.history_impl("all", prof)
    assert out["count"] == 24
    assert "temp" in out["summary"] and out["summary"]["temp"]["count"] == 24
    assert len(out["series"]) <= 60 and out["series"][0]["temp"] is not None


def test_mcp_history_empty(tmp_path):
    out = mcp_server.history_impl("12h", {"server": {"history_file": str(tmp_path / "none.jsonl")}})
    assert out["count"] == 0 and "note" in out


def test_mcp_history_bad_window(tmp_path):
    out = mcp_server.history_impl("bogus", {"server": {"history_file": str(tmp_path / "m.jsonl")}})
    assert out["error"] == "bad_window"
