"""Tests for ``insikt.collectors.hermes.build_hermes``.

``build_hermes(profile, now)`` turns a Hermes home directory into a
``(section_dict, agent_payload)`` pair. ``section_dict`` is the at-a-glance
dashboard summary; ``agent_payload`` carries the capability/timeline/cost/
hygiene/graph views.

These tests assert against the golden fixture ``tests/fixtures/hermes_home``
(counts verified by reading the fixture), the documented payload shape, the
hard privacy invariant (the fake secret VALUE never leaks; key NAMES may), and
that raw skill bodies are stripped from the graph payload. ``now`` is fixed so
the timeline is deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from insikt.collectors.hermes import build_hermes

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# The fixture's only secret literal (see CLAUDE.md / .env header). It must never
# appear in any normalized output — only credential key NAMES may.
FAKE_SECRET = "FAKE-do-not-use"

# Deterministic clock so the timeline range is reproducible.
NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def built():
    """Build once against the golden fixture; reused by the read-only asserts."""
    return build_hermes({"hermes": {"home": str(FIX)}}, now=NOW)


# --- happy path: shape + counts -------------------------------------------
def test_returns_section_and_payload_pair(built):
    section, payload = built
    assert isinstance(section, dict)
    assert isinstance(payload, dict)


def test_section_marks_available_and_identifies_hermes(built):
    section, _ = built
    # available fixture -> the section is live, not the OFF/"not found" stub.
    assert section["available"] is True
    assert section["key"] == "hermes"
    assert section["title"] == "Hermes"
    # When available, the OFF stub's {"home": ...} data is replaced by real data.
    assert "skills" in section["data"]


def test_section_data_counts_match_fixture(built):
    section, _ = built
    data = section["data"]
    # 5 bullet lines in memories/MEMORY.md
    assert data["memories"] == 5
    # pi-temp-watch, backup-helper, ascii-art
    assert data["skills"] == 3
    # default openai/gpt-4o + anthropic/claude-opus-4-8 (cron); morning-brief's
    # gpt-4o merges into the default model node by deterministic id.
    assert data["models"] == 2
    assert data["default_model"] == "openai/gpt-4o"
    # 2 cron jobs + 4 session ledger entries
    assert data["actions"] == 6
    # _config_version: 42
    assert data["config_version"] == 42


def test_section_findings_present_and_well_formed(built):
    section, _ = built
    findings = section["data"]["findings"]
    assert isinstance(findings, dict)
    # The exfil/posture fixture is engineered to surface CRITICALs; hygiene must
    # never return "just a number" — it is a severity-keyed breakdown.
    assert findings.get("critical", 0) >= 1
    # Every recorded severity must be a non-negative integer.
    assert all(isinstance(v, int) and v >= 0 for v in findings.values())
    total = sum(findings.values())
    assert total >= findings["critical"] >= 1


def test_section_status_reflects_critical_findings(built):
    section, _ = built
    # With critical findings present, status must escalate to "crit" (not ok/warn).
    assert section["data"]["findings"].get("critical", 0) >= 1
    assert section["status"] == "crit"


# --- payload shape ---------------------------------------------------------
def test_payload_has_the_five_documented_views(built):
    _, payload = built
    assert set(payload.keys()) == {"capability", "timeline", "cost", "hygiene", "graph"}
    # graph is a {nodes, edges} container shared with the report.
    assert set(payload["graph"]).issuperset({"nodes", "edges"})
    assert isinstance(payload["graph"]["nodes"], list)
    assert isinstance(payload["graph"]["edges"], list)


# --- determinism: timeline keyed on the injected `now` ---------------------
def test_timeline_is_deterministic_for_fixed_now(built):
    _, payload = built
    tl = payload["timeline"]
    assert tl["window"] == "all"
    # For the unbounded window, parse_window returns (epoch, now + 1 day).
    assert tl["range"]["start"] == datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat()
    assert tl["range"]["end"] == (NOW + timedelta(days=1)).isoformat()
    # All 6 backfilled actions fall inside the window.
    assert tl["count"] == 6
    assert tl["by_type"] == {"scheduled_run": 2, "message_sent": 1, "model_call": 3}
    # Token/cost totals are derived from the session ledger (deterministic).
    assert tl["total_tokens"] == 3000
    assert tl["total_cost"] == pytest.approx(0.065)


def test_timeline_independent_of_now_for_action_membership():
    # Re-building with a different clock shifts only the window end, never the
    # set of in-window actions (they all carry fixed June-2026 timestamps).
    later = datetime(2027, 1, 1, tzinfo=timezone.utc)
    _, payload = build_hermes({"hermes": {"home": str(FIX)}}, now=later)
    tl = payload["timeline"]
    assert tl["range"]["end"] == (later + timedelta(days=1)).isoformat()
    assert tl["count"] == 6  # same actions regardless of `now`


# --- CRITICAL privacy invariant -------------------------------------------
def test_no_secret_value_in_section(built):
    section, _ = built
    blob = json.dumps(section)
    assert FAKE_SECRET not in blob


def test_no_secret_value_in_payload(built):
    _, payload = built
    blob = json.dumps(payload)
    assert FAKE_SECRET not in blob


def test_credential_key_names_may_appear_but_not_values(built):
    _, payload = built
    blob = json.dumps(payload)
    # Names are allowed (they are CredentialRef node names, not material)...
    assert "ANTHROPIC_API_KEY" in blob
    # ...but the corresponding value must be absent everywhere.
    assert FAKE_SECRET not in blob


# --- skill bodies are stripped from the graph payload ----------------------
def _skill_nodes(payload):
    return [n for n in payload["graph"]["nodes"] if n.get("type") == "skill"]


def test_graph_has_three_skill_nodes(built):
    _, payload = built
    assert len(_skill_nodes(built[1])) == 3


def test_no_skill_node_carries_a_raw_body_prop(built):
    _, payload = built
    for node in _skill_nodes(payload):
        # Body is dropped before the payload is built (privacy + size). It must
        # not be a top-level key nor hide inside the nested props dict.
        assert "body" not in node
        assert "body" not in (node.get("props") or {})


# --- degrade path: missing home -------------------------------------------
def test_missing_home_returns_unavailable_stub_and_no_payload(tmp_path):
    section, payload = build_hermes({"hermes": {"home": str(tmp_path / "nope")}}, now=NOW)
    # A non-existent home is not a crash: it degrades to an OFF stub with no
    # agent payload at all.
    assert section["available"] is False
    assert section["status"] == "off"
    assert payload is None
    # Even the degraded stub must never leak a secret value.
    assert FAKE_SECRET not in json.dumps(section)
