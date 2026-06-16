"""The agent-facing MCP server — read-only, live whole-system state.

Insikt runs as a **local, read-only** MCP server. Once registered, an agent
(Hermes, Claude Code, …) simply *has* these tools and reaches for them when the
user asks an introspection question ("what's the Pi running at?", "what can you
do?", "what changed?") — no bespoke per-framework glue.

Every tool:

* reads **live** state by running the collectors (``collect_state``) — there is no
  database; the answer is always current,
* returns **structured data, not prose** (the agent phrases the reply), and
* is strictly read-only — it never mutates the host or the agent.

Tool logic lives in module-level ``*_impl`` functions (directly testable);
``build_server`` wraps them as FastMCP tools. ``mcp`` is imported lazily so the
core (``insikt scan`` / ``serve``) works even where the MCP SDK is absent.
"""

from __future__ import annotations

from typing import Optional

from . import __version__
from .profiles import load_profile
from .state import collect_state

# Exact, declared permissions — surfaced verbatim by insikt_self_report so the
# agent can prove the tool to the user before/after install.
PERMISSIONS = {
    "mode": "read-only",
    "writes_to_host": False,
    "writes_to_agent": False,
    "reads_secret_values": False,
    "internet_egress": False,
    "shell_exec": False,
    "reads": [
        "host metrics via /proc, /sys, vcgencmd (Raspberry Pi temperature/throttle)",
        "~/.hermes/{config.yaml, .env (KEY NAMES only), skills, sessions, memory} (read-only)",
        "local Honcho v3 API (counts only) and Home Assistant REST API (version/health/entity counts)",
    ],
    "network": "loopback HTTP to local Honcho / Home Assistant only — no internet egress",
}

# Views available on the Hermes agent-audit payload.
_HERMES_VIEWS = ("summary", "capability", "timeline", "cost", "hygiene", "graph", "all")


def _state(profile: Optional[dict] = None) -> dict:
    return collect_state(profile or load_profile())


def _trim_section(sec: dict) -> dict:
    return {
        "status": sec.get("status"),
        "available": sec.get("available"),
        "summary": sec.get("summary"),
        "partial": sec.get("partial", False),
        "data": sec.get("data", {}),
    }


# --- tool implementations (directly testable) -----------------------------
def system_state_impl(profile: Optional[dict] = None) -> dict:
    """The whole-system rollup: overall status + every section's status/summary/
    metrics. Token-light — the heavy Hermes agent-audit payload is omitted (use
    ``insikt_hermes`` for that)."""
    st = _state(profile)
    return {
        "meta": st["meta"],
        "status": st["status"],
        "sections": {k: _trim_section(v) for k, v in st["sections"].items()},
    }


def host_impl(profile: Optional[dict] = None) -> dict:
    """Raspberry Pi / host metrics: temperature, CPU%, memory, disk, load,
    uptime, and throttle/under-voltage history."""
    return _trim_section(_state(profile)["sections"].get("system", {}))


def hermes_impl(view: str = "summary", profile: Optional[dict] = None) -> dict:
    """Hermes agent introspection. ``view`` ∈ summary|capability|timeline|cost|
    hygiene|graph|all. summary = the dashboard section; the others are slices of
    the agent-audit payload (what it can do, what it did, model spend, hygiene
    findings, the capability graph)."""
    if view not in _HERMES_VIEWS:
        return {"error": "bad_view", "message": f"view must be one of {list(_HERMES_VIEWS)}"}
    st = _state(profile)
    section = _trim_section(st["sections"].get("hermes", {}))
    agent = st.get("agent") or {}
    if view == "summary":
        return section
    if view == "all":
        return {"summary": section, "agent": agent}
    if view not in agent:
        return {"error": "unavailable", "message": f"no '{view}' data (Hermes not readable?)",
                "summary": section}
    return {view: agent[view], "status": section.get("status")}


def source_impl(name: str, profile: Optional[dict] = None) -> dict:
    """An optional source's live section. ``name`` ∈ honcho|homeassistant|system."""
    sec = _state(profile)["sections"].get(name)
    if sec is None:
        return {"error": "unknown_source", "message": f"no source named {name!r}"}
    return _trim_section(sec)


def describe_layout_impl(profile: Optional[dict] = None) -> dict:
    """Read-only, secret-redacted digest of the Hermes home + reachability probes
    + the profile schema, so the agent can author/repair Insikt's profile for this
    host. Returns a profile; a human applies it with ``insikt configure --apply``."""
    from . import configure as cfg

    return cfg.describe(profile or load_profile())


def self_report_impl(profile: Optional[dict] = None) -> dict:
    """Insikt's own version + EXACT permissions, so the agent can prove the tool
    to the user."""
    return {
        "name": "insikt",
        "version": __version__,
        "provenance": {
            "signed": False,
            "canonical_name": "insikt",
            "repo": "https://github.com/wachtelhund/insikt",
            "note": "v0 is unsigned. Signed/reproducible releases are on the roadmap.",
        },
        "permissions": PERMISSIONS,
    }


# --- FastMCP wiring -------------------------------------------------------
def build_server(profile: Optional[dict] = None):
    """Construct the FastMCP server. Imported lazily so the MCP SDK is optional."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The MCP server needs the 'mcp' package. Install it with: pip install 'mcp>=1.2'"
        ) from exc

    profile = profile or load_profile()
    mcp = FastMCP("insikt")

    @mcp.tool()
    def insikt_system_state() -> dict:
        """Whole-system health: overall status plus every section (host, Hermes,
        Honcho, Home Assistant) with its status, one-line summary, and metrics.
        The answer to "how's everything doing?" """
        return system_state_impl(profile)

    @mcp.tool()
    def insikt_host() -> dict:
        """Raspberry Pi / host metrics right now: SoC temperature, CPU%, memory,
        disk, load, uptime, and any under-voltage / throttle history."""
        return host_impl(profile)

    @mcp.tool()
    def insikt_hermes(view: str = "summary") -> dict:
        """Hermes agent introspection. view ∈ summary|capability|timeline|cost|
        hygiene|graph|all: what it can do, what it did, model spend, hygiene
        findings, and the capability graph."""
        return hermes_impl(view, profile)

    @mcp.tool()
    def insikt_source(name: str) -> dict:
        """Live section for one source. name ∈ honcho|homeassistant|system —
        e.g. Home Assistant version/health/entity counts, or Honcho workspace/
        peer/session counts."""
        return source_impl(name, profile)

    @mcp.tool()
    def insikt_describe_layout() -> dict:
        """Read-only, secret-redacted digest of this host's layout + reachability
        + the profile schema, so YOU can author/repair Insikt's profile. Returns a
        profile; a human applies it with `insikt configure --apply <file>`."""
        return describe_layout_impl(profile)

    @mcp.tool()
    def insikt_self_report() -> dict:
        """Insikt's own version, provenance, and EXACT permissions — so you can
        prove the tool to the user before or after install."""
        return self_report_impl(profile)

    return mcp


def run(transport: str = "stdio", profile: Optional[dict] = None) -> None:
    """Run the MCP server (blocking). Used by ``insikt mcp``."""
    build_server(profile).run(transport=transport)
