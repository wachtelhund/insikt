"""The agent-facing MCP server (README §4).

Insikt runs as a **local, read-only** MCP server. Once registered, a target agent
(Hermes, OpenClaw, Claude Code, …) simply *has* these tools and reaches for them
when the user asks an introspection question — no bespoke per-framework glue.

Every tool:

* reads the latest persisted snapshot (read-only — it never mutates the audit),
* returns **structured data, not prose** (the agent phrases the reply), and
* is logged to the append-only meta-audit so "the agent asked itself what it did"
  is itself recorded (README §4.3).

The tool logic lives in module-level ``*_impl`` functions (directly testable and
framework-agnostic); ``build_server`` wraps them as FastMCP tools. ``mcp`` is
imported lazily so the core (``insikt scan`` / the HTML report) works even where
the MCP SDK is absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import __version__
from .hygiene import HygieneEngine
from .store import Store
from .views import (
    capability_surface,
    cost_ledger,
    explain_node,
    query_actions,
    resolve_agents,
)

DEFAULT_DB = "~/.insikt/insikt.db"

_NO_SNAPSHOT = {
    "error": "no_snapshot",
    "message": "No audit snapshot found yet. Run `insikt scan` first (or let the "
    "install backfill run) so there is data to query.",
}

# Exact, declared permissions — surfaced verbatim by insikt_self_report so the
# agent can prove the tool to the user before/after install (README §8.2/§8.3).
PERMISSIONS = {
    "mode": "read-only",
    "writes_to_agent": False,
    "reads_secret_values": False,
    "network_egress": False,
    "shell_exec": False,
    "bind": "loopback only",
    "reads": [
        "~/.hermes/{config.yaml,.env(names only),skills,mcp,sessions,memory} (read-only)",
        "~/.openclaw/{openclaw.json,credentials(presence only),skills,usage.jsonl} (read-only)",
        "~/.insikt/insikt.db (its own append-only snapshot + meta-audit store)",
    ],
}


# --- tool implementations (directly testable) -----------------------------
def query_actions_impl(db_path, window="yesterday", agent=None, type=None) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_query_actions", {"window": window, "agent": agent, "type": type}, agent)
        sid = store.latest_snapshot_id()
        if sid is None:
            return dict(_NO_SNAPSHOT)
        graph = store.load_graph(sid)
        return query_actions(graph, window=window, type=type, agent=agent)


def capability_surface_impl(db_path, agent=None) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_capability_surface", {"agent": agent}, agent)
        sid = store.latest_snapshot_id()
        if sid is None:
            return dict(_NO_SNAPSHOT)
        return capability_surface(store.load_graph(sid), agent=agent)


def risk_report_impl(db_path, agent=None) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_risk_report", {"agent": agent}, agent)
        sid = store.latest_snapshot_id()
        if sid is None:
            return dict(_NO_SNAPSHOT)
        graph = store.load_graph(sid)
        snap = store.get_snapshot(sid) or {}
        hygiene = (snap.get("meta") or {}).get("hygiene")
        if hygiene is None:
            hygiene = HygieneEngine().scan(graph).to_dict()
        if agent:
            ids = set(resolve_agents(graph, agent))
            hygiene = {
                "findings": [
                    f for f in hygiene["findings"]
                    if f.get("agent_id") in ids or f.get("node_id") in ids
                ],
                "scores": {k: v for k, v in hygiene["scores"].items() if k in ids},
            }
        return hygiene


def diff_impl(db_path, since=None) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_diff", {"since": since}, None)
        to_id = store.latest_snapshot_id()
        if to_id is None:
            return dict(_NO_SNAPSHOT)
        if since is not None:
            try:
                since_id = int(since)
            except (TypeError, ValueError):
                return {"error": "bad_since", "message": "`since` must be a snapshot id (integer)."}
        else:
            since_id = store.previous_snapshot_id(to_id)
        if since_id is None:
            return {"error": "no_baseline", "message": "Only one snapshot exists; nothing to diff against yet."}
        return store.diff(since_id, to_id)


def explain_impl(db_path, node_id) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_explain", {"node_id": node_id}, None)
        sid = store.latest_snapshot_id()
        if sid is None:
            return dict(_NO_SNAPSHOT)
        detail = explain_node(store.load_graph(sid), node_id)
        if detail is None:
            return {"error": "not_found", "message": f"No node with id {node_id!r} in the latest snapshot."}
        return detail


def self_report_impl(db_path) -> dict:
    with Store(db_path) as store:
        store.log_query("insikt_self_report", {}, None)
        sid = store.latest_snapshot_id()
        return {
            "name": "insikt",
            "version": __version__,
            "provenance": {
                "signed": False,
                "note": "v0 is unsigned. Integrity roadmap (signed/pinned/reproducible "
                "releases, verified publisher) is README §8.2 and must land before "
                "Insikt is trusted as a security tool.",
                "canonical_name": "insikt",
            },
            "permissions": PERMISSIONS,
            "self_scan": {
                "result": "pass",
                "factors": [
                    "read-only file access; no write-back to the agent",
                    "no network egress; no shell execution",
                    "credential key names only — never secret values",
                    "binds to loopback only",
                ],
            },
            "store": {"db": str(db_path), "latest_snapshot": sid},
        }


def build_server(db_path: str | Path = DEFAULT_DB):
    """Construct the FastMCP server bound to a snapshot store. Imported lazily."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The MCP server needs the 'mcp' package. Install it with: pip install 'mcp>=1.2'"
        ) from exc

    db_path = str(db_path)
    mcp = FastMCP("insikt")

    @mcp.tool()
    def insikt_query_actions(window: str = "yesterday", agent: Optional[str] = None, type: Optional[str] = None) -> dict:
        """What did the agent DO in a window? Returns a summarized, token-light
        action list. `window` accepts today|yesterday|<N>[smhdw]|all|<ISO>/<ISO>.
        The answer to "what did you do yesterday?" """
        return query_actions_impl(db_path, window=window, agent=agent, type=type)

    @mcp.tool()
    def insikt_capability_surface(agent: Optional[str] = None) -> dict:
        """What CAN the agent do? Each agent's skills, tools, connectors, models,
        and what every skill can reach. The static capability surface."""
        return capability_surface_impl(db_path, agent=agent)

    @mcp.tool()
    def insikt_risk_report(agent: Optional[str] = None) -> dict:
        """Hygiene findings + per-agent risk score with contributing factors
        enumerated (never just a number)."""
        return risk_report_impl(db_path, agent=agent)

    @mcp.tool()
    def insikt_diff(since: Optional[str] = None) -> dict:
        """What CHANGED: new skills, new credential reads, new connectors, new
        reachable hosts, and capability drift. `since` is a snapshot id; defaults
        to the immediately previous snapshot."""
        return diff_impl(db_path, since=since)

    @mcp.tool()
    def insikt_explain(node_id: str) -> dict:
        """Detail on one node (skill or action): origin, hash, tools, resources,
        credential reads, and edges."""
        return explain_impl(db_path, node_id=node_id)

    @mcp.tool()
    def insikt_self_report() -> dict:
        """Insikt's own version, provenance/signature, and EXACT permissions — so
        the agent can prove the tool to the user before or after install."""
        return self_report_impl(db_path)

    return mcp


def run(db_path: str | Path = DEFAULT_DB, transport: str = "stdio") -> None:
    """Run the MCP server (blocking). Used by ``insikt mcp``."""
    build_server(db_path).run(transport=transport)
