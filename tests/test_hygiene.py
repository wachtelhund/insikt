"""Tests for insikt.hygiene — the static, framework-agnostic risk scanner.

Builds the normalized graph from the bundled Hermes fixture and exercises the
HygieneEngine end to end:

  * happy path: the fixture's self-authored skill (``pi-temp-watch``) bundles
    credential-read + network + shell in one place, which is the exfil triad and
    must be a CRITICAL finding;
  * advisory feed: the community ``backup-helper`` skill's SKILL.md sha256 is on
    the bundled advisory feed, so a fingerprint (``fp:``) CRITICAL must fire;
  * invariants: every finding carries a ``kind`` and the dangerous ones carry a
    ``remediation``; scoring is per-agent and never "just a number" (factors are
    enumerated); a benign / empty graph produces no findings.

Read-only: nothing here writes under the agent home or under insikt/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from insikt.collectors.hermes import HermesGraphScanner
from insikt.hygiene import HygieneEngine, HygieneResult, load_advisory_feed
from insikt.model import FindingKind, Graph, NodeType, Severity

FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

# The bundled, unsigned sample feed (SPEC §6, §8.2). ``load_advisory_feed``
# requires a path argument — there is no zero-arg "default feed" overload — so we
# point it at the real packaged file the production code also uses
# (collectors/hermes.py build_hermes()).
import insikt  # noqa: E402

_BUNDLED_FEED = Path(insikt.__file__).resolve().parent / "data" / "advisory_feed.json"


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = HermesGraphScanner(home=str(FIX)).scan()
    assert g.by_type(NodeType.SKILL), "fixture should yield skill nodes"
    return g


@pytest.fixture(scope="module")
def feed() -> dict:
    f = load_advisory_feed(_BUNDLED_FEED)
    # Sanity: the sample feed actually carries the known-bad hash we rely on.
    assert f.get("known_bad_hashes"), "bundled advisory feed must list known-bad hashes"
    return f


@pytest.fixture(scope="module")
def result(graph: Graph, feed: dict) -> HygieneResult:
    # scan a fresh copy of the graph so engine annotation never bleeds across tests
    g = HermesGraphScanner(home=str(FIX)).scan()
    return HygieneEngine(advisory_feed=feed).scan(g)


def _by_severity(findings, sev: Severity):
    return [f for f in findings if f.severity == sev]


def _crit_dicts(d: dict):
    return [f for f in d["findings"] if f["severity"] == Severity.CRITICAL.value]


# --- shape -----------------------------------------------------------------

def test_result_to_dict_has_findings_and_scores(result: HygieneResult):
    d = result.to_dict()
    assert "findings" in d and isinstance(d["findings"], list)
    assert "scores" in d and isinstance(d["scores"], dict)
    assert d["findings"], "the malicious fixture should produce findings"

    # Per-agent scores: keyed by agent id, each a {agent_id, score, findings}.
    agent_ids = {a.id for a in HermesGraphScanner(home=str(FIX)).scan().by_type(NodeType.AGENT)}
    assert agent_ids, "fixture should have at least one agent"
    assert agent_ids <= set(d["scores"]), "every agent must appear in scores"
    for aid, sc in d["scores"].items():
        assert sc["agent_id"] == aid
        assert isinstance(sc["score"], int)
        assert sc["score"] >= 0
        assert isinstance(sc["findings"], list)


def test_every_finding_carries_a_kind(result: HygieneResult):
    valid = {FindingKind.CAPABILITY, FindingKind.CONFIG, FindingKind.ALERT}
    for fd in result.to_dict()["findings"]:
        assert fd["kind"] in valid, f"finding {fd['id']} has bad kind {fd['kind']!r}"
        # kind must be set by the engine, never left to re-derive from the id.
        assert fd["kind"]


def test_findings_carry_enumerated_factors_not_just_a_number(result: HygieneResult):
    # The whole point of the engine: output is a score WITH enumerated factors.
    for f in result.findings:
        assert f.factors, f"finding {f.id} must enumerate its factors"
        assert all(isinstance(x, str) and x for x in f.factors)


# --- happy path: the exfil triad CRITICAL ----------------------------------

def test_exfil_triad_critical_present(result: HygieneResult):
    crits = _by_severity(result.findings, Severity.CRITICAL)
    assert crits, "fixture must yield at least one CRITICAL finding"

    # The self-authored pi-temp-watch skill: shell + credential_read + network.
    triads = [f for f in crits if f.id.startswith("triad:")]
    assert triads, "expected a CRITICAL exfil-triad finding from the self-authored skill"
    t = triads[0]
    assert {"credential_read", "network", "shell"} <= set(t.factors)
    assert "self-authored/local" in t.factors
    assert "triad" in t.id.lower() or "exfil" in t.title.lower()
    # A dangerous, escalated finding must tell the operator what to do.
    assert t.remediation, "the self-authored triad finding must carry a remediation"
    assert t.kind == FindingKind.CAPABILITY


def test_critical_findings_have_kind_and_remediation(result: HygieneResult):
    d = result.to_dict()
    crits = _crit_dicts(d)
    assert crits, "must have CRITICAL findings"
    for fd in crits:
        assert fd["kind"], f"{fd['id']} missing kind"
        assert fd["remediation"], f"CRITICAL {fd['id']} must carry a remediation"


# --- advisory feed fingerprint match ---------------------------------------

def test_advisory_feed_fingerprint_match_present(result: HygieneResult):
    fp = [f for f in result.findings if f.id.startswith("fp:")]
    assert fp, "bundled advisory feed should fingerprint-match the community skill"
    f = fp[0]
    assert f.severity == Severity.CRITICAL
    assert f.kind == FindingKind.ALERT, "a fingerprint hit is a verified problem (alert)"
    assert "advisory feed match" in f.factors
    assert f.remediation, "fingerprint match must carry a remediation"


def test_no_fingerprint_match_without_feed():
    # Same graph, empty feed -> the fp: alert must NOT fire (degrade path).
    g = HermesGraphScanner(home=str(FIX)).scan()
    res = HygieneEngine(advisory_feed={}).scan(g)
    assert not [f for f in res.findings if f.id.startswith("fp:")], (
        "no advisory feed => no fingerprint alert"
    )
    # The static triad CRITICAL is independent of the feed and still fires.
    assert [f for f in res.findings if f.id.startswith("triad:")], (
        "triad detection must not depend on the advisory feed"
    )


# --- scoring + annotation invariants ---------------------------------------

def test_scores_aggregate_finding_weights_per_agent(result: HygieneResult):
    # Each agent's score equals the sum of its findings' severity weights, and a
    # graph with CRITICALs must produce a strictly positive score for its owner.
    assert result.scores
    total_crit_weight = Severity.CRITICAL.weight
    any_positive = False
    for rs in result.scores.values():
        assert rs.score == sum(f.severity.weight for f in rs.findings)
        # findings are ordered worst-first
        weights = [f.severity.weight for f in rs.findings]
        assert weights == sorted(weights, reverse=True)
        if rs.score > 0:
            any_positive = True
    assert any_positive, "the malicious fixture must score above zero for some agent"
    assert total_crit_weight > 0  # sanity on the weight table


def test_empty_graph_degrades_to_no_findings():
    res = HygieneEngine(advisory_feed=load_advisory_feed(_BUNDLED_FEED)).scan(Graph())
    d = res.to_dict()
    assert d["findings"] == []
    assert d["scores"] == {}


def test_load_advisory_feed_missing_path_is_empty_not_error(tmp_path: Path):
    # A stale/absent feed must never break a scan — it yields an empty dict.
    missing = tmp_path / "nope.json"
    assert load_advisory_feed(missing) == {}
    assert load_advisory_feed(None) == {}
