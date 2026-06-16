"""Append-only SQLite snapshot store + meta-audit log (README §7).

Each ``insikt scan`` writes one immutable, timestamped snapshot (nodes + edges +
scan metadata). Snapshots are never mutated, so:

* diffs over time come for free (``diff``), and
* you get an immutable-ish history of how an agent evolved.

The store also keeps a **meta-audit** log: every query made *to* Insikt — the
human's and the agent's own MCP calls — is appended here (README §4.3), giving
tamper-evidence and the tidy recursion "the agent asked itself what it did."

Pure stdlib (``sqlite3`` + ``json``) so the core has no runtime dependency.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .model import Edge, Graph, Node, NodeType, Rel, ToolKind

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    tool_version    TEXT NOT NULL,
    host            TEXT,
    partial         INTEGER NOT NULL DEFAULT 0,
    partial_reasons TEXT NOT NULL DEFAULT '[]',
    meta            TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS nodes (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    id          TEXT NOT NULL,
    type        TEXT NOT NULL,
    label       TEXT NOT NULL,
    props       TEXT NOT NULL DEFAULT '{}',
    ts          TEXT,
    PRIMARY KEY (snapshot_id, id)
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(snapshot_id, type);
CREATE INDEX IF NOT EXISTS idx_nodes_ts   ON nodes(snapshot_id, ts);

CREATE TABLE IF NOT EXISTS edges (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    src         TEXT NOT NULL,
    rel         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, src, rel, dst)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(snapshot_id, src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(snapshot_id, dst);

CREATE TABLE IF NOT EXISTS meta_audit (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    tool   TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    agent  TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            self.path = str(Path(self.path).expanduser())
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- writing ----------------------------------------------------------
    def write_snapshot(
        self,
        graph: Graph,
        *,
        tool_version: str,
        host: Optional[str] = None,
        meta: Optional[dict] = None,
        ts: Optional[str] = None,
    ) -> int:
        ts = ts or _now_iso()
        cur = self.conn.execute(
            "INSERT INTO snapshots (ts, tool_version, host, partial, partial_reasons, meta)"
            " VALUES (?,?,?,?,?,?)",
            (
                ts,
                tool_version,
                host,
                1 if graph.partial else 0,
                json.dumps(graph.partial_reasons),
                json.dumps(meta or {}, default=str),
            ),
        )
        snap_id = int(cur.lastrowid)
        self.conn.executemany(
            "INSERT INTO nodes (snapshot_id, id, type, label, props, ts) VALUES (?,?,?,?,?,?)",
            [
                (snap_id, n.id, n.type.value, n.label, json.dumps(n.props, default=str), n.ts)
                for n in graph.nodes.values()
            ],
        )
        self.conn.executemany(
            "INSERT INTO edges (snapshot_id, src, rel, dst) VALUES (?,?,?,?)",
            [(snap_id, e.src, e.rel.value, e.dst) for e in graph.edges],
        )
        self.conn.commit()
        return snap_id

    # --- reading ----------------------------------------------------------
    def latest_snapshot_id(self) -> Optional[int]:
        row = self.conn.execute("SELECT MAX(id) AS m FROM snapshots").fetchone()
        return int(row["m"]) if row and row["m"] is not None else None

    def previous_snapshot_id(self, before: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT MAX(id) AS m FROM snapshots WHERE id < ?", (before,)
        ).fetchone()
        return int(row["m"]) if row and row["m"] is not None else None

    def get_snapshot(self, snapshot_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["partial"] = bool(d["partial"])
        d["partial_reasons"] = json.loads(d["partial_reasons"])
        d["meta"] = json.loads(d["meta"])
        counts = self.conn.execute(
            "SELECT type, COUNT(*) AS c FROM nodes WHERE snapshot_id = ? GROUP BY type",
            (snapshot_id,),
        ).fetchall()
        d["node_counts"] = {r["type"]: r["c"] for r in counts}
        return d

    def list_snapshots(self) -> list[dict]:
        rows = self.conn.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
        return [self.get_snapshot(int(r["id"])) for r in rows]

    def load_graph(self, snapshot_id: Optional[int] = None) -> Optional[Graph]:
        if snapshot_id is None:
            snapshot_id = self.latest_snapshot_id()
        if snapshot_id is None:
            return None
        snap = self.get_snapshot(snapshot_id)
        if snap is None:
            return None
        g = Graph(partial=snap["partial"], partial_reasons=list(snap["partial_reasons"]))
        for r in self.conn.execute(
            "SELECT id, type, label, props, ts FROM nodes WHERE snapshot_id = ?",
            (snapshot_id,),
        ):
            g.add_node(
                Node.from_row(
                    {
                        "id": r["id"],
                        "type": r["type"],
                        "label": r["label"],
                        "props": json.loads(r["props"]),
                        "ts": r["ts"],
                    }
                )
            )
        edges = [
            Edge(src=r["src"], rel=Rel(r["rel"]), dst=r["dst"])
            for r in self.conn.execute(
                "SELECT src, rel, dst FROM edges WHERE snapshot_id = ?", (snapshot_id,)
            )
        ]
        g.set_edges(edges)
        return g

    # --- diff (README §4.1 insikt_diff, §6 drift) -------------------------
    def diff(self, since_id: int, to_id: Optional[int] = None) -> dict:
        if to_id is None:
            to_id = self.latest_snapshot_id()
        old = self.load_graph(since_id)
        new = self.load_graph(to_id)
        if old is None or new is None:
            raise ValueError("snapshot not found for diff")
        return diff_graphs(old, new, since_id=since_id, to_id=to_id, store=self)

    # --- meta-audit (README §4.3) -----------------------------------------
    def log_query(self, tool: str, params: Optional[dict] = None, agent: Optional[str] = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO meta_audit (ts, tool, params, agent) VALUES (?,?,?,?)",
            (_now_iso(), tool, json.dumps(params or {}), agent),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_queries(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT ts, tool, params, agent FROM meta_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params"])
            out.append(d)
        return out


# --- pure diff over two graphs (no store needed) --------------------------
_RISKY_TOOL_KINDS = {ToolKind.SHELL, ToolKind.WEB}


def _skill_label(g: Graph, skill_id: str) -> str:
    n = g.get(skill_id)
    return n.label if n else skill_id


def diff_graphs(
    old: Graph,
    new: Graph,
    *,
    since_id: Optional[int] = None,
    to_id: Optional[int] = None,
    store: Optional["Store"] = None,
) -> dict:
    """Structured diff: new/removed skills, new credential reads, new connectors,
    new reachable hosts, new models, and capability *drift* on self-authored
    skills (gained shell/network access)."""

    def ids(g: Graph, t: NodeType) -> set[str]:
        return {n.id for n in g.by_type(t)}

    def edgeset(g: Graph, rel: Rel) -> set[tuple[str, str]]:
        return {(e.src, e.dst) for e in g.edges if e.rel == rel}

    new_skills = ids(new, NodeType.SKILL) - ids(old, NodeType.SKILL)
    removed_skills = ids(old, NodeType.SKILL) - ids(new, NodeType.SKILL)
    new_connectors = ids(new, NodeType.CONNECTOR) - ids(old, NodeType.CONNECTOR)
    new_models = ids(new, NodeType.MODEL) - ids(old, NodeType.MODEL)

    new_cred_reads = edgeset(new, Rel.READS) - edgeset(old, Rel.READS)

    # Reachable hosts = Resource nodes of kind 'host' newly present.
    def host_ids(g: Graph) -> set[str]:
        return {n.id for n in g.by_type(NodeType.RESOURCE) if n.props.get("kind") == "host"}

    new_hosts = host_ids(new) - host_ids(old)

    # Drift: a self-authored skill that newly requires a shell/network tool.
    old_reqs = edgeset(old, Rel.REQUIRES)
    new_reqs = edgeset(new, Rel.REQUIRES)
    gained = new_reqs - old_reqs
    drift = []
    for skill_id, tool_id in gained:
        skill = new.get(skill_id)
        tool = new.get(tool_id)
        if not skill or skill.type != NodeType.SKILL:
            continue
        if not skill.props.get("self_authored"):
            continue
        kind = tool.props.get("kind") if tool else None
        if kind in _RISKY_TOOL_KINDS and skill_id not in new_skills:
            drift.append(
                {
                    "skill_id": skill_id,
                    "skill": skill.label,
                    "gained_tool": kind,
                }
            )

    def labelled(g: Graph, id_set) -> list[dict]:
        out = []
        for nid in sorted(id_set):
            n = g.get(nid)
            out.append({"id": nid, "label": n.label if n else nid})
        return out

    summary_bits = []
    if new_skills:
        summary_bits.append(f"{len(new_skills)} new skill(s)")
    if new_cred_reads:
        summary_bits.append(f"{len(new_cred_reads)} new credential read(s)")
    if new_connectors:
        summary_bits.append(f"{len(new_connectors)} new connector(s)")
    if new_hosts:
        summary_bits.append(f"{len(new_hosts)} new reachable host(s)")
    if drift:
        summary_bits.append(f"{len(drift)} capability-drift event(s)")
    if removed_skills:
        summary_bits.append(f"{len(removed_skills)} removed skill(s)")
    if not summary_bits:
        summary_bits.append("no capability changes")

    return {
        "since": {"id": since_id},
        "to": {"id": to_id},
        "new_skills": labelled(new, new_skills),
        "removed_skills": labelled(old, removed_skills),
        "new_credential_reads": [
            {
                "skill": _skill_label(new, s),
                "skill_id": s,
                "credential": (new.get(c).label if new.get(c) else c),
                "credential_id": c,
            }
            for (s, c) in sorted(new_cred_reads)
        ],
        "new_connectors": labelled(new, new_connectors),
        "new_reachable_hosts": labelled(new, new_hosts),
        "new_models": labelled(new, new_models),
        "capability_drift": drift,
        "summary": "; ".join(summary_bits),
    }
