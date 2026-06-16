"""Tests for insikt/collectors/honcho.py HonchoCollector.

The collector talks to a local Honcho v3 API over HTTP. We never hit the
network: ``get_json`` / ``post_json`` are monkeypatched to canned responses
keyed by URL. We assert the availability handshake, the count/queue shape of a
successful collect, the WARN escalation on a backed-up queue, the graceful
``off`` degrade, and — most importantly — that no workspace/peer *names* ever
leak into the Section payload (only counts/version/url/queue).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insikt.collectors import honcho as honcho_mod
from insikt.collectors.honcho import HonchoCollector
from insikt.collectors.base import OK, WARN

# Self-contained fixture path per the harness contract (not consumed by this
# HTTP-only collector, but kept so the module is uniform with the rest).
FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

BASE = "http://localhost:8000"

# A workspace id that, if it leaked, would be an obvious privacy violation.
SECRET_WS_ID = "ws-private-customer-name"
SECRET_PEER_NAME = "peer-alice@example.com"


def _healthy_get(url, *, token=None, timeout=4.0):
    """Canned GET router for a fully-healthy Honcho."""
    if url == f"{BASE}/health":
        return {"status": "healthy"}
    if url == f"{BASE}/openapi.json":
        return {"info": {"version": "3.7.1"}}
    if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/queue/status":
        # Mix of typed values; non-scalar values must be filtered out by the
        # collector (it only keeps int/bool/str).
        return {"pending": 3, "active": False, "worker": "w1", "detail": {"x": 1}}
    return None


def _healthy_post(url, body=None, *, token=None, timeout=4.0):
    """Canned POST router. ``items`` carry names that MUST NOT escape into data."""
    if url == f"{BASE}/v3/workspaces/list":
        return {
            "items": [{"id": SECRET_WS_ID, "name": "Top Secret Workspace"}],
            "total": 4,
        }
    if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/peers/list":
        return {
            "items": [{"id": "p1", "name": SECRET_PEER_NAME}],
            "total": 12,
        }
    if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/sessions/list":
        return {"items": [], "total": 7}
    return None


def _install(monkeypatch, get_fn, post_fn):
    monkeypatch.setattr(honcho_mod, "get_json", get_fn)
    monkeypatch.setattr(honcho_mod, "post_json", post_fn)


# --------------------------------------------------------------------------- #
# available()
# --------------------------------------------------------------------------- #

def test_available_true_when_healthy_and_workspaces_shape(monkeypatch):
    _install(monkeypatch, _healthy_get, _healthy_post)
    assert HonchoCollector().available() is True


def test_available_false_when_conf_disabled(monkeypatch):
    # Even with a perfectly healthy backend, an explicit enabled=False short
    # circuits before any HTTP call.
    def _boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("no HTTP should happen when disabled")

    _install(monkeypatch, _boom, _boom)
    c = HonchoCollector({"honcho": {"enabled": False}})
    assert c.available() is False


def test_available_false_when_health_unhealthy(monkeypatch):
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/health":
            return {"status": "down"}
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    assert HonchoCollector().available() is False


def test_available_false_when_health_unreachable(monkeypatch):
    # get_json returns None on any transport failure.
    _install(monkeypatch, lambda *a, **k: None, _healthy_post)
    assert HonchoCollector().available() is False


def test_available_false_when_workspaces_shape_wrong(monkeypatch):
    # Health is fine but the list endpoint lacks Honcho's paginated shape
    # (missing "total") — could be a different service on the port.
    def post_fn(url, body=None, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/list":
            return {"items": []}  # no "total"
        return None

    _install(monkeypatch, _healthy_get, post_fn)
    assert HonchoCollector().available() is False


def test_available_true_accepts_status_true_literal(monkeypatch):
    # The collector also accepts a boolean True health status.
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/health":
            return {"status": True}
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    assert HonchoCollector().available() is True


# --------------------------------------------------------------------------- #
# collect() — happy path
# --------------------------------------------------------------------------- #

def test_collect_happy_path_counts_and_queue(monkeypatch):
    _install(monkeypatch, _healthy_get, _healthy_post)
    sec = HonchoCollector().collect()

    assert sec.available is True
    assert sec.status == OK
    assert sec.key == "honcho"

    data = sec.data
    assert data["version"] == "3.7.1"
    assert data["base_url"] == BASE
    assert data["workspaces"] == 4
    assert data["peers"] == 12
    assert data["sessions"] == 7

    # queue keeps only scalar (int/bool/str) values; the nested dict is dropped.
    assert data["queue"] == {"pending": 3, "active": False, "worker": "w1"}
    assert "detail" not in data["queue"]

    # summary is a human string built from the counts; it should reflect them.
    assert "3.7.1" in sec.summary
    assert "12 peers" in sec.summary
    assert "7 sessions" in sec.summary


def test_collect_sessions_total_falls_back_to_item_count(monkeypatch):
    # _total uses len(items) when "total" is absent.
    def post_fn(url, body=None, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/sessions/list":
            return {"items": [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]}
        return _healthy_post(url, body, token=token, timeout=timeout)

    _install(monkeypatch, _healthy_get, post_fn)
    sec = HonchoCollector().collect()
    assert sec.data["sessions"] == 3


# --------------------------------------------------------------------------- #
# collect() — WARN on backed-up queue
# --------------------------------------------------------------------------- #

def test_collect_warn_when_queue_pending_over_100(monkeypatch):
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/queue/status":
            return {"pending": 250}
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    sec = HonchoCollector().collect()
    assert sec.status == WARN
    assert sec.data["queue"] == {"pending": 250}
    assert "queue 250" in sec.summary


def test_collect_ok_when_queue_pending_at_threshold(monkeypatch):
    # Boundary: exactly 100 is NOT a warning (strict > 100).
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/queue/status":
            return {"pending": 100}
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    sec = HonchoCollector().collect()
    assert sec.status == OK


def test_collect_warn_uses_size_when_no_pending(monkeypatch):
    # The collector falls back to queue["size"] when "pending" is absent.
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/{SECRET_WS_ID}/queue/status":
            return {"size": 500}
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    sec = HonchoCollector().collect()
    assert sec.status == WARN


# --------------------------------------------------------------------------- #
# collect() — degrade / empty
# --------------------------------------------------------------------------- #

def test_collect_off_when_not_available(monkeypatch):
    # All HTTP fails -> available() is False -> Section is the "off" degrade.
    _install(monkeypatch, lambda *a, **k: None, lambda *a, **k: None)
    sec = HonchoCollector().collect()
    assert sec.available is False
    assert sec.status == "off"
    assert sec.summary == "not reachable"
    # Even the degrade path leaks nothing but the configured URL.
    assert sec.data == {"base_url": BASE}


def test_collect_empty_workspaces_skips_per_workspace_calls(monkeypatch):
    # Healthy + reachable but zero workspaces: no primary -> peers/sessions/queue
    # stay None, and we never call the per-workspace endpoints.
    def post_fn(url, body=None, *, token=None, timeout=4.0):
        if url == f"{BASE}/v3/workspaces/list":
            return {"items": [], "total": 0}
        raise AssertionError(f"unexpected per-workspace POST: {url}")

    def get_fn(url, *, token=None, timeout=4.0):
        if url.endswith("/queue/status"):
            raise AssertionError("queue must not be polled with no workspace")
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, post_fn)
    sec = HonchoCollector().collect()
    assert sec.available is True
    assert sec.status == OK
    assert sec.data["workspaces"] == 0
    assert sec.data["peers"] is None
    assert sec.data["sessions"] is None
    assert sec.data["queue"] is None


def test_collect_version_none_when_openapi_unavailable(monkeypatch):
    def get_fn(url, *, token=None, timeout=4.0):
        if url == f"{BASE}/openapi.json":
            return None
        return _healthy_get(url, token=token, timeout=timeout)

    _install(monkeypatch, get_fn, _healthy_post)
    sec = HonchoCollector().collect()
    assert sec.data["version"] is None


# --------------------------------------------------------------------------- #
# PRIVACY invariant — only counts/version/url/queue, never names
# --------------------------------------------------------------------------- #

def test_collect_payload_has_only_count_keys(monkeypatch):
    _install(monkeypatch, _healthy_get, _healthy_post)
    sec = HonchoCollector().collect()
    assert set(sec.data.keys()) == {
        "version", "base_url", "workspaces", "peers", "sessions", "queue",
    }
    # No raw "items" list of entities is exposed.
    assert "items" not in sec.data


def test_collect_does_not_leak_workspace_or_peer_names(monkeypatch):
    _install(monkeypatch, _healthy_get, _healthy_post)
    sec = HonchoCollector().collect()

    import json as _json
    blob = _json.dumps(sec.to_dict())

    # The names/ids that exist only inside the API "items" lists must never
    # surface anywhere in the serialized Section.
    assert "Top Secret Workspace" not in blob
    assert SECRET_PEER_NAME not in blob
    assert SECRET_WS_ID not in blob
    # Sanity: the counts we DO expose are present.
    assert sec.data["peers"] == 12
