"""Static, local hygiene / risk scanning (README §6).

The same engine backs ``insikt_risk_report`` (MCP), the Hygiene view in the HTML
report, and the self-scan-on-install (README §8.2). Output is always a per-agent
score **with the contributing factors enumerated** — never just a number.
"""

from .engine import HygieneEngine, HygieneResult, load_advisory_feed

__all__ = ["HygieneEngine", "HygieneResult", "load_advisory_feed"]
