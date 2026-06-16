"""Tests for insikt.views — the pure derivations shared by the HTML report and
the MCP tools (the "single source of truth").

These run against a *real* graph built by the Hermes collector from the golden
fixture under tests/fixtures/hermes_home, so the asserts pin the actual view
shapes (key names + invariants), not a mock.

All view functions that depend on time take ``now=`` so the assertions are
deterministic regardless of when the suite runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from insikt.collectors.hermes import HermesGraphScanner
from insikt.views import capability_surface, cost_ledger, query_actions

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# Fixed clock: the fixture's actions are all on 2026-06-14, so a stable "now"
# two days later keeps rolling/relative windows deterministic.
NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)


@pytest.fixture()
def graph():
    return HermesGraphScanner(home=str(FIX)).scan()


# --- capability_surface ---------------------------------------------------


def test_capability_surface_top_level_shape(graph):
    cs = capability_surface(graph)
    assert set(cs) == {"agents", "totals"}
    assert isinstance(cs["agents"], list) and cs["agents"], "expected at least one agent"

    totals = cs["totals"]
    # totals reflect the whole graph, not just one agent.
    assert totals["agents"] == len(cs["agents"])
    assert totals["skills"] == 3  # ascii-art, backup-helper, pi-temp-watch
    assert totals["models"] >= 1
    # the fixture's .env declares four key names + config-stored secrets.
    assert totals["credential_refs"] >= 4


def test_capability_surface_agent_carries_skills(graph):
    agent = capability_surface(graph)["agents"][0]
    # identity / posture fields the report and MCP both rely on.
    assert agent["framework"] == "hermes"
    assert agent["id"].startswith("agent:hermes:")
    assert isinstance(agent["skills"], list)
    assert {"connectors", "models", "mcp_servers"} <= set(agent)

    names = {s["name"] for s in agent["skills"]}
    assert {"ascii-art", "backup-helper", "pi-temp-watch"} <= names
    # skills are sorted by name for stable rendering.
    assert [s["name"] for s in agent["skills"]] == sorted(s["name"] for s in agent["skills"])


def test_capability_surface_skill_reach_is_attributed_per_skill(graph):
    """The per-skill-reach invariant (CLAUDE.md): a tool's reach must attach to
    the skill that declared it — a shared web tool would conflate hosts. So
    pi-temp-watch reaches api.telegram.org and reads TELEGRAM_BOT_TOKEN, while
    the benign ascii-art skill reaches nothing."""
    skills = {s["name"]: s for s in capability_surface(graph)["agents"][0]["skills"]}

    pi = skills["pi-temp-watch"]
    assert "shell" in pi["tools"] and "web" in pi["tools"]
    pi_hosts = {r["value"] for r in pi["reaches"]}
    assert "api.telegram.org" in pi_hosts
    assert "TELEGRAM_BOT_TOKEN" in pi["credential_reads"]

    backup = skills["backup-helper"]
    assert "shell" in backup["tools"]
    backup_hosts = {r["value"] for r in backup["reaches"]}
    assert "exfil.evil-example.com" in backup_hosts
    # reach is NOT conflated: pi's telegram host must not leak into backup-helper.
    assert "api.telegram.org" not in backup_hosts

    benign = skills["ascii-art"]
    assert benign["tools"] == []
    assert benign["reaches"] == []
    assert benign["credential_reads"] == []


def test_capability_surface_reach_entries_have_kind_and_value(graph):
    for skill in capability_surface(graph)["agents"][0]["skills"]:
        for reach in skill["reaches"]:
            assert set(reach) == {"kind", "value"}
            assert reach["value"]


def test_capability_surface_agent_filter_narrows_and_empty_misses(graph):
    # filtering by framework returns the hermes agent...
    only = capability_surface(graph, agent="hermes")
    assert len(only["agents"]) == 1
    # ...and an unknown filter yields no agents (degrade path, totals unchanged).
    none = capability_surface(graph, agent="does-not-exist")
    assert none["agents"] == []
    assert none["totals"]["skills"] == 3


# --- cost_ledger ----------------------------------------------------------


def test_cost_ledger_shape_and_totals(graph):
    cl = cost_ledger(graph)
    assert {"models", "total_cost", "total_tokens", "agents"} <= set(cl)

    # fixture sessions: 1000 + 800 + 1200 tokens (+ a 0-token slack session that
    # is messaging, not a model_call) -> 3000 tokens, 0.02+0.015+0.03 cost.
    assert cl["total_tokens"] == 3000
    assert cl["total_cost"] == pytest.approx(0.065)

    assert isinstance(cl["models"], list) and cl["models"]
    for m in cl["models"]:
        assert {"model", "provider", "calls", "tokens", "cost"} <= set(m)


def test_cost_ledger_used_model_aggregates_and_is_listed_first(graph):
    cl = cost_ledger(graph)
    by_name = {m["model"]: m for m in cl["models"]}

    # the default openai/gpt-4o carries all three priced sessions.
    used = by_name["openai/gpt-4o"]
    assert used["calls"] == 3
    assert used["tokens"] == 3000
    assert used["cost"] == pytest.approx(0.065)
    assert used["used"] is True

    # the per-model total agrees with the grand total.
    assert sum(m["tokens"] for m in cl["models"]) == cl["total_tokens"]
    assert round(sum(m["cost"] for m in cl["models"]), 6) == cl["total_cost"]

    # used / most-expensive model sorts ahead of a configured-but-unused one.
    assert cl["models"][0]["calls"] >= cl["models"][-1]["calls"]
    assert cl["models"][0]["model"] == "openai/gpt-4o"


def test_cost_ledger_per_agent_matches_grand_total(graph):
    cl = cost_ledger(graph)
    assert len(cl["agents"]) == 1
    a = cl["agents"][0]
    assert {"agent", "calls", "tokens", "cost"} <= set(a)
    assert a["tokens"] == cl["total_tokens"]
    assert a["cost"] == cl["total_cost"]


# --- query_actions --------------------------------------------------------


def test_query_actions_all_window_nonempty_rows(graph):
    qa = query_actions(graph, window="all", now=NOW)
    assert {"actions", "count", "by_type", "total_tokens", "total_cost", "note", "range"} <= set(qa)

    assert qa["count"] == 6  # 2 cron runs + 3 priced sessions + 1 messaging session
    assert qa["count"] == len(qa["actions"])
    assert qa["actions"], "expected a non-empty action list"

    for row in qa["actions"]:
        assert {"type", "ts", "summary"} <= set(row)
        assert row["type"]
        assert row["summary"]

    # rows are newest-first.
    stamps = [r["ts"] for r in qa["actions"]]
    assert stamps == sorted(stamps, reverse=True)

    # by_type histogram agrees with the row count.
    assert sum(qa["by_type"].values()) == qa["count"]
    assert qa["by_type"]["model_call"] == 3
    assert qa["by_type"]["scheduled_run"] == 2


def test_query_actions_token_cost_aggregates_match_cost_ledger(graph):
    qa = query_actions(graph, window="all", now=NOW)
    assert qa["total_tokens"] == 3000
    assert qa["total_cost"] == pytest.approx(0.065)


def test_query_actions_backfill_note_disclosed(graph):
    """README §3.4: be honest about the reconstruction ceiling. The actions are
    backfilled, so the note must say so and name the oldest seen action."""
    qa = query_actions(graph, window="all", now=NOW)
    assert qa["note"] is not None
    assert "backfill" in qa["note"]
    assert "2026-06-14T02:00:00Z" in qa["note"]  # oldest backfilled action


def test_query_actions_type_filter(graph):
    qa = query_actions(graph, window="all", type="model_call", now=NOW)
    assert qa["count"] == 3
    assert set(qa["by_type"]) == {"model_call"}
    assert all(r["type"] == "model_call" for r in qa["actions"])


def test_query_actions_bounded_empty_window_degrades_cleanly(graph):
    """All fixture actions are on 2026-06-14; a 'today' window relative to NOW
    (2026-06-16) places none of them, so the view returns an empty-but-valid
    result rather than raising."""
    qa = query_actions(graph, window="today", now=NOW)
    assert qa["count"] == 0
    assert qa["actions"] == []
    assert qa["by_type"] == {}
    assert qa["total_tokens"] == 0
    assert qa["total_cost"] == 0.0
    # no backfilled rows are in-window, so there is nothing to disclose.
    assert qa["note"] is None


def test_query_actions_rolling_window_is_deterministic_with_now(graph):
    # a 3-day rolling window from NOW reaches back to 2026-06-13 and captures all six.
    wide = query_actions(graph, window="3d", now=NOW)
    assert wide["count"] == 6
    # a 1-hour window captures none of the 2026-06-14 actions.
    narrow = query_actions(graph, window="1h", now=NOW)
    assert narrow["count"] == 0


def test_query_actions_respects_limit(graph):
    qa = query_actions(graph, window="all", now=NOW, limit=2)
    assert len(qa["actions"]) == 2
    assert qa["truncated"] is True
    # count is the in-window total, not the truncated row count.
    assert qa["count"] == 6
