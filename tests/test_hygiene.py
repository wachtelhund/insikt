from pathlib import Path

from insikt.hygiene import HygieneEngine, load_advisory_feed
from insikt.model import NodeType, Severity, make_id

FEED_PATH = Path(__file__).resolve().parents[1] / "insikt" / "data" / "advisory_feed.json"


def _scan(graph, feed=None):
    return HygieneEngine(advisory_feed=feed).scan(graph)


def test_exfil_triad_flagged(hermes_graph):
    res = _scan(hermes_graph)
    pi = make_id(NodeType.SKILL, "hermes", "pi-temp-watch")
    triad = [f for f in res.findings if f.id == f"triad:{pi}"]
    assert triad and triad[0].severity == Severity.CRITICAL
    assert "shell" in triad[0].factors and "network" in triad[0].factors


def test_fingerprint_match(hermes_graph):
    feed = load_advisory_feed(FEED_PATH)
    res = _scan(hermes_graph, feed=feed)
    backup = make_id(NodeType.SKILL, "hermes", "backup-helper")
    fp = [f for f in res.findings if f.id == f"fp:{backup}"]
    assert fp and fp[0].severity == Severity.CRITICAL


def test_no_fingerprint_without_feed(hermes_graph):
    res = _scan(hermes_graph, feed=None)
    assert not any(f.id.startswith("fp:") for f in res.findings)


def test_obfuscation_and_egress(hermes_graph):
    res = _scan(hermes_graph)
    backup = make_id(NodeType.SKILL, "hermes", "backup-helper")
    assert any(f.id == f"cap:obfuscation:{backup}" and f.severity == Severity.HIGH for f in res.findings)
    egress = [f for f in res.findings if f.id == f"egress:{backup}"]
    assert egress
    assert any("exfil.evil-example.com" in fac for fac in egress[0].factors)


def test_allowlisted_host_no_egress(hermes_graph):
    res = _scan(hermes_graph)
    summarize = make_id(NodeType.SKILL, "hermes", "summarize")
    # summarize only reaches api.anthropic.com (allowlisted)
    assert not any(f.id == f"egress:{summarize}" for f in res.findings)


def test_exposure_critical_with_strangers(hermes_graph):
    res = _scan(hermes_graph)
    default = make_id(NodeType.AGENT, "hermes", "default")
    exposure = [f for f in res.findings if f.id == f"exposure:{default}"]
    assert exposure and exposure[0].severity == Severity.CRITICAL
    assert any("accepts strangers" in fac or "stranger" in fac.lower() for fac in exposure[0].factors)


def test_stranger_connector_finding(hermes_graph):
    res = _scan(hermes_graph)
    assert any(f.id.startswith("stranger:") for f in res.findings)


def test_risk_scores_enumerate_factors(hermes_graph):
    feed = load_advisory_feed(FEED_PATH)
    res = _scan(hermes_graph, feed=feed)
    default = make_id(NodeType.AGENT, "hermes", "default")
    score = res.scores[default]
    assert score.score > 0
    # never just a number: each contributing finding is present
    assert score.findings
    # findings sorted worst-first
    weights = [f.severity.weight for f in score.findings]
    assert weights == sorted(weights, reverse=True)


def test_graph_annotated_with_risk(hermes_graph):
    feed = load_advisory_feed(FEED_PATH)
    _scan(hermes_graph, feed=feed)
    backup = hermes_graph.get(make_id(NodeType.SKILL, "hermes", "backup-helper"))
    assert backup.props.get("risk") == "critical"


def test_drift_finding():
    from insikt.model import Graph, Rel

    g = Graph()
    sid = g.node(NodeType.SKILL, "hermes", "evolver", label="evolver", name="evolver", self_authored=True)
    res = HygieneEngine().scan(
        g, drift={"capability_drift": [{"skill_id": sid, "skill": "evolver", "gained_tool": "shell"}]}
    )
    assert any(f.id == f"drift:{sid}" and f.severity == Severity.HIGH for f in res.findings)
