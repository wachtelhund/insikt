"""Regression tests for issues found in the adversarial review."""

from datetime import datetime, timezone

import pytest

from insikt import mcp_server
from insikt.hygiene.engine import HygieneEngine, _is_wildcard_bind
from insikt.model import Graph, NodeType, Rel, Severity
from insikt.redact import redact_secrets
from insikt.store import Store
from insikt.views import capability_surface, cost_ledger, explain_node, query_actions

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


# --- #6/#8 secret redaction ----------------------------------------------
def test_redact_token_shapes():
    assert "sk-ant-" not in redact_secrets("key = sk-ant-abcdefghijklmnop12345")
    assert redact_secrets("ghp_0123456789abcdef0123456789abcdef") == "[REDACTED]"
    out = redact_secrets('API_KEY="supersecretvalue123"')
    assert "supersecretvalue123" not in out and "API_KEY" in out


def test_redact_keeps_normal_text():
    assert redact_secrets("reads TELEGRAM_BOT_TOKEN from env") is not None
    # a bare env var NAME (no value) must survive — names are safe to surface
    assert "TELEGRAM_BOT_TOKEN" in redact_secrets("os.environ['TELEGRAM_BOT_TOKEN']")


def test_scan_does_not_persist_raw_body(hermes_home, tmp_path):
    from insikt.cli import main

    db = str(tmp_path / "i.db")
    main(["scan", "--hermes-home", hermes_home, "--no-openclaw", "--db", db, "--out", str(tmp_path / "o.html")])
    store = Store(db)
    graph = store.load_graph()
    store.close()
    for skill in graph.by_type(NodeType.SKILL):
        assert "body" not in skill.props, f"raw body persisted for {skill.label}"
        # a redacted excerpt is still available for insikt_explain
        assert "body_excerpt" in skill.props


# --- #1 ts-less actions ---------------------------------------------------
def _graph_with_undated():
    g = Graph()
    a = g.node(NodeType.AGENT, "hermes", "default", label="hermes/default", framework="hermes", profile="default")
    g.node(NodeType.ACTION, "dated", label="shell: x", ts="2026-06-14T10:00:00Z", type="shell", agent_id=a, payload_summary="x", source="backfill")
    g.node(NodeType.ACTION, "undated", label="shell: y", ts=None, type="shell", agent_id=a, payload_summary="y", source="backfill")
    return g


def test_undated_action_included_in_all_window():
    g = _graph_with_undated()
    res = query_actions(g, window="all", now=NOW)
    assert res["count"] == 2  # both, including the ts-less one
    assert res["note"] and "no timestamp" in res["note"]


def test_undated_action_excluded_from_bounded_window():
    g = _graph_with_undated()
    res = query_actions(g, window="yesterday", now=NOW)
    assert res["count"] == 1  # only the dated one


# --- #2 malformed numeric cost/tokens degrades, never crashes -------------
def test_bad_numeric_cost_tokens_does_not_crash():
    g = Graph()
    a = g.node(NodeType.AGENT, "hermes", "default", label="hermes/default", framework="hermes", profile="default")
    m = g.node(NodeType.MODEL, "anthropic", "claude-opus-4-8", label="anthropic/claude-opus-4-8", provider="anthropic", model_name="claude-opus-4-8")
    g.node(NodeType.ACTION, "bad", label="model_call: x", ts="2026-06-14T10:00:00Z", type="model_call", agent_id=a, model_id=m, tokens="lots", cost="expensive", payload_summary="x", source="backfill")
    qa = query_actions(g, window="all", now=NOW)   # must not raise
    assert qa["count"] == 1
    assert qa["total_tokens"] == 0 and qa["total_cost"] == 0.0
    led = cost_ledger(g)                            # must not raise
    assert led["total_tokens"] == 0


# --- #4/#7/#9 IPv6 wildcard bind detection --------------------------------
@pytest.mark.parametrize("bind,expected", [
    ("0.0.0.0:8765", True),
    ("0.0.0.0", True),
    ("::", True),
    ("[::]:8765", True),
    ("[::1]:8765", False),
    ("127.0.0.1:18789", False),
    ("::1", False),
    ("192.168.1.5:80", False),
])
def test_is_wildcard_bind(bind, expected):
    assert _is_wildcard_bind(bind) is expected


def test_ipv6_exposure_flagged():
    g = Graph()
    g.node(NodeType.AGENT, "hermes", "default", label="hermes/default", framework="hermes", profile="default", gateway_bind="[::]:8765", auth_mode="none")
    res = HygieneEngine().scan(g)
    assert any(f.id.startswith("exposure:") and f.severity in (Severity.HIGH, Severity.CRITICAL) for f in res.findings)


# --- #5 risk_report agent filter is consistent with the score -------------
def test_risk_report_filter_matches_score(populated_db):
    res = mcp_server.risk_report_impl(populated_db, agent="default")
    score = next(iter(res["scores"].values()))
    # every finding the score counted is present in the returned findings list
    returned_ids = {f["id"] for f in res["findings"]}
    counted_ids = {f["id"] for f in score["findings"]}
    assert counted_ids <= returned_ids
    # and skill-level findings (triad) survive the filter
    assert any(fid.startswith("triad:") for fid in returned_ids)


# --- #12 bad window returns a structured error (no uncaught ValueError) ----
def test_bad_window_structured_error(populated_db):
    res = mcp_server.query_actions_impl(populated_db, window="last fortnight")
    assert res["error"] == "bad_window"


# --- #3 MCP servers appear in the capability surface ----------------------
def test_capability_surface_includes_mcp_servers(hermes_graph):
    cap = capability_surface(hermes_graph)
    assert cap["totals"]["mcp_servers"] == 2
    names = {s["name"] for s in cap["agents"][0]["mcp_servers"]}
    assert {"filesystem", "insikt"} == names


# --- #13 distinct actions sharing ts/type/summary don't merge -------------
def test_action_id_discriminator_avoids_merge():
    from insikt.model import action_id

    a = action_id("hermes", "2026-06-14T10:00:00Z", "model_call", "call", "default", "claude|100|0.01")
    b = action_id("hermes", "2026-06-14T10:00:00Z", "model_call", "call", "default", "gpt-4o|200|0.02")
    assert a != b


# --- #6 explain never returns a raw body, only a redacted excerpt ----------
def test_explain_excerpt_is_redacted(tmp_path):
    g = Graph()
    sid = g.node(
        NodeType.SKILL, "hermes", "leaky", label="leaky", name="leaky",
        body="token = sk-ant-abcdefghijklmnop12345 rest of body",
        body_excerpt=redact_secrets("token = sk-ant-abcdefghijklmnop12345 rest of body"),
    )
    detail = explain_node(g, sid)
    assert "sk-ant-abcdefghijklmnop12345" not in detail.get("body_excerpt", "")
    assert "body" not in detail["props"]
