"""Pure derivations over a normalized ``Graph`` — the single source of truth
shared by the HTML report (human-facing, README §5) and the MCP tools
(agent-facing, README §4).

Keeping both consumers on these functions means the answer an agent gets from
``insikt_query_actions`` is exactly what a human sees in the timeline.
"""

from __future__ import annotations

from typing import Optional

from .model import Graph, NodeType, Rel
from .redact import redact_secrets
from .timewindow import in_window, parse_window

_UNBOUNDED = ("all", "", "*")


def _to_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def resolve_agents(graph: Graph, agent: Optional[str]) -> list[str]:
    """Resolve an ``agent`` filter (id, profile, label, or framework) to ids.
    ``None`` returns all agents."""
    agents = graph.by_type(NodeType.AGENT)
    if not agent:
        return [a.id for a in agents]
    needle = agent.lower()
    return [
        a.id
        for a in agents
        if needle in (a.id.lower(), str(a.props.get("profile", "")).lower(), str(a.props.get("framework", "")).lower())
        or needle in a.label.lower()
    ]


def _skill_detail(graph: Graph, skill) -> dict:
    tools = []
    reaches = []
    for tool in graph.neighbors(skill.id, Rel.REQUIRES):
        tools.append(tool.props.get("kind", tool.label))
        for res in graph.neighbors(tool.id, Rel.CAN_ACCESS):
            reaches.append({"kind": res.props.get("kind"), "value": res.props.get("value", res.label)})
    cred_reads = [
        c.props.get("name", c.label) for c in graph.neighbors(skill.id, Rel.READS)
    ]
    return {
        "id": skill.id,
        "name": skill.props.get("name", skill.label),
        "source": skill.props.get("source"),
        "self_authored": bool(skill.props.get("self_authored")),
        "origin_hash": skill.props.get("origin_hash"),
        "risk": skill.props.get("risk"),
        "tools": sorted(set(t for t in tools if t)),
        "reaches": reaches,
        "credential_reads": sorted(set(cred_reads)),
    }


def capability_surface(graph: Graph, agent: Optional[str] = None) -> dict:
    """Per-agent inventory of skills/tools/connectors/models and what each can
    reach (README §4.1 ``insikt_capability_surface`` / §5 view 2)."""
    agent_ids = set(resolve_agents(graph, agent))
    # MCP config is per-home (framework-level), so the connected servers apply to
    # every profile/agent of that home. Surface them so they aren't orphaned from
    # the capability view (they otherwise only appear via touched-by actions).
    mcp_servers = sorted(
        (
            {"name": r.props.get("value", r.label), "command": r.props.get("command")}
            for r in graph.by_type(NodeType.RESOURCE)
            if r.props.get("kind") == "mcp_server"
        ),
        key=lambda s: s["name"],
    )
    agents_out = []
    for a in graph.by_type(NodeType.AGENT):
        if a.id not in agent_ids:
            continue
        skills = [_skill_detail(graph, s) for s in graph.neighbors(a.id, Rel.USES)]
        skills.sort(key=lambda s: s["name"])
        connectors = [
            {
                "platform": c.props.get("platform", c.label),
                "accepts_strangers": bool(c.props.get("accepts_strangers")),
                "risk": c.props.get("risk"),
            }
            for c in graph.neighbors(a.id, Rel.REACHABLE_VIA)
        ]
        models = [
            {"provider": m.props.get("provider"), "model_name": m.props.get("model_name")}
            for m in graph.neighbors(a.id, Rel.CALLED)
        ]
        agents_out.append(
            {
                "id": a.id,
                "label": a.label,
                "framework": a.props.get("framework"),
                "profile": a.props.get("profile"),
                "version": a.props.get("version"),
                "host": a.props.get("host"),
                "gateway_bind": a.props.get("gateway_bind"),
                "auth_mode": a.props.get("auth_mode"),
                "memory_items": a.props.get("memory_items"),
                "risk": a.props.get("risk"),
                "skills": skills,
                "connectors": connectors,
                "models": models,
                "mcp_servers": mcp_servers,
            }
        )
    agents_out.sort(key=lambda a: a["label"])
    return {
        "agents": agents_out,
        "totals": {
            "agents": len(agents_out),
            "skills": len(graph.by_type(NodeType.SKILL)),
            "tools": len(graph.by_type(NodeType.TOOL)),
            "connectors": len(graph.by_type(NodeType.CONNECTOR)),
            "models": len(graph.by_type(NodeType.MODEL)),
            "credential_refs": len(graph.by_type(NodeType.CREDENTIAL_REF)),
            "mcp_servers": len(mcp_servers),
        },
    }


