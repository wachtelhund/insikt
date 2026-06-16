"""Tests for ``insikt.mcp_server`` — the agent-facing, read-only MCP tools.

We exercise the module-level ``*_impl`` functions directly (``build_server``
just wraps these as FastMCP tools, so testing the impls covers the real
behavior without needing the MCP SDK or a live transport).

The profile disables Honcho and Home Assistant so no network call is ever made;
Hermes points at the committed fixture home. The single secret literal in that
fixture is ``"FAKE-do-not-use"`` — a core invariant of Insikt is that secret
*values* never reach any surfaced payload, so we assert it is absent from the
serialized system-state rollup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insikt import mcp_server
from insikt.collectors.base import OFF

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# Honcho + Home Assistant disabled -> no network; Hermes reads the fixture home.
PROFILE = {
    "hermes": {"home": str(FIX)},
    "honcho": {"enabled": False},
    "homeassistant": {"enabled": False},
}

# Fields a trimmed section (``_trim_section``) always carries.
_TRIM_KEYS = {"status", "available", "summary", "partial", "data"}


# --- insikt_system_state --------------------------------------------------

def test_system_state_shape():
    out = mcp_server.system_state_impl(PROFILE)

    # The whole-system rollup: meta, overall status, and per-section trims.
    assert set(("meta", "status", "sections")) <= set(out)
    assert isinstance(out["meta"], dict)
    # meta carries the standard rollup metadata.
    assert {"generated", "tool_version", "host"} <= set(out["meta"])

    sections = out["sections"]
    # full pass -> all four sources present.
    assert set(sections) == {"system", "hermes", "honcho", "homeassistant"}
    # each section is the *trimmed* form (heavy agent payload omitted here).
    for key, sec in sections.items():
        assert _TRIM_KEYS <= set(sec), f"{key} missing trim keys"
        # token-light: the trim must not smuggle the full Section's extras.
        assert "reasons" not in sec

    # disabled optionals are reported as "off".
    assert sections["honcho"]["status"] == OFF
    assert sections["homeassistant"]["status"] == OFF


def test_system_state_never_leaks_secret_values():
    """Insikt reads key NAMES, never key VALUES. The fixture's only secret
    literal is ``FAKE-do-not-use``; it must never appear in any payload the
    agent can see."""
    out = mcp_server.system_state_impl(PROFILE)
    blob = json.dumps(out, default=str)
    assert "FAKE-do-not-use" not in blob


# --- insikt_host ----------------------------------------------------------

def test_host_returns_trimmed_system_section():
    out = mcp_server.host_impl(PROFILE)

    # host_impl is the "system" section, trimmed.
    assert _TRIM_KEYS <= set(out)
    assert "status" in out and "available" in out and "data" in out
    assert isinstance(out["data"], dict)

    # it must equal the system section inside the full rollup.
    full = mcp_server.system_state_impl(PROFILE)
    assert out == full["sections"]["system"]


# --- insikt_hermes --------------------------------------------------------

def test_hermes_summary_is_the_trimmed_section():
    out = mcp_server.hermes_impl("summary", PROFILE)
    assert _TRIM_KEYS <= set(out)
    # the fixture home is present, so hermes is available and not off.
    assert out["available"] is True
    assert out["status"] != OFF


def test_hermes_hygiene_view():
    out = mcp_server.hermes_impl("hygiene", PROFILE)
    # a single-view slice returns {"<view>": <data>, "status": ...}.
    assert "hygiene" in out
    assert out.get("status") is not None
    assert isinstance(out["hygiene"], dict)
    # not an error response.
    assert "error" not in out


def test_hermes_all_view_has_summary_and_agent():
    out = mcp_server.hermes_impl("all", PROFILE)
    assert {"summary", "agent"} <= set(out)
    # summary is the trimmed section.
    assert _TRIM_KEYS <= set(out["summary"])
    # agent is the full audit payload (all five views).
    assert {"capability", "timeline", "cost", "hygiene", "graph"} <= set(out["agent"])


def test_hermes_bogus_view_is_an_error():
    out = mcp_server.hermes_impl("bogus", PROFILE)
    assert out.get("error") == "bad_view"
    assert "message" in out
    # the error enumerates the valid views (helps the agent self-correct).
    assert "summary" in out["message"]


# --- insikt_source --------------------------------------------------------

def test_source_disabled_optional_is_off():
    out = mcp_server.source_impl("honcho", PROFILE)
    # a disabled optional source is trimmed and reports "off".
    assert _TRIM_KEYS <= set(out)
    assert out["status"] == OFF
    assert out["available"] is False
    assert "error" not in out


def test_source_unknown_name_is_an_error():
    out = mcp_server.source_impl("nope", PROFILE)
    assert out.get("error") == "unknown_source"
    assert "nope" in out["message"]


def test_source_system_is_alias_for_host():
    # "system" is a valid source name and should match the host section.
    out = mcp_server.source_impl("system", PROFILE)
    assert "error" not in out
    assert out == mcp_server.host_impl(PROFILE)


# --- insikt_self_report ---------------------------------------------------

def test_self_report_proves_read_only_posture():
    out = mcp_server.self_report_impl()

    assert out["name"] == "insikt"
    assert isinstance(out["version"], str) and out["version"]

    perms = out["permissions"]
    # the exact, declared, agent-provable permission posture.
    assert perms["mode"] == "read-only"
    assert perms["internet_egress"] is False
    assert perms["shell_exec"] is False
    assert perms["writes_to_agent"] is False
    # and, for completeness, the other hard no's.
    assert perms["writes_to_host"] is False
    assert perms["reads_secret_values"] is False


def test_self_report_runs_without_a_profile():
    """self_report is pure declaration — it must not require a profile or touch
    any collector (the agent can call it before Insikt is even configured)."""
    out = mcp_server.self_report_impl()
    assert out["permissions"] is mcp_server.PERMISSIONS
