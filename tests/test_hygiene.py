from pathlib import Path

from insikt.hygiene import HygieneEngine, load_advisory_feed
from insikt.model import NodeType, Severity, make_id

FEED_PATH = Path(__file__).resolve().parents[1] / "insikt" / "data" / "advisory_feed.json"
AGENT = make_id(NodeType.AGENT, "hermes", "main")
PI = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")
BACKUP = make_id(NodeType.SKILL, "hermes", "backup-helper")


def _scan(graph, feed=None):
    return HygieneEngine(advisory_feed=feed).scan(graph)


def test_exfil_triad_flagged(hermes_graph):
    res = _scan(hermes_graph)
    triad = [f for f in res.findings if f.id == f"triad:{PI}"]
    assert triad and triad[0].severity == Severity.CRITICAL
    assert "shell" in triad[0].factors and "network" in triad[0].factors


def test_fingerprint_match(hermes_graph):
    res = _scan(hermes_graph, feed=load_advisory_feed(FEED_PATH))
    fp = [f for f in res.findings if f.id == f"fp:{BACKUP}"]
    assert fp and fp[0].severity == Severity.CRITICAL


def test_no_fingerprint_without_feed(hermes_graph):
    assert not any(f.id.startswith("fp:") for f in _scan(hermes_graph).findings)


def test_obfuscation_and_egress(hermes_graph):
    res = _scan(hermes_graph)
    assert any(f.id == f"cap:obfuscation:{BACKUP}" and f.severity == Severity.HIGH for f in res.findings)
    egress = [f for f in res.findings if f.id == f"egress:{BACKUP}"]
    assert egress and any("exfil.evil-example.com" in fac for fac in egress[0].factors)


def test_allowlisted_host_no_egress(hermes_graph):
    # pi-temp-watch only reaches api.telegram.org (allowlisted)
    res = _scan(hermes_graph)
    assert not any(f.id == f"egress:{PI}" for f in res.findings)


def test_posture_findings(hermes_graph):
    res = _scan(hermes_graph)
    ids = {f.id for f in res.findings}
    assert f"posture:tirith_enabled:{AGENT}" in ids
    assert f"posture:allow_lazy_installs:{AGENT}" in ids
    assert f"posture:guard_agent_created:{AGENT}" in ids


def test_stranger_connector_finding(hermes_graph):
    res = _scan(hermes_graph)
    assert any(f.id.startswith("stranger:") for f in res.findings)


def test_posture_silent_when_not_reported():
    # an agent that doesn't report these flags gets no posture findings (no noise)
    from insikt.model import Graph

    g = Graph()
    g.node(NodeType.AGENT, "x", "default", label="x/default", framework="x")
    res = _scan(g)
    assert not any(f.id.startswith("posture:") for f in res.findings)


def test_risk_scores_enumerate_factors(hermes_graph):
    res = _scan(hermes_graph, feed=load_advisory_feed(FEED_PATH))
    score = res.scores[AGENT]
    assert score.score > 0
    assert score.findings
    weights = [f.severity.weight for f in score.findings]
    assert weights == sorted(weights, reverse=True)


def test_graph_annotated_with_risk(hermes_graph):
    _scan(hermes_graph, feed=load_advisory_feed(FEED_PATH))
    assert hermes_graph.get(BACKUP).props.get("risk") == "critical"


def test_drift_finding():
    from insikt.model import Graph

    g = Graph()
    sid = g.node(NodeType.SKILL, "hermes", "evolver", label="evolver", name="evolver", self_authored=True)
    res = HygieneEngine().scan(
        g, drift={"capability_drift": [{"skill_id": sid, "skill": "evolver", "gained_tool": "shell"}]}
    )
    assert any(f.id == f"drift:{sid}" and f.severity == Severity.HIGH for f in res.findings)
