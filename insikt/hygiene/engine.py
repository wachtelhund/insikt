"""The hygiene engine: orchestrates the static detectors, escalates dangerous
combinations, scores per agent, and annotates the graph for risk-colouring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..model import Finding, Graph, NodeType, Rel, RiskScore, Severity
from . import rules

# Capability categories that together form the "exfil triad" (README §6).
_EXFIL_TRIAD = {"shell", "network", "credential_read"}
_RISKY_DECLARED_TOOLS = {"shell", "web", "network", "messaging"}


def _is_wildcard_bind(bind: str) -> bool:
    """True if a gateway bind exposes all interfaces (IPv4 ``0.0.0.0`` or IPv6
    ``::`` / ``[::]``), tolerating ``host:port`` and ``[host]:port`` forms."""
    host = (bind or "").strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    if host.startswith("["):            # [::]:8765 / [::1]:8765
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:          # 0.0.0.0:8765 (IPv4 host:port)
        host = host.rsplit(":", 1)[0]
    return host in ("0.0.0.0", "::", "")


def load_advisory_feed(path: Optional[str | Path]) -> dict:
    """Load a (future: signed) advisory feed of known-bad skill hashes.

    Shape: ``{"version": "...", "known_bad_hashes": ["<sha256>", ...]}``. Missing
    or unreadable feeds yield an empty feed rather than an error — a stale/absent
    feed must never break a scan.
    """
    if not path:
        return {}
    p = Path(path).expanduser()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


@dataclass
class HygieneResult:
    findings: list[Finding] = field(default_factory=list)
    scores: dict[str, RiskScore] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "scores": {aid: s.to_dict() for aid, s in self.scores.items()},
        }


class HygieneEngine:
    def __init__(
        self,
        advisory_feed: Optional[dict] = None,
        allowlist_hosts: Optional[set[str]] = None,
    ):
        self.feed = advisory_feed or {}
        self.allowlist = set(allowlist_hosts or rules.DEFAULT_HOST_ALLOWLIST)
        self._known_bad = {h.lower() for h in self.feed.get("known_bad_hashes", [])}

    def scan(self, graph: Graph, *, drift: Optional[dict] = None) -> HygieneResult:
        findings: list[Finding] = []

        for skill in graph.by_type(NodeType.SKILL):
            findings.extend(self._scan_skill(graph, skill))

        findings.extend(self._scan_exposure(graph))
        findings.extend(self._scan_posture(graph))
        findings.extend(self._scan_drift(graph, drift))

        self._annotate(graph, findings)
        scores = self._score(graph, findings)
        return HygieneResult(findings=findings, scores=scores)

    # --- per-skill --------------------------------------------------------
    def _skill_capabilities(self, skill_props: dict) -> dict[str, list[str]]:
        caps = rules.detect_capabilities(skill_props.get("body", "") or "")
        # Fold in *declared* capability so a skill that declares shell but whose
        # body we couldn't read still counts (lower bound, README §10.4).
        declared_tools = {str(t).lower() for t in (skill_props.get("declared_tools") or [])}
        if declared_tools & {"shell"}:
            caps.setdefault("shell", []).append("declared:shell")
        if declared_tools & {"web", "network", "messaging"} or skill_props.get("declared_network"):
            caps.setdefault("network", []).append("declared:network")
        if skill_props.get("declared_credentials"):
            caps.setdefault("credential_read", []).append("declared:credentials")
        return caps

    def _scan_skill(self, graph: Graph, skill) -> list[Finding]:
        out: list[Finding] = []
        sid = skill.id
        props = skill.props

        # 1. Fingerprint against advisory feed.
        h = (props.get("origin_hash") or "").lower()
        if h and h in self._known_bad:
            out.append(
                Finding(
                    id=f"fp:{sid}",
                    severity=Severity.CRITICAL,
                    title="Skill matches a known-bad advisory hash",
                    detail=f"{skill.label}: origin_hash {h[:12]}… is on the advisory feed",
                    node_id=sid,
                    factors=[f"hash {h[:12]}…", "advisory feed match"],
                )
            )

        # 2. Static content scan -> one finding per detected category.
        caps = self._skill_capabilities(props)
        for category, evidence in caps.items():
            sev = Severity(rules.CATEGORY_SEVERITY[category])
            # A self-authored skill exercising a sensitive capability is notable.
            if props.get("self_authored") and category in ("shell", "network"):
                sev = Severity.MEDIUM if sev == Severity.LOW else sev
            out.append(
                Finding(
                    id=f"cap:{category}:{sid}",
                    severity=sev,
                    title=rules.CATEGORY_TITLE[category],
                    detail=f"{skill.label}: {', '.join(evidence[:3])}",
                    node_id=sid,
                    factors=[category, *(["self-authored"] if props.get("self_authored") else [])],
                )
            )

        # 2b. Egress to non-allowlisted hosts.
        hosts = rules.extract_hosts(props.get("body", ""), props.get("declared_network") or [])
        bad_hosts = rules.non_allowlisted_hosts(hosts, self.allowlist)
        if bad_hosts:
            out.append(
                Finding(
                    id=f"egress:{sid}",
                    severity=Severity.MEDIUM,
                    title="Egress to non-allowlisted host(s)",
                    detail=f"{skill.label}: {', '.join(bad_hosts[:5])}",
                    node_id=sid,
                    factors=[f"host:{h}" for h in bad_hosts[:5]],
                )
            )

        # 3. Capability blast radius — the exfil triad.
        present = set(caps.keys())
        if _EXFIL_TRIAD.issubset(present):
            out.append(
                Finding(
                    id=f"triad:{sid}",
                    severity=Severity.CRITICAL,
                    title="Exfiltration triad: credential read + network egress + shell",
                    detail=(
                        f"{skill.label} combines all three capabilities in one skill — "
                        "the classic data-exfiltration shape."
                    ),
                    node_id=sid,
                    factors=["credential_read", "network", "shell", *(["self-authored"] if props.get("self_authored") else [])],
                )
            )
        return out

    # --- exposure (README §6) --------------------------------------------
    def _scan_exposure(self, graph: Graph) -> list[Finding]:
        out: list[Finding] = []
        for agent in graph.by_type(NodeType.AGENT):
            props = agent.props
            bind = str(props.get("gateway_bind") or "")
            auth = str(props.get("auth_mode") or "unknown").lower()
            exposed_bind = _is_wildcard_bind(bind)
            no_auth = auth in ("none", "", "unknown", "off", "false")

            stranger_connectors = [
                c for c in graph.neighbors(agent.id, Rel.REACHABLE_VIA)
                if c.props.get("accepts_strangers")
            ]

            if exposed_bind and no_auth:
                sev = Severity.CRITICAL if stranger_connectors else Severity.HIGH
                factors = [f"gateway_bind={bind}", f"auth={auth}"]
                if stranger_connectors:
                    factors.append("connector accepts strangers")
                out.append(
                    Finding(
                        id=f"exposure:{agent.id}",
                        severity=sev,
                        title="Gateway exposed without authentication",
                        detail=f"{agent.label}: bound to {bind} with auth '{auth}'",
                        node_id=agent.id,
                        agent_id=agent.id,
                        factors=factors,
                    )
                )
            elif exposed_bind:
                out.append(
                    Finding(
                        id=f"exposure:{agent.id}",
                        severity=Severity.MEDIUM,
                        title="Gateway bound to all interfaces",
                        detail=f"{agent.label}: bound to {bind} (auth '{auth}')",
                        node_id=agent.id,
                        agent_id=agent.id,
                        factors=[f"gateway_bind={bind}", f"auth={auth}"],
                    )
                )

            for c in stranger_connectors:
                out.append(
                    Finding(
                        id=f"stranger:{agent.id}:{c.id}",
                        severity=Severity.MEDIUM,
                        title="Connector accepts messages from strangers",
                        detail=f"{agent.label} reachable via {c.label}, which accepts unsolicited messages",
                        node_id=c.id,
                        agent_id=agent.id,
                        factors=[f"connector={c.label}", "accepts_strangers"],
                    )
                )

            if props.get("tailscale_exposed"):
                out.append(
                    Finding(
                        id=f"overlay:{agent.id}",
                        severity=Severity.MEDIUM,
                        title="Agent exposed beyond the private overlay",
                        detail=f"{agent.label}: tailscale exposure enabled",
                        node_id=agent.id,
                        agent_id=agent.id,
                        factors=["tailscale_exposed"],
                    )
                )
        return out

    # --- security posture (framework config, e.g. Hermes) ----------------
    def _scan_posture(self, graph: Graph) -> list[Finding]:
        """Findings from the agent's own safety config. Each only fires when the
        agent actually reports that setting (None = framework doesn't expose it),
        so this never produces noise for collectors that don't populate it."""
        out: list[Finding] = []
        checks = [
            ("tirith_enabled", False, Severity.MEDIUM, "Skill security scanner is disabled",
             "the agent's static skill scanner (tirith) is turned off"),
            ("allow_lazy_installs", True, Severity.MEDIUM, "Unattended skill installs are allowed",
             "skills can be installed without explicit confirmation"),
            ("guard_agent_created", False, Severity.MEDIUM, "Self-authored skills are not guarded",
             "skills the agent writes for itself are not gated before use"),
        ]
        for agent in graph.by_type(NodeType.AGENT):
            p = agent.props
            for key, bad, sev, title, detail in checks:
                if key in p and p.get(key) == bad:
                    out.append(Finding(
                        id=f"posture:{key}:{agent.id}", severity=sev, title=title,
                        detail=f"{agent.label}: {detail}", node_id=agent.id, agent_id=agent.id,
                        factors=[f"{key}={p.get(key)}"],
                    ))
        return out

    # --- drift (README §6) -----------------------------------------------
    def _scan_drift(self, graph: Graph, drift: Optional[dict]) -> list[Finding]:
        if not drift:
            return []
        out: list[Finding] = []
        for ev in drift.get("capability_drift", []):
            sid = ev.get("skill_id")
            out.append(
                Finding(
                    id=f"drift:{sid}",
                    severity=Severity.HIGH,
                    title="Self-authored skill gained sensitive capability",
                    detail=(
                        f"{ev.get('skill')} newly requires '{ev.get('gained_tool')}' "
                        "access since the previous snapshot"
                    ),
                    node_id=sid,
                    factors=["capability drift", f"gained:{ev.get('gained_tool')}", "self-authored"],
                )
            )
        return out

    # --- annotation + scoring --------------------------------------------
    @staticmethod
    def _annotate(graph: Graph, findings: list[Finding]) -> None:
        worst: dict[str, Severity] = {}
        for f in findings:
            if not f.node_id:
                continue
            cur = worst.get(f.node_id)
            if cur is None or f.severity.weight > cur.weight:
                worst[f.node_id] = f.severity
        for node_id, sev in worst.items():
            node = graph.get(node_id)
            if node:
                node.props["risk"] = sev.value

    @staticmethod
    def _owners(graph: Graph, finding: Finding) -> set[str]:
        if finding.agent_id:
            return {finding.agent_id}
        nid = finding.node_id
        if not nid:
            return set()
        node = graph.get(nid)
        if node is None:
            return set()
        if node.type == NodeType.AGENT:
            return {nid}
        if node.type == NodeType.SKILL:
            return {e.src for e in graph.edges_to(nid, Rel.USES)}
        if node.type == NodeType.CONNECTOR:
            return {e.src for e in graph.edges_to(nid, Rel.REACHABLE_VIA)}
        return set()

    def _score(self, graph: Graph, findings: list[Finding]) -> dict[str, RiskScore]:
        scores: dict[str, RiskScore] = {
            a.id: RiskScore(agent_id=a.id, score=0, findings=[])
            for a in graph.by_type(NodeType.AGENT)
        }
        for f in findings:
            for owner in self._owners(graph, f):
                rs = scores.setdefault(owner, RiskScore(agent_id=owner, score=0, findings=[]))
                rs.findings.append(f)
                rs.score += f.severity.weight
        # Order each agent's findings worst-first.
        for rs in scores.values():
            rs.findings.sort(key=lambda f: f.severity.weight, reverse=True)
        return scores
