"""The normalized data model — the framework-agnostic core.

Everything a collector reads is flattened into a tiny set of node and edge types
(README §2). Two things share this model but mean different things:

* **Capability surface** = the static graph (what an agent *could* do).
* **Audit** = the ``Action`` node stream (what it *did*).

Most of the risk lives in the gap between them, so they are kept distinct: an
``Action`` is just another node (``type == ACTION``) carrying a ``ts``, while the
capability nodes carry no timestamp.

IDs are deterministic (derived from stable identity, never random) so that the
same real-world entity gets the same id across scans — that is what makes
append-only snapshot *diffs* meaningful (README §7).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Iterator, Optional


class NodeType(str, Enum):
    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"
    MODEL = "model"
    CONNECTOR = "connector"
    RESOURCE = "resource"
    CREDENTIAL_REF = "credential_ref"
    ACTION = "action"


class Rel(str, Enum):
    USES = "uses"               # Agent  -> Skill
    REQUIRES = "requires"       # Skill  -> Tool
    CAN_ACCESS = "can_access"   # Tool   -> Resource
    READS = "reads"             # Skill  -> CredentialRef
    REACHABLE_VIA = "reachable_via"  # Agent -> Connector
    CALLED = "called"           # Agent  -> Model
    EXECUTED_BY = "executed_by"  # Action -> Agent
    VIA = "via"                 # Action -> Skill
    TOUCHED = "touched"         # Action -> Resource


# Canonical action types (README §2). Stored as a plain string on the node so a
# collector can emit something outside this set without crashing the pipeline,
# but collectors should prefer these.
class ActionType(str, Enum):
    SHELL = "shell"
    FILE_WRITE = "file_write"
    MESSAGE_SENT = "message_sent"
    SKILL_WRITTEN = "skill_written"
    MODEL_CALL = "model_call"
    MCP_CALL = "mcp_call"


class Source(str, Enum):
    BACKFILL = "backfill"  # reconstructed from already-retained logs (README §3.4)
    LIVE = "live"          # captured as it happened (README §10.1) — future


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> int:
        return {"info": 0, "low": 1, "medium": 3, "high": 7, "critical": 12}[self.value]


def make_id(node_type: NodeType, *parts: object) -> str:
    """Deterministic id from stable identity parts (``type:part:part``)."""
    tail = ":".join(str(p) for p in parts)
    return f"{node_type.value}:{tail}" if tail else node_type.value


def action_id(framework: str, ts: str, atype: str, summary: str, profile: str = "") -> str:
    """Content-addressed action id so re-scanning the same log line dedups.

    Backfill is idempotent: running ``insikt scan`` twice over the same logs must
    not double-count actions, so the id is a hash of the action's identity.
    """
    digest = hashlib.sha1(
        f"{framework}|{ts}|{atype}|{summary}|{profile}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{NodeType.ACTION.value}:{digest}"


@dataclass
class Node:
    id: str
    type: NodeType
    label: str
    props: dict = field(default_factory=dict)
    ts: Optional[str] = None  # ISO-8601; set only for ACTION nodes

    def to_row(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "props": dict(self.props),
            "ts": self.ts,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Node":
        return cls(
            id=row["id"],
            type=NodeType(row["type"]),
            label=row["label"],
            props=dict(row.get("props") or {}),
            ts=row.get("ts"),
        )


@dataclass(frozen=True)
class Edge:
    src: str
    rel: Rel
    dst: str

    def to_row(self) -> dict:
        return {"src": self.src, "rel": self.rel.value, "dst": self.dst}

    @classmethod
    def from_row(cls, row: dict) -> "Edge":
        return cls(src=row["src"], rel=Rel(row["rel"]), dst=row["dst"])


@dataclass
class Graph:
    """An in-memory normalized graph. The unit a collector produces and a
    snapshot persists. Merging two collector graphs is a plain union."""

    nodes: dict[str, Node] = field(default_factory=dict)
    _edges: set[Edge] = field(default_factory=set)
    partial: bool = False
    partial_reasons: list[str] = field(default_factory=list)

    # --- construction -----------------------------------------------------
    def add_node(self, node: Node) -> str:
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
            return node.id
        # Merge: union props, keep a non-empty label, keep a ts if either has one.
        merged = dict(existing.props)
        for k, v in node.props.items():
            if v is not None and v != []:
                merged[k] = v
        existing.props = merged
        if node.label and not existing.label:
            existing.label = node.label
        if node.ts and not existing.ts:
            existing.ts = node.ts
        return existing.id

    def node(
        self,
        node_type: NodeType,
        *id_parts: object,
        label: str = "",
        ts: Optional[str] = None,
        **props: object,
    ) -> str:
        """Convenience: build + add a node from identity parts, return its id."""
        nid = make_id(node_type, *id_parts)
        clean = {k: v for k, v in props.items() if v is not None}
        return self.add_node(Node(id=nid, type=node_type, label=label or str(id_parts[-1] if id_parts else node_type.value), props=clean, ts=ts))

    def add_edge(self, src: str, rel: Rel, dst: str) -> None:
        if src and dst:
            self._edges.add(Edge(src, rel, dst))

    def mark_partial(self, reason: str) -> None:
        self.partial = True
        if reason not in self.partial_reasons:
            self.partial_reasons.append(reason)

    def merge(self, other: "Graph") -> "Graph":
        for n in other.nodes.values():
            self.add_node(n)
        self._edges |= other._edges
        if other.partial:
            self.partial = True
        for r in other.partial_reasons:
            if r not in self.partial_reasons:
                self.partial_reasons.append(r)
        return self

    # --- access -----------------------------------------------------------
    @property
    def edges(self) -> list[Edge]:
        return sorted(self._edges, key=lambda e: (e.src, e.rel.value, e.dst))

    def get(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def by_type(self, node_type: NodeType) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]

    def actions(self) -> list[Node]:
        """Action nodes, oldest first."""
        acts = [n for n in self.nodes.values() if n.type == NodeType.ACTION]
        return sorted(acts, key=lambda n: n.ts or "")

    def edges_from(self, src: str, rel: Optional[Rel] = None) -> list[Edge]:
        return [e for e in self._edges if e.src == src and (rel is None or e.rel == rel)]

    def edges_to(self, dst: str, rel: Optional[Rel] = None) -> list[Edge]:
        return [e for e in self._edges if e.dst == dst and (rel is None or e.rel == rel)]

    def neighbors(self, src: str, rel: Rel) -> list[Node]:
        return [self.nodes[e.dst] for e in self.edges_from(src, rel) if e.dst in self.nodes]

    def set_edges(self, edges: Iterable[Edge]) -> None:
        self._edges = set(edges)

    def __len__(self) -> int:
        return len(self.nodes)


@dataclass
class Finding:
    """One hygiene/risk finding (README §6). Always carries enumerated factors —
    never just a number."""

    id: str
    severity: Severity
    title: str
    detail: str
    node_id: Optional[str] = None
    agent_id: Optional[str] = None
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "factors": list(self.factors),
        }


@dataclass
class RiskScore:
    agent_id: str
    score: int
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
        }


def iter_factor_lines(findings: Iterable[Finding]) -> Iterator[str]:
    for f in findings:
        yield f"[{f.severity.value}] {f.title}"
