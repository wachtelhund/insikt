"""Insikt — local-first, read-only observability dashboard for a self-hosted AI homelab.

Collectors read each source (Raspberry Pi host metrics, a Hermes agent, optional
Honcho + Home Assistant) into one normalized ``Section`` (``insikt.collectors``);
``insikt.state.collect_state`` assembles them into one whole-system state that
feeds the offline HTML dashboard (``insikt.report``), the live read-only web
server (``insikt.server``), and the read-only MCP toolset (``insikt.mcp_server``).

Adding a source is one new ``Collector``; everything downstream is source-agnostic.
"""

__version__ = "0.0.2"
