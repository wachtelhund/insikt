"""Honcho collector (optional) — memory/representation backend stats.

Talks to a local Honcho v3 API (default ``http://localhost:8000``). Reports
health, version, and **counts** of workspaces / peers / sessions plus queue
status. It never reads peer names, workspace names, representations, or message
contents — only aggregates.
"""

from __future__ import annotations

from typing import Optional

from ._http import get_json, post_json
from .base import OK, WARN, Collector, Section


class HonchoCollector(Collector):
    key = "honcho"
    title = "Honcho"
    optional = True
    interval = 60.0

    def __init__(self, profile: Optional[dict] = None):
        super().__init__(profile)
        self.base = str(self.conf.get("base_url", "http://localhost:8000")).rstrip("/")
        self._version: Optional[str] = None

    def available(self) -> bool:
        if self.conf.get("enabled") is False:
            return False
        h = get_json(f"{self.base}/health", timeout=2.5)
        if not (isinstance(h, dict) and h.get("status") in ("ok", "healthy", "up", True)):
            return False
        # Confirm it's actually Honcho (not some other service on the port): the
        # v3 workspaces list must return Honcho's paginated shape.
        r = post_json(f"{self.base}/v3/workspaces/list", {}, timeout=3)
        return isinstance(r, dict) and "items" in r and "total" in r

    def _total(self, path: str) -> Optional[int]:
        r = post_json(f"{self.base}{path}", {})
        if isinstance(r, dict):
            if isinstance(r.get("total"), int):
                return r["total"]
            if isinstance(r.get("items"), list):
                return len(r["items"])
        return None

    def _ver(self) -> Optional[str]:
        if self._version is None:
            spec = get_json(f"{self.base}/openapi.json", timeout=4)
            self._version = (spec or {}).get("info", {}).get("version", "") if isinstance(spec, dict) else ""
        return self._version or None

    def collect(self) -> Section:
        if not self.available():
            return Section(self.key, self.title, available=False, status="off",
                           summary="not reachable", data={"base_url": self.base})

        workspaces = post_json(f"{self.base}/v3/workspaces/list", {})
        ws_total = workspaces.get("total") if isinstance(workspaces, dict) else None
        items = workspaces.get("items", []) if isinstance(workspaces, dict) else []
        primary = items[0].get("id") if items and isinstance(items[0], dict) else None

        peers = sessions = None
        queue = None
        if primary:
            peers = self._total(f"/v3/workspaces/{primary}/peers/list")
            sessions = self._total(f"/v3/workspaces/{primary}/sessions/list")
            q = get_json(f"{self.base}/v3/workspaces/{primary}/queue/status", timeout=3)
            if isinstance(q, dict):
                queue = {k: v for k, v in q.items() if isinstance(v, (int, bool, str))}

        data = {
            "version": self._ver(),
            "base_url": self.base,
            "workspaces": ws_total,
            "peers": peers,
            "sessions": sessions,
            "queue": queue,
        }
        bits = []
        if data["version"]:
            bits.append(data["version"])
        if ws_total is not None:
            bits.append(f"{ws_total} workspace" + ("s" if ws_total != 1 else ""))
        if peers is not None:
            bits.append(f"{peers} peers")
        if sessions is not None:
            bits.append(f"{sessions} sessions")
        status = OK
        pending = (queue or {}).get("pending") or (queue or {}).get("size")
        if isinstance(pending, int) and pending > 100:
            status, _ = WARN, bits.append(f"queue {pending}")
        return Section(self.key, self.title, available=True, status=status,
                       summary="  ·  ".join(bits) or "reachable", data=data)
