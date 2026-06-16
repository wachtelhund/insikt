"""Home Assistant collector (optional) — version, health, entity inventory.

Talks to a local HA REST API (default ``http://localhost:8123``) with a
long-lived token read from a file or env var. Reports the HA version, run state,
component count, and a per-domain **entity count** (e.g. sensor: 20, light: 5).
It never reads entity names, states, coordinates, or any location/identity field.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Optional

from ._http import get_json
from .base import CRIT, OK, WARN, Collector, Section


class HomeAssistantCollector(Collector):
    key = "homeassistant"
    title = "Home Assistant"
    optional = True
    interval = 60.0

    def __init__(self, profile: Optional[dict] = None):
        super().__init__(profile)
        self.base = str(self.conf.get("base_url", "http://localhost:8123")).rstrip("/")
        self.token = self._load_token()

    def _load_token(self) -> Optional[str]:
        env = self.conf.get("token_env", "HA_TOKEN")
        if env and os.environ.get(env):
            return os.environ[env].strip()
        tf = self.conf.get("token_file", "~/.hermes/ha_token.txt")
        if tf:
            try:
                return Path(tf).expanduser().read_text(encoding="utf-8").strip() or None
            except OSError:
                return None
        return None

    def available(self) -> bool:
        if self.conf.get("enabled") is False or not self.token:
            return False
        r = get_json(f"{self.base}/api/", token=self.token, timeout=2.5)
        return isinstance(r, dict) and "message" in r

    def collect(self) -> Section:
        if not self.token:
            return Section(self.key, self.title, available=False, status="off",
                           summary="no token", data={"base_url": self.base})
        root = get_json(f"{self.base}/api/", token=self.token, timeout=2.5)
        if not isinstance(root, dict):
            return Section(self.key, self.title, available=False, status="off",
                           summary="not reachable", data={"base_url": self.base})

        cfg = get_json(f"{self.base}/api/config", token=self.token) or {}
        # privacy: keep only non-identifying fields (no lat/long/location/urls).
        version = cfg.get("version")
        run_state = cfg.get("state")
        components = len(cfg.get("components", [])) if isinstance(cfg.get("components"), list) else None
        recovery = bool(cfg.get("recovery_mode"))
        safe = bool(cfg.get("safe_mode"))

        states = get_json(f"{self.base}/api/states", token=self.token)
        n_entities = None
        domains: dict[str, int] = {}
        if isinstance(states, list):
            n_entities = len(states)
            dom = Counter()
            for s in states:
                eid = s.get("entity_id", "") if isinstance(s, dict) else ""
                if "." in eid:
                    dom[eid.split(".", 1)[0]] += 1
            domains = dict(sorted(dom.items(), key=lambda kv: -kv[1]))

        status, notes = OK, []
        if run_state and run_state != "RUNNING":
            status, _ = WARN, notes.append(f"state {run_state}")
        if recovery or safe:
            status = CRIT
            notes.append("recovery/safe mode")

        data = {
            "version": version,
            "state": run_state,
            "components": components,
            "entities": n_entities,
            "domains": domains,
            "recovery_mode": recovery,
            "safe_mode": safe,
            "base_url": self.base,
        }
        bits = [b for b in (version, run_state,
                            (f"{n_entities} entities" if n_entities is not None else None),
                            (f"{components} components" if components is not None else None)) if b]
        return Section(self.key, self.title, available=True, status=status,
                       summary="  ·  ".join(str(b) for b in bits) or "reachable", data=data)
