"""Tests for ``insikt.state.collect_state`` — the single whole-system contract.

These exercise the orchestration in ``state.py`` (assembling the system +
hermes + honcho + homeassistant sections, the status rollup, and the
``fast_only`` short-circuit), not the individual collectors. Honcho and Home
Assistant are explicitly disabled in the profile so the test never touches the
network. A fixed ``now`` (a ``datetime``, which is what the hermes timeline
parser requires) makes ``meta.generated`` deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from insikt.collectors.base import OFF
from insikt.state import _RANK, collect_state

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# A fixed instant so meta.generated and the hermes timeline window are stable.
NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

# Honcho + Home Assistant disabled -> no network, both sections land "off".
PROFILE = {
    "hermes": {"home": str(FIX)},
    "honcho": {"enabled": False},
    "homeassistant": {"enabled": False},
}


def _worst_live_status(sections: dict) -> str:
    """Reimplement the rollup rule the way the docstring states it: the worst
    status among sections that are not ``off`` (ties broken by severity rank)."""
    live = [s["status"] for s in sections.values() if s["status"] != OFF]
    if not live:
        return "ok"
    return max(live, key=lambda s: _RANK.get(s, 0))


# --- full pass ----------------------------------------------------------------

def test_full_pass_meta_and_sections():
    state = collect_state(PROFILE, now=NOW)

    # meta carries the four required keys.
    meta = state["meta"]
    assert set(("generated", "tool_version", "host", "refresh")) <= set(meta)
    assert meta["generated"] == NOW  # passed-in now flows straight through
    assert isinstance(meta["tool_version"], str) and meta["tool_version"]
    assert isinstance(meta["host"], str) and meta["host"]
    # default refresh when no [server] config is present.
    assert meta["refresh"] == 5

    # all four sections present in a full pass.
    sections = state["sections"]
    assert set(sections) == {"system", "hermes", "honcho", "homeassistant"}
    for sec in sections.values():
        # every section is a serialized Section dict.
        assert {"key", "title", "available", "status", "summary"} <= set(sec)

    # top-level status + the agent audit payload exist.
    assert "status" in state
    assert state["agent"] is not None


def test_full_pass_agent_payload_is_the_hermes_audit():
    state = collect_state(PROFILE, now=NOW)
    agent = state["agent"]
    # build_hermes returns the capability/timeline/cost/hygiene/graph views.
    assert isinstance(agent, dict)
    assert {"capability", "timeline", "cost", "hygiene", "graph"} <= set(agent)


def test_disabled_optionals_are_off():
    state = collect_state(PROFILE, now=NOW)
    sections = state["sections"]

    for key in ("honcho", "homeassistant"):
        sec = sections[key]
        assert sec["status"] == OFF, f"{key} should be off when disabled"
        assert sec["available"] is False
        assert sec["summary"] == "disabled"

    # the live hermes home is found, so its section is available (not off).
    assert sections["hermes"]["available"] is True
    assert sections["hermes"]["status"] != OFF


def test_status_rollup_ignores_off_and_reflects_worst_live():
    state = collect_state(PROFILE, now=NOW)
    sections = state["sections"]

    # the rollup equals the worst *live* (non-off) section status.
    assert state["status"] == _worst_live_status(sections)

    # disabled optionals must not influence the rollup: their "off" status
    # ranks 0 and is filtered out entirely, so the result is driven purely by
    # the system + hermes sections.
    live_statuses = {k: v["status"] for k, v in sections.items() if v["status"] != OFF}
    assert "honcho" not in live_statuses
    assert "homeassistant" not in live_statuses
    # rollup is at least as severe as the live hermes section.
    assert _RANK.get(state["status"], 0) >= _RANK.get(sections["hermes"]["status"], 0)


# --- fast_only short-circuit --------------------------------------------------

def test_fast_only_returns_system_only_and_no_agent():
    state = collect_state(PROFILE, now=NOW, fast_only=True)

    # only the cheap host section is collected.
    assert list(state["sections"]) == ["system"]
    # no hermes/honcho/homeassistant work was done.
    for key in ("hermes", "honcho", "homeassistant"):
        assert key not in state["sections"]

    # no agent audit payload in the fast path.
    assert state["agent"] is None

    # meta is still populated with the deterministic now.
    assert state["meta"]["generated"] == NOW
    assert state["meta"]["tool_version"]

    # rollup is just the system section's status (the only live one).
    assert state["status"] == state["sections"]["system"]["status"]


def test_fast_only_and_full_agree_on_the_system_section():
    """The system section should be identical content-wise whether collected on
    its own (fast) or as part of a full pass — the fast path is a strict
    subset, not a different code path for the host metrics."""
    fast = collect_state(PROFILE, now=NOW, fast_only=True)
    full = collect_state(PROFILE, now=NOW)

    fs = fast["sections"]["system"]
    full_sys = full["sections"]["system"]
    # same key/title/availability; both come from SystemCollector.safe_collect.
    assert fs["key"] == full_sys["key"] == "system"
    assert fs["title"] == full_sys["title"]
    assert fs["available"] == full_sys["available"]
