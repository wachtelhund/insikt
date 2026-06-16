"""Assemble the whole-system state from all collectors.

This is the single contract the dashboard, the web server (live JSON/SSE), the
one-shot ``scan`` report, and the MCP tools all read. ``fast_only`` collects just
the host metrics (cheap, for the live ticker); a full pass adds Hermes (with its
agent-audit payload), Honcho, and Home Assistant.
"""

from __future__ import annotations

import platform as _platform
from datetime import datetime, timezone
from typing import Optional

from . import __version__
from .collectors.base import CRIT, OFF, OK, WARN, Section
from .collectors.hermes import build_hermes
from .collectors.homeassistant import HomeAssistantCollector
from .collectors.honcho import HonchoCollector
from .collectors.system import SystemCollector

_RANK = {OK: 0, OFF: 0, WARN: 1, CRIT: 2}
_OPTIONAL = [HonchoCollector, HomeAssistantCollector]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _optional_section(col, profile: dict) -> dict:
    enabled = (profile.get(col.key) or {}).get("enabled", "auto")
    if enabled is False:
        return Section(col.key, col.title, available=False, status=OFF, summary="disabled").to_dict()
    if not col.available():
        return Section(col.key, col.title, available=False, status=OFF,
                       summary="not configured / not reachable").to_dict()
    return col.safe_collect().to_dict()


def collect_state(
    profile: dict,
    *,
    now=None,
    fast_only: bool = False,
    system_collector: Optional[SystemCollector] = None,
) -> dict:
    """Collect the full system state (or just host metrics if ``fast_only``)."""
    sections: dict[str, dict] = {}
    agent = None

    sys_col = system_collector or SystemCollector(profile)
    sections["system"] = sys_col.safe_collect().to_dict()

    if not fast_only:
        hermes_section, agent = build_hermes(profile, now=now)
        sections["hermes"] = hermes_section
        for cls in _OPTIONAL:
            col = cls(profile)
            sections[col.key] = _optional_section(col, profile)

    live = [s["status"] for s in sections.values() if s["status"] != OFF]
    rollup = max(live, key=lambda s: _RANK.get(s, 0)) if live else OK

    return {
        "meta": {
            "generated": now or _now_iso(),
            "tool_version": __version__,
            "host": _platform.node() or "host",
            "model": sections["system"].get("data", {}).get("model"),
            "refresh": (profile.get("server") or {}).get("refresh", 5),
            "chat": bool(((profile.get("server") or {}).get("chat") or {}).get("enabled")),
        },
        "status": rollup,
        "sections": sections,
        "agent": agent,
    }
