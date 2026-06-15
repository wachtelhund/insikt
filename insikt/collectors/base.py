"""Collector contract (README §3).

Collectors are **read-only** and **degrade gracefully**: a missing path or an
unreadable file becomes a ``partial`` reason on the graph, never an exception that
aborts the scan. They declare the framework version range they support so the UI
and MCP responses can say "incomplete" rather than silently lie.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..model import Graph


@dataclass
class CollectorResult:
    framework: str
    graph: Graph
    available: bool
    supported_versions: str = "*"
    detected_version: str | None = None


class Collector(ABC):
    #: Short framework key, e.g. "hermes" / "openclaw".
    framework: str = "unknown"
    #: Human-readable version range this collector was written against.
    supported_versions: str = "*"

    @abstractmethod
    def available(self) -> bool:
        """True if this framework's state appears to be present on disk."""

    @abstractmethod
    def collect(self) -> CollectorResult:
        """Read on-disk state and return a normalized graph. Must not raise on a
        merely-incomplete install — set ``graph.mark_partial(reason)`` instead."""
