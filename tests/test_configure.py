"""Tests for insikt/configure.py — the AI-first profile authoring/validation path.

``configure`` proposes, describes, validates, and saves the system *profile*.
Several of its helpers (``describe``, ``validate``, ``detect_profile``) end up
probing the optional HTTP collectors (Honcho, Home Assistant) on localhost. We
never hit the network: ``get_json`` / ``post_json`` on those collector modules
are monkeypatched to ``None`` so the probes deterministically report
"unreachable". The Hermes home is pointed at the in-repo fixture, so the layout
digest / validation read real files without touching the user's ``~/.hermes`` or
``~/.insikt``.

Covered:
  * ``_extract_profile`` parses a fenced ```yaml block into a mapping, falls back
    to bare YAML, and returns ``None`` for junk (non-mapping or invalid YAML).
  * ``describe`` returns the agent-facing payload with all five sections, and the
    fixture's only secret literal ("FAKE-do-not-use") is redacted out of the
    JSON-serialized digest (the contract: never surface secret values).
  * ``detect_profile`` returns a full profile with every section key and toggles
    the optional sources off when nothing is reachable.
  * ``validate`` runs the collectors and reports overall/host/sections.
  * ``save_profile_to`` writes valid YAML that round-trips via ``yaml.safe_load``
    (to a tmp path — never the real ~/.insikt/profile.yaml).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from insikt import configure as C
from insikt.collectors import homeassistant as ha_mod
from insikt.collectors import honcho as honcho_mod

# Self-contained fixture path per the harness contract.
FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# The fixture's ONLY secret literal (see config.yaml / .env). If this ever
# escapes into a digest/profile payload, redaction is broken.
FAKE_SECRET = "FAKE-do-not-use"


@pytest.fixture
def offline(monkeypatch):
    """Make the optional-collector reachability probes deterministic + offline.

    ``_reachability`` constructs HonchoCollector / HomeAssistantCollector and
    calls ``.available()``, which goes through ``get_json`` / ``post_json``.
    Patching them to ``None`` means every probe reports "not reachable" without
    any real socket. We also clear HA_TOKEN so HA never appears configured.
    """
    monkeypatch.setattr(honcho_mod, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(honcho_mod, "post_json", lambda *a, **k: None)
    monkeypatch.setattr(ha_mod, "get_json", lambda *a, **k: None)
    monkeypatch.delenv("HA_TOKEN", raising=False)


@pytest.fixture
def fixture_profile():
    """A complete profile whose Hermes home is the in-repo fixture and whose
    HA token sources point nowhere (so HA stays unconfigured)."""
    return {
        "system": {"enabled": True, "temp_warn": 70, "temp_crit": 80},
        "hermes": {"home": str(FIX)},
        "honcho": {"enabled": "auto", "base_url": "http://localhost:8000"},
        "homeassistant": {
            "enabled": "auto",
            "base_url": "http://localhost:8123",
            "token_file": str(FIX / "no_such_ha_token.txt"),
            "token_env": "HA_TOKEN_DOES_NOT_EXIST",
        },
        "server": {"bind": "0.0.0.0", "port": 8420, "refresh": 5},
    }


# --- _extract_profile -----------------------------------------------------
def test_extract_profile_fenced_yaml_returns_mapping():
    text = (
        "Sure, here is the profile for your host:\n\n"
        "```yaml\n"
        "hermes:\n"
        "  home: ~/.hermes\n"
        "system:\n"
        "  enabled: true\n"
        "  temp_warn: 65\n"
        "```\n\n"
        "Apply it with `insikt configure --apply`."
    )
    out = C._extract_profile(text)
    assert out == {
        "hermes": {"home": "~/.hermes"},
        "system": {"enabled": True, "temp_warn": 65},
    }


def test_extract_profile_plain_yaml_tag_fence():
    # The fence regex also accepts a bare ```yml tag (no language at all works too).
    out = C._extract_profile("```yml\nhoncho:\n  enabled: false\n```")
    assert out == {"honcho": {"enabled": False}}


def test_extract_profile_bare_mapping_without_fence():
    # No fence at all: the whole blob is parsed as YAML; a mapping passes through.
    out = C._extract_profile("hermes:\n  home: /opt/hermes\n")
    assert out == {"hermes": {"home": "/opt/hermes"}}


def test_extract_profile_rejects_non_mapping():
    # A YAML *list* and a bare scalar are valid YAML but not a profile mapping.
    assert C._extract_profile("```yaml\n- a\n- b\n```") is None
    assert C._extract_profile("just a sentence, no yaml here") is None


def test_extract_profile_rejects_invalid_yaml():
    # Malformed YAML must degrade to None, never raise.
    assert C._extract_profile("```yaml\nkey: : :\n  - [unterminated\n```") is None


# --- describe -------------------------------------------------------------
def test_describe_payload_shape(offline, fixture_profile):
    d = C.describe(fixture_profile)
    assert set(d.keys()) == {
        "current_profile",
        "profile_schema",
        "hermes_layout",
        "reachability",
        "instructions",
    }
    # The profile we passed is echoed back verbatim as current_profile.
    assert d["current_profile"] == fixture_profile
    # Schema documents exactly the five overridable sections.
    assert set(d["profile_schema"].keys()) == {
        "system",
        "hermes",
        "honcho",
        "homeassistant",
        "server",
    }
    # Reachability probes both optional sources; offline => both unreachable.
    assert set(d["reachability"].keys()) == {"honcho", "homeassistant"}
    assert d["reachability"]["honcho"]["reachable"] is False
    assert d["reachability"]["homeassistant"]["reachable"] is False
    # The layout digest actually walked the fixture home.
    layout = d["hermes_layout"]
    assert layout["exists"] is True
    assert layout["home"] == str(FIX)
    assert "config.yaml" in layout["samples"]
    assert isinstance(d["instructions"], str) and d["instructions"]


def test_describe_redacts_secret_values(offline, fixture_profile):
    """Contract (README §1, §8.2): never surface secret *values*. The fixture's
    config.yaml holds `api_key: FAKE-do-not-use`; the digest samples that file,
    so the secret must be [REDACTED] before it reaches the agent payload."""
    import json

    d = C.describe(fixture_profile)
    blob = json.dumps(d, default=str)
    assert FAKE_SECRET not in blob
    # Sanity: the config.yaml sample is present (so the redaction is the reason
    # the secret is gone, not the file simply being absent from the digest).
    sample = d["hermes_layout"]["samples"]["config.yaml"]
    assert "api_key" in sample  # the KEY name is kept ...
    assert FAKE_SECRET not in sample  # ... but the VALUE is redacted
    assert "[REDACTED]" in sample


# --- detect_profile -------------------------------------------------------
def test_detect_profile_sections_and_offline_toggles(offline, monkeypatch):
    # Force the heuristic to use the fixture as the Hermes home.
    monkeypatch.setenv("HERMES_HOME", str(FIX))
    prof = C.detect_profile()
    assert set(prof.keys()) == {
        "system",
        "hermes",
        "honcho",
        "homeassistant",
        "server",
    }
    # The detected home is the reachable directory we pointed it at.
    assert prof["hermes"]["home"] == str(FIX)
    # Nothing reachable offline => optional sources detected as disabled (bool).
    assert prof["honcho"]["enabled"] is False
    assert prof["homeassistant"]["enabled"] is False


# --- validate -------------------------------------------------------------
def test_validate_shape_and_sections(offline, fixture_profile):
    val = C.validate(fixture_profile)
    assert set(val.keys()) == {"overall", "host", "sections"}
    # All four collectors report a section.
    assert set(val["sections"].keys()) == {
        "system",
        "hermes",
        "honcho",
        "homeassistant",
    }
    # Host is a non-empty string; overall is a known status level.
    assert isinstance(val["host"], str) and val["host"]
    assert val["overall"] in {"ok", "warn", "crit", "off"}
    # Hermes reads the fixture, so it is available; each section carries the
    # documented per-section fields.
    hermes = val["sections"]["hermes"]
    assert hermes["available"] is True
    for sec in val["sections"].values():
        assert set(sec.keys()) == {
            "status",
            "available",
            "summary",
            "partial",
            "reasons",
        }
        assert isinstance(sec["reasons"], list)
    # Offline optional sources degrade to off/unavailable rather than raising.
    assert val["sections"]["honcho"]["available"] is False
    assert val["sections"]["homeassistant"]["available"] is False


def test_validate_missing_hermes_home_degrades(offline):
    """A non-existent Hermes home must not raise — validation still returns a
    well-formed report (the empty/degrade path)."""
    prof = {
        "system": {"enabled": True},
        "hermes": {"home": str(FIX / "definitely_not_here")},
        "honcho": {"enabled": "auto"},
        "homeassistant": {"enabled": "auto", "token_env": "NOPE", "token_file": "/nope"},
        "server": {},
    }
    val = C.validate(prof)
    assert set(val.keys()) == {"overall", "host", "sections"}
    assert "hermes" in val["sections"]
    # It should report unavailable or partial, never crash.
    h = val["sections"]["hermes"]
    assert h["available"] is False or h["partial"] is True


# --- save_profile_to ------------------------------------------------------
def test_save_profile_to_round_trips(tmp_path, fixture_profile):
    dest = tmp_path / "p.yaml"
    returned = C.save_profile_to(fixture_profile, dest)
    assert returned == dest
    assert dest.exists()
    loaded = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert loaded == fixture_profile


def test_save_profile_to_creates_parent_dirs(tmp_path, fixture_profile):
    # The helper mkdir(parents=True)s — a nested path must be created, and we
    # write to a tmp dir, NEVER the real ~/.insikt.
    dest = tmp_path / "nested" / "deeper" / "profile.yaml"
    C.save_profile_to(fixture_profile, dest)
    assert dest.is_file()
    assert yaml.safe_load(dest.read_text(encoding="utf-8")) == fixture_profile
