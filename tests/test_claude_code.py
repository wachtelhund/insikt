from collections import Counter

from insikt.hygiene import HygieneEngine
from insikt.model import NodeType, Severity, make_id

AGENT = make_id(NodeType.AGENT, "claude-code", "default")
DANGER = make_id(NodeType.SKILL, "claude-code", "command:danger")


def test_available(claude_code_home):
    from insikt.collectors import ClaudeCodeCollector

    assert ClaudeCodeCollector(home=claude_code_home).available()


def test_counts(claude_code_graph):
    g = claude_code_graph
    n = lambda t: len(g.by_type(t))
    assert n(NodeType.AGENT) == 1
    assert n(NodeType.SKILL) == 4
    assert n(NodeType.CREDENTIAL_REF) == 2
    assert sum(1 for r in g.by_type(NodeType.RESOURCE) if r.props.get("kind") == "mcp_server") == 2


def test_skill_kinds_and_self_authored(claude_code_graph):
    kinds = Counter(s.props.get("skill_kind") for s in claude_code_graph.by_type(NodeType.SKILL))
    assert kinds == {"command": 2, "subagent": 1, "skill": 1}
    # user-authored commands/subagents are self_authored; installed skills are not
    self_authored = {s.props["name"] for s in claude_code_graph.by_type(NodeType.SKILL) if s.props.get("self_authored")}
    assert self_authored == {"audit", "danger", "docker-debug"}


def test_agent_posture(claude_code_graph):
    a = claude_code_graph.get(AGENT)
    assert a.props["permission_mode"] == "auto"
    assert a.props["skip_dangerous_prompt"] is True
    assert a.props["skip_auto_prompt"] is True
    assert a.props["allow_rules"] == 4  # 3 from settings.json + 1 from settings.local.json


def test_actions(claude_code_graph):
    types = Counter(x.props.get("type") for x in claude_code_graph.actions())
    assert types["shell"] == 1        # Bash
    assert types["file_write"] == 1   # Write (Read is skipped as noise)
    assert types["model_call"] == 3   # assistant usage on each turn
    assert all(x.props.get("source") == "backfill" for x in claude_code_graph.actions())


def test_credentials_names_only(claude_code_graph):
    creds = {c.props["name"] for c in claude_code_graph.by_type(NodeType.CREDENTIAL_REF)}
    assert creds == {"anthropic", "github.com"}
    blob = repr([n.props for n in claude_code_graph.nodes.values()])
    assert "presence-only" not in blob  # value never read, only the key name


def test_hygiene(claude_code_graph):
    res = HygieneEngine().scan(claude_code_graph)
    ids = {f.id for f in res.findings}
    # danger is a user-authored command with the triad -> CRITICAL
    triad = [f for f in res.findings if f.id == f"triad:{DANGER}"]
    assert triad and triad[0].severity == Severity.CRITICAL
    # Claude Code posture findings
    assert f"posture:skip_dangerous_prompt:{AGENT}" in ids
    assert f"posture:skip_auto_prompt:{AGENT}" in ids