def _action_row(graph: Graph, action) -> dict:
    p = action.props
    skill = None
    for e in graph.edges_from(action.id, Rel.VIA):
        n = graph.get(e.dst)
        if n:
            skill = n.label
            break
    resource = None
    for e in graph.edges_from(action.id, Rel.TOUCHED):
        n = graph.get(e.dst)
        if n:
            resource = n.props.get("value", n.label)
            break
    model = None
    if p.get("model_id"):
        m = graph.get(p["model_id"])
        if m:
            model = m.label
    return {
        "id": action.id,
        "ts": action.ts,
        "type": p.get("type"),
        "summary": p.get("payload_summary", action.label),
        "agent": _agent_label(graph, p.get("agent_id")),
        "skill": skill,
        "resource": resource,
        "model": model,
        "tokens": _to_int(p.get("tokens")),
        "cost": _to_float(p.get("cost")),
        "connector": p.get("connector"),
        "source": p.get("source"),
    }


def _agent_label(graph: Graph, agent_id: Optional[str]) -> Optional[str]:
    if not agent_id:
        return None
    n = graph.get(agent_id)
    return n.label if n else agent_id


def query_actions(
    graph: Graph,
    window: str = "all",
    type: Optional[str] = None,
    agent: Optional[str] = None,
    now=None,
    limit: int = 200,
) -> dict:
    """Summarized action list for a window — the answer to "what did you do?"
    (README §4.1 ``insikt_query_actions`` / §5 view 3). Token-light: returns
    aggregates plus the most recent ``limit`` rows."""
    start, end = parse_window(window, now=now)
    unbounded = (window or "all").strip().lower() in _UNBOUNDED
    agent_ids = set(resolve_agents(graph, agent)) if agent else None

    rows = []
    undated = 0
    for action in graph.actions():
        if action.ts:
            if not in_window(action.ts, start, end):
                continue
        elif not unbounded:
            # A timestamp-less action can't be placed in a bounded window.
            continue
        if type and action.props.get("type") != type:
            continue
        if agent_ids is not None and action.props.get("agent_id") not in agent_ids:
            continue
        if not action.ts:
            undated += 1
        rows.append(_action_row(graph, action))

    by_type: dict[str, int] = {}
    total_cost = 0.0
    total_tokens = 0
    backfilled = False
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
        if r.get("cost") is not None:
            total_cost += r["cost"]
        if r.get("tokens") is not None:
            total_tokens += r["tokens"]
        if r.get("source") == "backfill":
            backfilled = True

    # Reconstruction ceiling = the oldest backfilled action across the WHOLE
    # stream, not just this window (README §3.4: be honest about the cutoff).
    backfill_ts = [
        a.ts for a in graph.actions() if a.ts and a.props.get("source") == "backfill"
    ]
    ceiling = min(backfill_ts) if backfill_ts else None

    rows.sort(key=lambda r: r["ts"] or "", reverse=True)
    truncated = len(rows) > limit
    note = None
    if backfilled:
        note = "Reconstructed from the agent's retained logs (source=backfill)"
        if ceiling:
            note += f"; the audit cannot see actions before {ceiling}"
        if undated:
            note += f"; {undated} action(s) had no timestamp and are shown only in the unbounded view"
        note += "."

    return {
        "window": window,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(rows),
        "by_type": by_type,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "truncated": truncated,
        "note": note,
        "actions": rows[:limit],
    }


