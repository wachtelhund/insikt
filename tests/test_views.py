from insikt.model import NodeType, make_id
from insikt.views import (
    capability_surface,
    cost_ledger,
    explain_node,
    query_actions,
    resolve_agents,
)

AGENT = make_id(NodeType.AGENT, "hermes", "main")
PI = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")


def test_resolve_agents(hermes_graph):
    assert resolve_agents(hermes_graph, None) == [AGENT]
    assert resolve_agents(hermes_graph, "main") == [AGENT]
    assert resolve_agents(hermes_graph, "nope") == []


def test_capability_surface(hermes_graph):
    cap = capability_surface(hermes_graph)
    assert cap["totals"]["agents"] == 1
    assert cap["totals"]["skills"] == 3
    agent = cap["agents"][0]
    names = {s["name"] for s in agent["skills"]}
    assert names == {"ascii-art", "pi-temp-watch", "backup-helper"}
    pi = [s for s in agent["skills"] if s["name"] == "pi-temp-watch"][0]
    assert pi["self_authored"] is True
    assert "shell" in pi["tools"] and "web" in pi["tools"]
    assert {r["value"] for r in pi["reaches"]} == {"api.telegram.org"}
    assert "TELEGRAM_BOT_TOKEN" in pi["credential_reads"]
    assert any(c["platform"] == "telegram" and c["accepts_strangers"] for c in agent["connectors"])


def test_reach_is_per_skill(hermes_graph):
    cap = capability_surface(hermes_graph)
    by = {s["name"]: s for s in cap["agents"][0]["skills"]}
    assert {r["value"] for r in by["backup-helper"]["reaches"]} == {"exfil.evil-example.com"}
    assert "api.telegram.org" not in {r["value"] for r in by["backup-helper"]["reaches"]}
    assert by["ascii-art"]["tools"] == []  # benign skill, no capabilities


def test_query_actions_yesterday(hermes_graph, now):
    res = query_actions(hermes_graph, window="yesterday", now=now)
    assert res["count"] == 6
    assert res["by_type"] == {"model_call": 3, "message_sent": 1, "scheduled_run": 2}
    assert res["total_tokens"] == 3000
    assert abs(res["total_cost"] - 0.065) < 1e-9
    assert res["note"] and "backfill" in res["note"]
    ts = [a["ts"] for a in res["actions"]]
    assert ts == sorted(ts, reverse=True)


def test_query_actions_type_filter(hermes_graph, now):
    res = query_actions(hermes_graph, window="yesterday", type="model_call", now=now)
    assert res["count"] == 3
    assert all(a["type"] == "model_call" for a in res["actions"])


def test_cost_ledger(hermes_graph):
    led = cost_ledger(hermes_graph)
    assert led["total_tokens"] == 3000
    assert abs(led["total_cost"] - 0.065) < 1e-9
    gpt = [m for m in led["models"] if "gpt-4o" in m["model"]][0]
    assert gpt["calls"] == 3


def test_explain_skill(hermes_graph):
    detail = explain_node(hermes_graph, PI)
    assert detail["type"] == "skill"
    assert detail["detail"]["self_authored"] is True
    assert "body_excerpt" in detail
    assert "body" not in detail["props"]


def test_explain_missing(hermes_graph):
    assert explain_node(hermes_graph, "skill:does:not:exist") is None
