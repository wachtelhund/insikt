"""``insikt serve`` — a read-only live dashboard web server.

Runs on the Pi, bound (by default) to all interfaces so it's reachable over a
ZeroTier/Tailscale overlay. A background ``StateCache`` refreshes host metrics on
a fast cadence and the heavier sources (Hermes / Honcho / Home Assistant) on a
slow one; the browser gets the initial render inline, then live host updates via
Server-Sent Events. Strictly read-only: only GET is served, POST/etc. return 405.

Pure stdlib (``http.server``) — no web framework dependency.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .collectors.base import CRIT, OFF, OK, WARN
from .collectors.system import SystemCollector
from .profiles import load_profile
from .report import render_dashboard
from .state import collect_state

_RANK = {OK: 0, OFF: 0, WARN: 1, CRIT: 2}


class StateCache:
    """Thread-safe latest-state holder, refreshed by background loops."""

    def __init__(self, profile: dict):
        self.profile = profile
        self._lock = threading.Lock()
        self._sys = SystemCollector(profile)  # persistent → real CPU% deltas
        self._stop = threading.Event()
        self._state = collect_state(profile, system_collector=self._sys)

    def state(self) -> dict:
        with self._lock:
            return self._state

    def host(self) -> dict:
        with self._lock:
            return self._state["sections"].get("system", {})

    def _rollup(self, sections: dict) -> str:
        live = [s["status"] for s in sections.values() if s.get("status") != OFF]
        return max(live, key=lambda s: _RANK.get(s, 0)) if live else OK

    def _refresh_host(self) -> None:
        sec = self._sys.safe_collect().to_dict()
        with self._lock:
            self._state["sections"]["system"] = sec
            self._state["status"] = self._rollup(self._state["sections"])
            self._state["meta"]["generated"] = _now()

    def _refresh_full(self) -> None:
        st = collect_state(self.profile, system_collector=self._sys)
        with self._lock:
            self._state = st

    def run(self) -> None:
        fast = float((self.profile.get("server") or {}).get("refresh", 5))
        slow = max(fast * 6, 45.0)

        def fast_loop():
            while not self._stop.wait(fast):
                try:
                    self._refresh_host()
                except Exception:
                    pass

        def slow_loop():
            while not self._stop.wait(slow):
                try:
                    self._refresh_full()
                except Exception:
                    pass

        threading.Thread(target=fast_loop, daemon=True).start()
        threading.Thread(target=slow_loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_handler(cache: StateCache):
    refresh = float((cache.profile.get("server") or {}).get("refresh", 5))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body, ctype: str) -> None:
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, render_dashboard(cache.state(), live=True), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, json.dumps(cache.state(), default=str), "application/json")
            elif path == "/api/host":
                self._send(200, json.dumps(cache.host(), default=str), "application/json")
            elif path == "/healthz":
                self._send(200, json.dumps({"status": "ok"}), "application/json")
            elif path == "/events":
                self._sse()
            else:
                self._send(404, json.dumps({"error": "not_found"}), "application/json")

        def do_POST(self):
            self._send(405, json.dumps({"error": "read_only", "message": "Insikt is read-only"}), "application/json")

        do_PUT = do_DELETE = do_PATCH = do_POST

        def _sse(self):
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                while not cache._stop.is_set():
                    st = cache.state()
                    payload = json.dumps({
                        "host": st["sections"].get("system", {}),
                        "status": st.get("status"),
                        "generated": st["meta"].get("generated"),
                    }, default=str)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(refresh)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

    return Handler


def serve(profile: Optional[dict] = None, bind: Optional[str] = None, port: Optional[int] = None) -> None:
    profile = profile or load_profile()
    srv = profile.get("server") or {}
    bind = bind or srv.get("bind", "0.0.0.0")
    port = int(port or srv.get("port", 8420))

    cache = StateCache(profile)
    cache.run()
    httpd = ThreadingHTTPServer((bind, port), _make_handler(cache))
    httpd.daemon_threads = True
    print(f"insikt serving (read-only) on http://{bind}:{port}")
    for ip in _local_ips():
        print(f"  → http://{ip}:{port}")
    print("  Ctrl-C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
    finally:
        cache.stop()
        httpd.shutdown()


def _local_ips() -> list[str]:
    import socket

    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)
