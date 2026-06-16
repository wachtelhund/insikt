"""Tests for insikt/collectors/homeassistant.py — HomeAssistantCollector.

The collector talks to a local Home Assistant REST API. We never let it touch
the network: ``insikt.collectors.homeassistant.get_json`` is monkeypatched with a
fake router that returns canned payloads keyed by URL. The token comes from the
``HA_TOKEN`` env var (or a token_file in the profile).

The load-bearing invariant under test is PRIVACY: the collector must surface only
domain *prefixes* and integer counts, never a full ``entity_id`` ("sensor.foo"),
never latitude/longitude/location/identifying fields — even though the canned API
responses contain all of those.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from insikt.collectors import homeassistant as ha_mod
from insikt.collectors.homeassistant import HomeAssistantCollector

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

BASE = "http://localhost:8123"

# A /api/states payload deliberately stuffed with location/identity fields and
# full entity_ids — none of which may leak into the Section.
STATES = [
    {
        "entity_id": "sensor.living_room_temperature",
        "state": "21.4",
        "attributes": {"friendly_name": "Living Room Temp", "unit_of_measurement": "C"},
    },
    {
        "entity_id": "sensor.kitchen_humidity",
        "state": "55",
        "attributes": {"friendly_name": "Kitchen Humidity"},
    },
    {
        "entity_id": "light.bedroom_lamp",
        "state": "on",
        "attributes": {"friendly_name": "Bedroom Lamp"},
    },
    {
        "entity_id": "device_tracker.demo_phone",
        "state": "home",
        "attributes": {
            "latitude": 11.111111,
            "longitude": 22.222222,
            "gps_accuracy": 10,
            "source_type": "gps",
            "friendly_name": "Demo Phone",
        },
    },
    # malformed rows must be tolerated and ignored by the domain counter.
    {"state": "weird"},          # no entity_id
    "not-a-dict",                 # not even a dict
    {"entity_id": "noseparator"}, # no '.' -> not counted as a domain
]

CONFIG_RUNNING = {
    "version": "2024.6.1",
    "state": "RUNNING",
    "components": ["sensor", "light", "device_tracker", "http", "api"],
    "recovery_mode": False,
    "safe_mode": False,
    # privacy-sensitive fields the collector must NOT propagate (all fake):
    "latitude": 11.1111,
    "longitude": 22.2222,
    "location_name": "Home",
    "time_zone": "Etc/UTC",
    "internal_url": "http://homeassistant.local:8123",
    "external_url": "https://example.duckdns.org",
}

ROOT_OK = {"message": "API running."}


def _router(config, states, *, root=ROOT_OK):
    """Build a fake get_json keyed on the URL suffix."""

    def fake_get_json(url, *, token=None, timeout=4.0):
        assert token == "x", "collector must pass the loaded token through"
        if url == f"{BASE}/api/":
            return root
        if url == f"{BASE}/api/config":
            return config
        if url == f"{BASE}/api/states":
            return states
        raise AssertionError(f"unexpected URL requested: {url}")

    return fake_get_json


@pytest.fixture
def with_token(monkeypatch):
    monkeypatch.setenv("HA_TOKEN", "x")
    return monkeypatch


# --------------------------------------------------------------------------- #
# available()
# --------------------------------------------------------------------------- #

def test_available_true_with_token_and_message(with_token, monkeypatch):
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, STATES))
    c = HomeAssistantCollector()
    assert c.token == "x"
    assert c.available() is True


def test_available_false_without_token(monkeypatch):
    monkeypatch.delenv("HA_TOKEN", raising=False)
    # Point token_file at a path that does not exist so no token is found.
    profile = {"homeassistant": {"token_file": str(FIX / "no_such_ha_token.txt")}}
    c = HomeAssistantCollector(profile)
    assert c.token is None
    # available() must short-circuit on a missing token and never hit the network.
    def boom(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("get_json must not be called without a token")
    monkeypatch.setattr(ha_mod, "get_json", boom)
    assert c.available() is False


def test_available_false_when_root_missing_message(with_token, monkeypatch):
    # /api/ reachable but the body is not the HA banner -> not HA.
    monkeypatch.setattr(ha_mod, "get_json",
                        _router(CONFIG_RUNNING, STATES, root={"ok": True}))
    c = HomeAssistantCollector()
    assert c.available() is False


def test_available_false_when_root_unreachable(with_token, monkeypatch):
    # get_json returns None on any transport failure.
    monkeypatch.setattr(ha_mod, "get_json",
                        _router(CONFIG_RUNNING, STATES, root=None))
    c = HomeAssistantCollector()
    assert c.available() is False


def test_available_false_when_disabled(with_token, monkeypatch):
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, STATES))
    c = HomeAssistantCollector({"homeassistant": {"enabled": False}})
    assert c.token == "x"
    assert c.available() is False


# --------------------------------------------------------------------------- #
# collect() — happy path + per-domain counts
# --------------------------------------------------------------------------- #

def test_collect_happy_path_builds_full_section(with_token, monkeypatch):
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, STATES))
    c = HomeAssistantCollector()
    sec = c.collect()

    assert sec.available is True
    assert sec.key == "homeassistant"
    assert sec.title == "Home Assistant"
    assert sec.status == "ok"  # state RUNNING, no recovery/safe mode

    d = sec.data
    assert d["version"] == "2024.6.1"
    assert d["state"] == "RUNNING"
    assert d["components"] == 5
    # 4 well-formed entity_ids contain a '.', plus one bad dict, one str, one
    # no-separator row -> n_entities counts the WHOLE list length.
    assert d["entities"] == len(STATES)
    assert d["recovery_mode"] is False
    assert d["safe_mode"] is False
    assert d["base_url"] == BASE

    # Per-domain counts derived only from the prefix before the first '.'.
    assert d["domains"] == {"sensor": 2, "light": 1, "device_tracker": 1}

    # summary mentions the human bits.
    assert "2024.6.1" in sec.summary
    assert "RUNNING" in sec.summary


def test_collect_domains_sorted_by_count_descending(with_token, monkeypatch):
    states = [
        {"entity_id": "light.a"},
        {"entity_id": "light.b"},
        {"entity_id": "light.c"},
        {"entity_id": "sensor.x"},
        {"entity_id": "binary_sensor.y"},
    ]
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, states))
    c = HomeAssistantCollector()
    sec = c.collect()
    assert sec.data["domains"] == {"light": 3, "sensor": 1, "binary_sensor": 1}
    # the dominant domain comes first.
    assert list(sec.data["domains"])[0] == "light"


# --------------------------------------------------------------------------- #
# collect() — status escalation
# --------------------------------------------------------------------------- #

def test_collect_warn_when_state_not_running(with_token, monkeypatch):
    cfg = dict(CONFIG_RUNNING, state="STARTING")
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    assert sec.status == "warn"
    assert sec.data["state"] == "STARTING"


def test_collect_crit_when_recovery_mode(with_token, monkeypatch):
    cfg = dict(CONFIG_RUNNING, recovery_mode=True)
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    assert sec.status == "crit"
    assert sec.data["recovery_mode"] is True


def test_collect_crit_when_safe_mode(with_token, monkeypatch):
    cfg = dict(CONFIG_RUNNING, safe_mode=True)
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    assert sec.status == "crit"
    assert sec.data["safe_mode"] is True


def test_collect_crit_overrides_warn(with_token, monkeypatch):
    # Non-running AND in safe mode -> the worse status (crit) wins.
    cfg = dict(CONFIG_RUNNING, state="STARTING", safe_mode=True)
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    assert sec.status == "crit"


# --------------------------------------------------------------------------- #
# collect() — degrade paths
# --------------------------------------------------------------------------- #

def test_collect_off_without_token(monkeypatch):
    monkeypatch.delenv("HA_TOKEN", raising=False)
    profile = {"homeassistant": {"token_file": str(FIX / "no_such_ha_token.txt")}}
    c = HomeAssistantCollector(profile)
    assert c.token is None
    def boom(*a, **k):  # pragma: no cover - must not be called
        raise AssertionError("get_json must not be called without a token")
    monkeypatch.setattr(ha_mod, "get_json", boom)
    sec = c.collect()
    assert sec.available is False
    assert sec.status == "off"
    assert sec.summary == "no token"
    assert sec.data == {"base_url": BASE}


def test_collect_off_when_root_unreachable(with_token, monkeypatch):
    monkeypatch.setattr(ha_mod, "get_json",
                        _router(CONFIG_RUNNING, STATES, root=None))
    sec = HomeAssistantCollector().collect()
    assert sec.available is False
    assert sec.status == "off"
    assert sec.summary == "not reachable"
    assert sec.data == {"base_url": BASE}


def test_collect_tolerates_missing_config_and_states(with_token, monkeypatch):
    # /api/ ok, but /api/config and /api/states are unreachable (None).
    def fake_get_json(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/api/":
            return ROOT_OK
        return None

    monkeypatch.setattr(ha_mod, "get_json", fake_get_json)
    sec = HomeAssistantCollector().collect()
    # No exception; degrades to an available-but-empty Section.
    assert sec.available is True
    assert sec.status == "ok"
    d = sec.data
    assert d["version"] is None
    assert d["state"] is None
    assert d["components"] is None
    assert d["entities"] is None
    assert d["domains"] == {}
    # falls back to a non-empty summary.
    assert sec.summary == "reachable"


def test_collect_components_none_when_not_a_list(with_token, monkeypatch):
    cfg = dict(CONFIG_RUNNING, components="sensor,light")  # not a list
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    assert sec.data["components"] is None


# --------------------------------------------------------------------------- #
# PRIVACY — the load-bearing invariant
# --------------------------------------------------------------------------- #

# Substrings that, if present anywhere in the serialized Section, prove a leak.
FORBIDDEN_SUBSTRINGS = [
    "living_room_temperature",  # entity object name
    "kitchen_humidity",
    "bedroom_lamp",
    "demo_phone",
    "sensor.",                  # any full entity_id
    "light.",
    "device_tracker.",
    "friendly_name",
    "Living Room Temp",
    "Bedroom Lamp",
    "11.111111", "22.222222",   # phone GPS coords (fake)
    "Etc/UTC",
    "homeassistant.local",      # internal_url
    "duckdns",                  # external_url
    # NB: location_name's value here is "Home", which collides with the fixed
    # title "Home Assistant" — so we assert that leak via the key-walk below
    # (FORBIDDEN_KEYS includes "location_name"/"location") rather than a substring.
]

FORBIDDEN_KEYS = [
    "latitude", "longitude", "location", "location_name",
    "gps_accuracy", "internal_url", "external_url", "time_zone",
    "friendly_name", "attributes", "entity_id",
]


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def test_privacy_no_entity_ids_or_location_anywhere(with_token, monkeypatch):
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, STATES))
    sec = HomeAssistantCollector().collect()

    serialized = json.dumps(sec.to_dict())

    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in serialized, (
            f"privacy leak: {needle!r} appeared in the Section: {serialized}"
        )

    # No identifying key anywhere in the nested data structure.
    all_keys = set(_walk_keys(sec.to_dict()))
    leaked = all_keys & set(FORBIDDEN_KEYS)
    assert not leaked, f"privacy leak: forbidden keys present: {leaked}"

    # The ONLY keys inside `domains` are bare domain prefixes (no dots),
    # and the ONLY values are integer counts.
    for dom, count in sec.data["domains"].items():
        assert "." not in dom, f"domain key looks like an entity_id: {dom!r}"
        assert isinstance(count, int)


def test_privacy_distinctive_location_name_not_leaked(with_token, monkeypatch):
    # Use a location_name that cannot collide with the title/key, so a substring
    # check is unambiguous proof the value is dropped.
    cfg = dict(CONFIG_RUNNING, location_name="Sample-Home-Location-XYZ")
    monkeypatch.setattr(ha_mod, "get_json", _router(cfg, STATES))
    sec = HomeAssistantCollector().collect()
    serialized = json.dumps(sec.to_dict())
    assert "Sample-Home-Location-XYZ" not in serialized
    assert "location_name" not in set(_walk_keys(sec.to_dict()))


def test_privacy_domains_are_prefixes_only_minimal_example(with_token, monkeypatch):
    # Mirrors the prompt's minimal example: sensor.a + light.b -> {sensor:1, light:1}
    states = [{"entity_id": "sensor.a"}, {"entity_id": "light.b"}]
    monkeypatch.setattr(ha_mod, "get_json", _router(CONFIG_RUNNING, states))
    sec = HomeAssistantCollector().collect()
    assert sec.data["domains"] == {"sensor": 1, "light": 1}
    serialized = json.dumps(sec.to_dict())
    assert "sensor.a" not in serialized
    assert "light.b" not in serialized
