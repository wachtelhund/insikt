from insikt.model import NodeType, make_id
from insikt.views import (
    capability_surface,
    cost_ledger,
    explain_node,
    query_actions,
    resolve_agents,
)


def test_resolve_agents(hermes_graph):
    assert len(resolve_agents(hermes_graph, None)) == 2
    assert resolve_agents(hermes_graph, "research") == [make_id(NodeType.AGENT, "hermes", "research")]


def test_capability_surface(hermes_graph):
    cap = capability_surface(hermes_graph)
    assert cap["totals"]["agents"] == 2
    assert cap["totals"]["skills"] == 3
    default = [a for a in cap["agents"] if a["profile"] == "default"][0]
    names = {s["name"] for s in default["skills"]}
    assert {"pi-temp-watch", "summarize", "backup-helper"} <= names
    pi = [s for s in default["skills"] if s["name"] == "pi-temp-watch"][0]
    assert pi["self_authored"] is True
    assert "shell" in pi["tools"]
    assert "TELEGRAM_BOT_TOKEN" in pi["credential_reads"]
    assert any(c["platform"] == "telegram" and c["accepts_strangers"] for c in default["connectors"])


def test_query_actions_yesterday(hermes_graph, now):
    res = query_actions(hermes_graph, window="yesterday", now=now)
    assert res["count"] == 13
    assert res["by_type"]["message_sent"] == 2
    assert res["by_type"]["shell"] == 3
    assert res["by_type"]["model_call"] == 3
    assert res["total_tokens"] == 5140
    assert abs(res["total_cost"] - 0.074) < 1e-9
    assert res["note"] and "backfill" in res["note"]
    # newest first
    ts = [a["ts"] for a in res["actions"]]
    assert ts == sorted(ts, reverse=True)


def test_query_actions_type_filter(hermes_graph, now):
    res = query_actions(hermes_graph, window="yesterday", type="message_sent", now=now)
    assert res["count"] == 2
    assert all(a["type"] == "message_sent" for a in res["actions"])


def test_query_actions_agent_filter(hermes_graph, now):
    # research profile did a model_call (11:05) and an MCP file read (11:02)
    res = query_actions(hermes_graph, window="yesterday", agent="research", now=now)
    assert res["count"] == 2
    assert all(a["agent"].endswith("research") for a in res["actions"])


def test_cost_ledger(hermes_graph):
    led = cost_ledger(hermes_graph)
    assert led["total_tokens"] == 5140
    assert abs(led["total_cost"] - 0.074) < 1e-9
    opus = [m for m in led["models"] if "claude-opus-4-8" in m["model"]][0]
    assert opus["calls"] == 2
    assert opus["tokens"] == 4220


def test_explain_skill(hermes_graph):
    pi = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")
    detail = explain_node(hermes_graph, pi)
    assert detail["type"] == "skill"
    assert detail["detail"]["self_authored"] is True
    assert "body_excerpt" in detail
    # explain must not leak the full body field via props
    assert "body" not in detail["props"]


def test_explain_missing(hermes_graph):
    assert explain_node(hermes_graph, "skill:does:not:exist") is None
