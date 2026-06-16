"""Collectors — one per data source in the homelab stack.

* ``SystemCollector``        — Raspberry Pi / host metrics (always on, fast).
* ``HermesGraphScanner`` + ``build_hermes`` — the agent: capabilities, actions,
  memories, models, hygiene.
* ``HonchoCollector``        — optional memory-backend stats.
* ``HomeAssistantCollector`` — optional HA version / health / entity inventory.

Everything below the collector line is source-agnostic (state assembly, server,
report, MCP). A new source = one new collector.
"""

from .base import CRIT, OFF, OK, WARN, Collector, Section
from .hermes import HermesGraphScanner, build_hermes
from .homeassistant import HomeAssistantCollector
from .honcho import HonchoCollector
from .system import SystemCollector

__all__ = [
    "Collector",
    "Section",
    "OK",
    "WARN",
    "CRIT",
    "OFF",
    "SystemCollector",
    "HonchoCollector",
    "HomeAssistantCollector",
    "HermesGraphScanner",
    "build_hermes",
]
