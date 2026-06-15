"""Framework-specific collectors (the only framework-specific layer).

Each collector reads one framework's on-disk state read-only and emits the
normalized ``Graph``. Everything downstream of here is framework-agnostic, so new
agent support is one new collector and nothing else changes (README §3, §7).
"""

from .base import Collector, CollectorResult
from .hermes import HermesCollector
from .openclaw import OpenClawCollector

# Registry of known collectors, in scan order.
COLLECTORS: list[type[Collector]] = [HermesCollector, OpenClawCollector]

__all__ = [
    "Collector",
    "CollectorResult",
    "HermesCollector",
    "OpenClawCollector",
    "COLLECTORS",
]
