"""Tests for ``insikt.server`` — the read-only live dashboard web server.

We exercise the HTTP surface end-to-end against a real (but loopback, ephemeral
port) ``ThreadingHTTPServer`` built from ``_make_handler``. Crucially we build a
``StateCache`` *without* calling ``.run()`` so no background refresh threads are
started — the state collected in ``__init__`` is fixed and deterministic, which
keeps the assertions stable and the test fast.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from insikt.server import StateCache, _make_handler

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# Optional collectors explicitly disabled so the test never touches the network
# or a real Home Assistant / Honcho; refresh is irrelevant (we never .run()).
PROFILE = {
    "hermes": {"home": str(FIX)},
    "honcho": {"enabled": False},
    "homeassistant": {"enabled": False},
    "server": {"refresh": 5},
}


def _make_cache() -> StateCache:
    return StateCache(dict(PROFILE))


class _Server:
    """Spin up the handler on 127.0.0.1:0 and tear it down deterministically."""

    def __init__(self, cache: StateCache):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(cache))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self) -> "_Server":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self._thread.join(timeout=5)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"


def _get(server: _Server, path: str):
    with urllib.request.urlopen(server.url(path), timeout=5) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


# --------------------------------------------------------------------------- #
# Cache construction (no background threads)
# --------------------------------------------------------------------------- #

def test_cache_constructs_without_threads():
    """Building the cache must not spawn refresh loops (we never call .run())."""
    before = threading.active_count()
    cache = _make_cache()
    # No new long-lived threads should appear just from constructing the cache.
    assert threading.active_count() == before
    # The stop event must be unset — .run() was never called.
    assert not cache._stop.is_set()


def test_cache_state_shape():
    cache = _make_cache()
    st = cache.state()
    assert "sections" in st
    assert "system" in st["sections"]
    # Hermes was pointed at the fixture, so it should be present and available.
    assert "hermes" in st["sections"]
    assert st["sections"]["hermes"].get("available") is True
    # host() is a convenience accessor onto the system section.
    assert cache.host() == st["sections"]["system"]


# --------------------------------------------------------------------------- #
# HTTP surface — happy paths
# --------------------------------------------------------------------------- #

def test_index_returns_html_dashboard():
    with _Server(_make_cache()) as srv:
        status, ctype, body = _get(srv, "/")
    assert status == 200
    assert "text/html" in ctype
    text = body.decode("utf-8")
    assert "Insikt" in text


def test_index_html_alias():
    with _Server(_make_cache()) as srv:
        status, ctype, body = _get(srv, "/index.html")
    assert status == 200
    assert "text/html" in ctype
    assert "Insikt" in body.decode("utf-8")


def test_api_state_returns_json_with_sections():
    with _Server(_make_cache()) as srv:
        status, ctype, body = _get(srv, "/api/state")
    assert status == 200
    assert "application/json" in ctype
    payload = json.loads(body)
    assert "sections" in payload
    assert "system" in payload["sections"]
    assert "status" in payload


def test_api_host_returns_json_system_section():
    cache = _make_cache()
    with _Server(cache) as srv:
        status, ctype, body = _get(srv, "/api/host")
    assert status == 200
    assert "application/json" in ctype
    payload = json.loads(body)
    # /api/host mirrors the cached system section exactly.
    assert payload == cache.host()


def test_healthz_reports_ok():
    with _Server(_make_cache()) as srv:
        status, ctype, body = _get(srv, "/healthz")
    assert status == 200
    assert "application/json" in ctype
    assert json.loads(body) == {"status": "ok"}


# --------------------------------------------------------------------------- #
# HTTP surface — error / read-only invariants
# --------------------------------------------------------------------------- #

def test_unknown_path_404():
    with _Server(_make_cache()) as srv:
        try:
            _get(srv, "/nope")
            raise AssertionError("expected HTTP 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
            payload = json.loads(e.read())
            assert payload == {"error": "not_found"}


def test_post_is_405_read_only():
    """The server is strictly read-only — any mutating verb is rejected."""
    with _Server(_make_cache()) as srv:
        req = urllib.request.Request(srv.url("/"), data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTP 405")
        except urllib.error.HTTPError as e:
            assert e.code == 405
            payload = json.loads(e.read())
            assert payload["error"] == "read_only"
            assert "read-only" in payload["message"].lower()


def test_mutating_verbs_all_rejected():
    """PUT/DELETE/PATCH share the POST handler and must all 405."""
    with _Server(_make_cache()) as srv:
        for verb in ("PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(srv.url("/api/state"), method=verb)
            try:
                urllib.request.urlopen(req, timeout=5)
                raise AssertionError(f"expected HTTP 405 for {verb}")
            except urllib.error.HTTPError as e:
                assert e.code == 405, verb
                assert json.loads(e.read())["error"] == "read_only"


def _post(server, path, payload):
    req = urllib.request.Request(
        server.url(path), data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def test_refresh_returns_fresh_full_state():
    """GET /api/refresh forces a full re-collect and returns the whole state."""
    with _Server(_make_cache()) as srv:
        status, ctype, raw = _get(srv, "/api/refresh")
        assert status == 200 and "application/json" in ctype
        body = json.loads(raw)
        assert "sections" in body and "system" in body["sections"]
        assert "meta" in body and "status" in body
        assert "history" in body  # ring buffer travels with the state


def test_chat_disabled_by_default_is_405():
    """Chat is opt-in: with no server.chat config, POST /api/chat is rejected."""
    with _Server(_make_cache()) as srv:
        req = urllib.request.Request(
            srv.url("/api/chat"), data=b'{"message":"hi"}', method="POST",
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTP 405")
        except urllib.error.HTTPError as e:
            assert e.code == 405
            assert json.loads(e.read())["error"] == "read_only"


def _chat_cache() -> StateCache:
    # Enable chat with a harmless stub command: `echo <message>` echoes it back.
    prof = dict(PROFILE)
    prof["server"] = {"refresh": 5, "chat": {"enabled": True, "cmd": ["echo"], "timeout": 10}}
    return StateCache(prof)


def test_chat_enabled_runs_command_and_returns_reply():
    with _Server(_chat_cache()) as srv:
        status, body = _post(srv, "/api/chat", {"message": "ping pong"})
        assert status == 200
        assert body["ok"] is True
        assert body["reply"] == "ping pong"  # echo strips the trailing newline


def test_chat_empty_message_is_400():
    with _Server(_chat_cache()) as srv:
        req = urllib.request.Request(
            srv.url("/api/chat"), data=b'{"message":"   "}', method="POST",
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTP 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400


def test_chat_enabled_other_paths_still_405():
    """Enabling chat must not open any other mutating route."""
    with _Server(_chat_cache()) as srv:
        req = urllib.request.Request(srv.url("/"), data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTP 405")
        except urllib.error.HTTPError as e:
            assert e.code == 405

    # meta.chat reflects the toggle so the dashboard can show the box.
    assert _chat_cache().state()["meta"]["chat"] is True
    assert _make_cache().state()["meta"]["chat"] is False