def cost_ledger(graph: Graph, agent: Optional[str] = None) -> dict:
    """Models used, token volume and spend — per agent and combined (README §5
    view 4)."""
    agent_ids = set(resolve_agents(graph, agent)) if agent else None
    per_model: dict[str, dict] = {}
    per_agent: dict[str, dict] = {}
    total_tokens = 0
    total_cost = 0.0

    # Seed EVERY configured/used model so the model an agent actually runs on
    # shows up even when no per-call token/cost was recorded (e.g. Hermes
    # sessions with 0 usage). Without this, the configured default is invisible.
    if agent_ids is None:
        seed_models = graph.by_type(NodeType.MODEL)
    else:
        seed_models = [m for aid in agent_ids for m in graph.neighbors(aid, Rel.CALLED)]
    for m in seed_models:
        per_model.setdefault(
            m.label,
            {
                "model": m.label, "provider": m.props.get("provider"),
                "calls": 0, "tokens": 0, "cost": 0.0,
                "default": bool(m.props.get("is_default")),
                "configured": bool(m.props.get("configured")),
                "used": bool(m.props.get("used")),
            },
        )

    for action in graph.actions():
        if action.props.get("type") != "model_call":
            continue
        aid = action.props.get("agent_id")
        if agent_ids is not None and aid not in agent_ids:
            continue
        model_id = action.props.get("model_id")
        m = graph.get(model_id) if model_id else None
        key = m.label if m else "unknown"
        tokens = _to_int(action.props.get("tokens")) or 0
        cost = _to_float(action.props.get("cost")) or 0.0
        total_tokens += tokens
        total_cost += cost

        pm = per_model.setdefault(
            key,
            {"model": key, "provider": (m.props.get("provider") if m else None), "calls": 0,
             "tokens": 0, "cost": 0.0, "default": False, "configured": False, "used": True},
        )
        pm["calls"] += 1
        pm["tokens"] += tokens
        pm["cost"] += cost
        pm["used"] = True

        alabel = _agent_label(graph, aid) or "unknown"
        pa = per_agent.setdefault(alabel, {"agent": alabel, "calls": 0, "tokens": 0, "cost": 0.0})
        pa["calls"] += 1
        pa["tokens"] += tokens
        pa["cost"] += cost

    for d in list(per_model.values()) + list(per_agent.values()):
        d["cost"] = round(d["cost"], 6)

    # used / most-expensive first; configured-but-unused models last.
    return {
        "models": sorted(per_model.values(), key=lambda d: (d["calls"] == 0, -d["cost"], -d["tokens"], d["model"])),
        "agents": sorted(per_agent.values(), key=lambda d: d["cost"], reverse=True),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
    }


def explain_node(graph: Graph, node_id: str) -> Optional[dict]:
    """Detail on one node (README §4.1 ``insikt_explain``)."""
    node = graph.get(node_id)
    if node is None:
        return None
    base = {
        "id": node.id,
        "type": node.type.value,
        "label": node.label,
        "props": {k: v for k, v in node.props.items() if k not in ("body", "body_excerpt")},
    }
    if node.type == NodeType.SKILL:
        base["detail"] = _skill_detail(graph, node)
        # Prefer the precomputed, redacted excerpt; fall back to redacting the
        # raw body (present on an in-memory graph that hasn't been persisted).
        excerpt = node.props.get("body_excerpt")
        if excerpt is None and node.props.get("body"):
            excerpt = redact_secrets(node.props["body"][:1000])
        if excerpt:
            base["body_excerpt"] = excerpt
    elif node.type == NodeType.ACTION:
        base["detail"] = _action_row(graph, node)
    else:
        out_edges = [
            {"rel": e.rel.value, "to": (graph.get(e.dst).label if graph.get(e.dst) else e.dst)}
            for e in graph.edges_from(node.id)
        ]
        in_edges = [
            {"rel": e.rel.value, "from": (graph.get(e.src).label if graph.get(e.src) else e.src)}
            for e in graph.edges_to(node.id)
        ]
        base["edges_out"] = out_edges
        base["edges_in"] = in_edges
    return base


def graph_payload(graph: Graph) -> dict:
    """Nodes + edges flattened for the force-directed view (README §5 view 1).
    Skill bodies are stripped — the report must stay small and never embed
    secret-adjacent text."""
    nodes = []
    for n in graph.nodes.values():
        props = {k: v for k, v in n.props.items() if k not in ("body", "body_excerpt")}
        nodes.append(
            {
                "id": n.id,
                "type": n.type.value,
                "label": n.label,
                "risk": n.props.get("risk"),
                "props": props,
                "ts": n.ts,
            }
        )
    edges = [{"src": e.src, "rel": e.rel.value, "dst": e.dst} for e in graph.edges]
    return {"nodes": nodes, "edges": edges}
