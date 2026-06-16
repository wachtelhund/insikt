"""Tiny stdlib JSON-over-HTTP helper for the optional local API collectors
(Honcho, Home Assistant). No third-party deps; short timeouts; never raises —
returns ``None`` on any failure so collectors degrade to ``off``/``partial``."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional


def _request(method: str, url: str, *, token: Optional[str] = None,
             body: Optional[dict] = None, timeout: float = 4.0) -> Optional[object]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else {}
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def get_json(url: str, *, token: Optional[str] = None, timeout: float = 4.0) -> Optional[object]:
    return _request("GET", url, token=token, timeout=timeout)


def post_json(url: str, body: Optional[dict] = None, *, token: Optional[str] = None,
              timeout: float = 4.0) -> Optional[object]:
    return _request("POST", url, token=token, body=body or {}, timeout=timeout)
