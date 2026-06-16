"""Collector contract for the system dashboard.

Insikt is now a whole-system observability layer for a self-hosted homelab stack
(Raspberry Pi + Hermes, optional Honcho + Home Assistant). Each data source is a
``Collector`` that produces one JSON-serializable ``Section``. Collectors are
read-only, degrade gracefully (a dead/absent source becomes ``status=off`` or a
``partial`` reason, never an exception that aborts the scan), and declare a live
refresh ``interval`` so the web server can poll fast sources (the Pi metrics)
more often than slow ones (the agent / HA / Honcho).

Privacy: collectors deliberately gather *counts, versions, health and metrics* —
never coordinates, entity names, peer names, memory contents, or secret values.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# Section / metric status levels.
OK = "ok"
WARN = "warn"
CRIT = "crit"
OFF = "off"


@dataclass
class Section:
    key: str
    title: str
    available: bool
    status: str = OK
    summary: str = ""
    data: dict = field(default_factory=dict)
    partial: bool = False
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "available": self.available,
            "status": self.status,
            "summary": self.summary,
            "data": self.data,
            "partial": self.partial,
            "reasons": list(self.reasons),
        }


class Collector(ABC):
    key: str = "?"
    title: str = "?"
    interval: float = 30.0  # seconds between refreshes in the live server
    optional: bool = False  # optional sources are silently dropped when absent

    def __init__(self, profile: Optional[dict] = None):
        self.profile = profile or {}
        self.conf = (self.profile.get(self.key) or {}) if isinstance(self.profile, dict) else {}

    @abstractmethod
    def available(self) -> bool:
        """True if this source appears to be present/reachable."""

    @abstractmethod
    def collect(self) -> Section:
        """Read the source and return a Section. Must not raise on a merely
        unreachable/incomplete source — set status/partial instead."""

    def safe_collect(self) -> Section:
        """Never-raises wrapper used by the scan/server."""
        try:
            return self.collect()
        except Exception as exc:  # pragma: no cover - defensive
            return Section(
                key=self.key, title=self.title, available=False, status=CRIT,
                summary=f"collector error", partial=True, reasons=[f"{type(exc).__name__}: {exc}"],
            )
