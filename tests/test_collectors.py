from insikt.collectors import HermesCollector, OpenClawCollector
from insikt.model import NodeType, Rel, make_id

AGENT = make_id(NodeType.AGENT, "hermes", "main")
PI = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")
BACKUP = make_id(NodeType.SKILL, "hermes", "backup-helper")


# --- Hermes (real ~/.hermes layout) ---------------------------------------
def test_hermes_available(hermes_home):
    assert HermesCollector(home=hermes_home).available()


def test_hermes_missing_home_not_available(tmp_path):
    assert not HermesCollector(home=tmp_path / "nope").available()


def test_hermes_counts(hermes_graph):
    n = lambda t: len(hermes_graph.by_type(t))
    assert n(NodeType.AGENT) == 1
    assert n(NodeType.SKILL) == 3
    assert n(NodeType.CONNECTOR) == 2
    assert n(NodeType.MODEL) == 2
    assert n(NodeType.CREDENTIAL_REF) == 6
    assert len(hermes_graph.actions()) == 6
    assert not hermes_graph.partial


def test_hermes_agent_posture(hermes_graph):
    a = hermes_graph.get(AGENT)
    assert a.props["framework"] == "hermes"
    assert a.props["tirith_enabled"] is False
    assert a.props["allow_lazy_installs"] is True
    assert a.props["guard_agent_created"] is False
    assert a.props["memory_items"] == 5
    assert a.props["honcho"] is True
    assert a.props["gateway_platforms"] == ["telegram"]


def test_hermes_skills_nested_and_self_authored(hermes_graph):
    skills = {s.props["name"]: s for s in hermes_graph.by_type(NodeType.SKILL)}
    assert set(skills) == {"ascii-art", "pi-temp-watch", "backup-helper"}
    assert skills["ascii-art"].props["source"] == "bundled"
    assert skills["ascii-art"].props["self_authored"] is False
    assert skills["pi-temp-watch"].props["self_authored"] is True
    assert skills["pi-temp-watch"].props["category"] == "autonomous-ai-agents"
    assert "subprocess" in skills["pi-temp-watch"].props["body"]
    # bundled skill takes its hash from the manifest
    assert skills["ascii-art"].props["origin_hash"] == "aaaa1111bbbb2222cccc3333dddd4444"


def test_hermes_connectors_strangers(hermes_graph):
    conns = {c.props["platform"]: c for c in hermes_graph.by_type(NodeType.CONNECTOR)}
    assert set(conns) == {"slack", "telegram"}
    assert conns["telegram"].props["accepts_strangers"] is True   # no allowed_chats
    assert conns["slack"].props["accepts_strangers"] is False      # require_mention
    for c in conns.values():
        assert any(e.dst == c.id for e in hermes_graph.edges_from(AGENT, Rel.REACHABLE_VIA))


def test_hermes_credentials_names_only(hermes_graph):
    creds = {c.props["name"] for c in hermes_graph.by_type(NodeType.CREDENTIAL_REF)}
    assert {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY"} <= creds
    # config-stored secrets surfaced by dotted path, names only
    assert "model.openrouter.api_key" in creds
    assert "gateway.telegram.token" in creds
    # never values; bool flags like redact_secrets are NOT credentials
    assert "security.redact_secrets" not in creds
    for c in hermes_graph.by_type(NodeType.CREDENTIAL_REF):
        assert "FAKE" not in str(c.props)


def test_hermes_actions(hermes_graph):
    from collections import Counter
    types = Counter(a.props["type"] for a in hermes_graph.actions())
    assert types["model_call"] == 3
    assert types["message_sent"] == 1
    assert types["scheduled_run"] == 2
    assert all(a.props.get("source") == "backfill" for a in hermes_graph.actions())


def test_hermes_no_secret_values_anywhere(hermes_graph):
    blob = repr([n.props for n in hermes_graph.nodes.values()])
    assert "FAKE" not in blob


# --- OpenClaw -------------------------------------------------------------
def test_openclaw_available(openclaw_home):
    assert OpenClawCollector(home=openclaw_home).available()


def test_openclaw_basic(openclaw_graph):
    agents = openclaw_graph.by_type(NodeType.AGENT)
    assert len(agents) == 1
    a = agents[0]
    assert a.props["framework"] == "openclaw"
    assert a.props["gateway_bind"] == "127.0.0.1:18789"
    connectors = {c.props["platform"] for c in openclaw_graph.by_type(NodeType.CONNECTOR)}
    assert {"telegram", "discord"} == connectors
    skills = {s.props["name"] for s in openclaw_graph.by_type(NodeType.SKILL)}
    assert "weather" in skills
    assert openclaw_graph.partial  # preliminary collector


def test_openclaw_actions(openclaw_graph):
    actions = openclaw_graph.actions()
    assert len(actions) == 3
    assert any(a.props.get("cron") for a in actions)
