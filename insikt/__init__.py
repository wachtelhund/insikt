"""Insikt — local-first, read-only auditor for self-hosted AI agents.

Collectors read an agent's on-disk state, normalize it into one graph + action
timeline (``insikt.model``), persist append-only snapshots (``insikt.store``),
and expose the result as a self-contained HTML report (``insikt.report``) and a
read-only MCP server (``insikt.mcp_server``).

Everything below the collector layer is framework-agnostic: new agent support is
one new collector and nothing else changes.
"""

__version__ = "0.0.1"
