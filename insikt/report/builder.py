"""Assemble the report payload and inline it into the HTML shell."""

from __future__ import annotations

import json
from typing import Optional

from .. import __version__
from ..hygiene import HygieneResult
from ..model import Graph, NodeType
from ..views import capability_surface, cost_ledger, graph_payload, query_actions
from .template import render_page


def _summary(graph: Graph, cap: dict, timeline: dict, cost: dict, hygiene: HygieneResult) -> dict:
    self_authored = sum(
        1 for s in graph.by_type(NodeType.SKILL) if s.props.get("self_authored")
    )
    risk = [
        {
            "agent_id": aid,
            "label": (graph.get(aid).label if graph.get(aid) else aid),
            "score": rs.score,
            "top_findings": [f.title for f in rs.findings[:3]],
            "worst": (rs.findings[0].severity.value if rs.findings else "info"),
        }
        for aid, rs in hygiene.scores.items()
    ]
    risk.sort(key=lambda r: r["score"], reverse=True)
    return {
        "agents": cap["totals"]["agents"],
        "skills": cap["totals"]["skills"],
        "self_authored_skills": self_authored,
        "tools": cap["totals"]["tools"],
        "connectors": cap["totals"]["connectors"],
        "models": cap["totals"]["models"],
        "credential_refs": cap["totals"]["credential_refs"],
        "actions": timeline["count"],
        "total_cost": cost["total_cost"],
        "total_tokens": cost["total_tokens"],
        "risk": risk,
    }


def render_report(
    graph: Graph,
    *,
    meta: dict,
    hygiene: HygieneResult,
    diff: Optional[dict] = None,
    now=None,
) -> str:
    """Render the full ``overview.html`` for a snapshot."""
    cap = capability_surface(graph)
    timeline = query_actions(graph, window="all", now=now, limit=1000)
    cost = cost_ledger(graph)

    payload = {
        "meta": {
            "tool_version": __version__,
            "generated_by": f"insikt {__version__}",
            **meta,
            "partial": graph.partial,
            "partial_reasons": list(graph.partial_reasons),
        },
        "summary": _summary(graph, cap, timeline, cost, hygiene),
        "capability": cap,
        "timeline": timeline,
        "cost": cost,
        "hygiene": hygiene.to_dict(),
        "diff": diff,
        "graph": graph_payload(graph),
        "backfill_note": timeline.get("note"),
    }

    title = meta.get("title", "Insikt — agent audit")
    data_json = json.dumps(payload, default=str)
    return render_page(title, data_json)
