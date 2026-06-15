from pathlib import Path

from insikt.collectors import HermesCollector, OpenClawCollector
from insikt.model import NodeType, Rel, make_id


# --- Hermes ---------------------------------------------------------------
def test_hermes_available(hermes_home):
    assert HermesCollector(home=hermes_home).available()


def test_hermes_missing_home_not_available(tmp_path):
    assert not HermesCollector(home=tmp_path / "nope").available()


def test_hermes_agents_and_profiles(hermes_graph):
    agents = hermes_graph.by_type(NodeType.AGENT)
    profiles = {a.props["profile"] for a in agents}
    assert profiles == {"default", "research"}
    default = hermes_graph.get(make_id(NodeType.AGENT, "hermes", "default"))
    assert default.props["gateway_bind"] == "0.0.0.0:8765"
    assert default.props["auth_mode"] == "none"
    assert default.props["host"] == "pi-hermes"
    assert default.props["memory_items"] == 7


def test_hermes_skills(hermes_graph):
    skills = {s.props["name"]: s for s in hermes_graph.by_type(NodeType.SKILL)}
    assert set(skills) == {"pi-temp-watch", "summarize", "backup-helper"}
    pi = skills["pi-temp-watch"]
    assert pi.props["self_authored"] is True
    assert pi.props["source"] == "self"
    assert len(pi.props["origin_hash"]) == 64
    # body retained for the static scan
    assert "subprocess" in pi.props["body"]


def test_hermes_credentials_names_only(hermes_graph):
    creds = {c.props["name"] for c in hermes_graph.by_type(NodeType.CREDENTIAL_REF)}
    assert {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "OPENCLAW_API_KEY"} <= creds
    # 'export ' prefix handled
    assert "HERMES_SIGNING_KEY" in creds
    # never the value
    for c in hermes_graph.by_type(NodeType.CREDENTIAL_REF):
        assert "FAKE" not in str(c.props)


def test_hermes_no_secret_values_anywhere(hermes_graph):
    # The literal fake secret material must never appear in the normalized graph.
    blob = repr([n.props for n in hermes_graph.nodes.values()])
    assert "sk-ant-FAKE" not in blob
    assert "ocw-FAKE" not in blob


def test_hermes_skill_edges(hermes_graph):
    pi = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")
    tools = {t.props["kind"] for t in hermes_graph.neighbors(pi, Rel.REQUIRES)}
    assert {"shell", "file", "web"} <= tools
    creds = {c.props["name"] for c in hermes_graph.neighbors(pi, Rel.READS)}
    assert "TELEGRAM_BOT_TOKEN" in creds
    # pi-temp-watch's web tool reaches ONLY its own declared host (per-skill scope)
    web = make_id(NodeType.TOOL, "web", "pi-temp-watch")
    hosts = {r.props["value"] for r in hermes_graph.neighbors(web, Rel.CAN_ACCESS)}
    assert hosts == {"api.telegram.org"}


def test_hermes_reach_is_per_skill(hermes_graph):
    # summarize must NOT appear to reach backup-helper's exfil host.
    from insikt.views import capability_surface

    cap = capability_surface(hermes_graph)
    default = [a for a in cap["agents"] if a["profile"] == "default"][0]
    by_name = {s["name"]: s for s in default["skills"]}
    summarize_hosts = {r["value"] for r in by_name["summarize"]["reaches"]}
    assert summarize_hosts == {"api.anthropic.com"}
    backup_hosts = {r["value"] for r in by_name["backup-helper"]["reaches"]}
    assert "exfil.evil-example.com" in backup_hosts
    assert "api.anthropic.com" not in backup_hosts


def test_hermes_actions_and_backfill(hermes_graph):
    actions = hermes_graph.actions()
    # 11 valid session actions (1 malformed skipped) + 3 mcp-log calls
    assert len(actions) == 14
    assert all(a.props.get("source") == "backfill" for a in actions)
    types = {a.props["type"] for a in actions}
    assert {"shell", "file_write", "message_sent", "skill_written", "model_call", "mcp_call"} <= types


def test_hermes_malformed_line_marks_partial(hermes_graph):
    assert hermes_graph.partial
    assert any("malformed" in r for r in hermes_graph.partial_reasons)


def test_hermes_model_called_edge_only_when_used(hermes_graph):
    default = make_id(NodeType.AGENT, "hermes", "default")
    called = {m.props["model_name"] for m in hermes_graph.neighbors(default, Rel.CALLED)}
    # default profile actually called opus and gpt-4o
    assert {"claude-opus-4-8", "gpt-4o"} <= called


def test_hermes_action_via_skill_and_touched_resource(hermes_graph):
    # the skill_written action links via the skill it created
    sw = [a for a in hermes_graph.actions() if a.props["type"] == "skill_written"][0]
    via = [hermes_graph.get(e.dst) for e in hermes_graph.edges_from(sw.id, Rel.VIA)]
    assert any(n and n.props.get("name") == "pi-temp-watch" for n in via)


def test_hermes_partial_when_config_missing(tmp_path):
    home = tmp_path / "h"
    (home / "skills").mkdir(parents=True)
    (home / "skills" / "x.md").write_text("---\nname: x\n---\nbody")
    res = HermesCollector(home=home).collect()
    assert res.graph.partial
    assert any("config.yaml" in r for r in res.graph.partial_reasons)


# --- OpenClaw -------------------------------------------------------------
def test_openclaw_available(openclaw_home):
    assert OpenClawCollector(home=openclaw_home).available()


def test_openclaw_basic(openclaw_graph):
    agents = openclaw_graph.by_type(NodeType.AGENT)
    assert len(agents) == 1
    a = agents[0]
    assert a.props["framework"] == "openclaw"
    assert a.props["gateway_bind"] == "127.0.0.1:18789"
    assert a.props["auth_mode"] == "token"
    connectors = {c.props["platform"] for c in openclaw_graph.by_type(NodeType.CONNECTOR)}
    assert {"telegram", "discord"} == connectors
    skills = {s.props["name"] for s in openclaw_graph.by_type(NodeType.SKILL)}
    assert "weather" in skills
    weather = [s for s in openclaw_graph.by_type(NodeType.SKILL) if s.props["name"] == "weather"][0]
    assert weather.props["source"] == "clawhub"
    assert weather.props["package_version"] == "1.2.0"
    # always marked partial (preliminary collector)
    assert openclaw_graph.partial


def test_openclaw_actions(openclaw_graph):
    actions = openclaw_graph.actions()
    assert len(actions) == 3
    cron = [a for a in actions if a.props.get("cron")]
    assert cron and cron[0].props["cron"] == "0 3 * * *"
