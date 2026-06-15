"""``insikt`` command-line interface.

Subcommands:

* ``scan``      run collectors, persist a snapshot, emit ``overview.html``.
* ``report``    re-render the HTML for an existing snapshot.
* ``diff``      print what changed between two snapshots.
* ``snapshots`` list stored snapshots.
* ``queries``   show the meta-audit log (queries made *to* Insikt).
* ``mcp``       run the read-only MCP server.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .collectors import HermesCollector, OpenClawCollector
from .hygiene import HygieneEngine, load_advisory_feed
from .model import Graph, NodeType
from .report import render_report
from .store import Store, _now_iso, diff_graphs

DEFAULT_DB = "~/.insikt/insikt.db"
DEFAULT_OUT = "overview.html"
BUNDLED_FEED = Path(__file__).resolve().parent / "data" / "advisory_feed.json"


def _build_collectors(args) -> list:
    cols = []
    if not args.no_hermes:
        cols.append(HermesCollector(home=args.hermes_home))
    if not args.no_openclaw:
        cols.append(OpenClawCollector(home=args.openclaw_home))
    return cols


def cmd_scan(args) -> int:
    collectors = _build_collectors(args)
    graph = Graph()
    frameworks: list[str] = []
    detected: dict[str, Optional[str]] = {}

    for col in collectors:
        if not col.available():
            continue
        result = col.collect()
        graph.merge(result.graph)
        frameworks.append(result.framework)
        detected[result.framework] = result.detected_version

    if not frameworks:
        print(
            "No agent state found. Looked for Hermes (~/.hermes or --hermes-home) "
            "and OpenClaw (~/.openclaw or --openclaw-home).",
            file=sys.stderr,
        )
        return 2

    host = next(
        (a.props.get("host") for a in graph.by_type(NodeType.AGENT) if a.props.get("host")),
        None,
    )
    scan_ts = _now_iso()

    # Advisory feed (pluggable; bundled sample by default).
    feed_path = args.feed
    if feed_path is None and not args.no_feed and BUNDLED_FEED.exists():
        feed_path = str(BUNDLED_FEED)
    feed = load_advisory_feed(feed_path)

    # Diff + drift vs the previous snapshot, if any.
    report_diff = None
    drift = None
    store: Optional[Store] = None
    if not args.no_store:
        store = Store(args.db)
        prev_id = store.latest_snapshot_id()
        if prev_id is not None:
            prev_graph = store.load_graph(prev_id)
            if prev_graph is not None:
                drift = diff_graphs(prev_graph, graph, since_id=prev_id, to_id=None)

    hygiene = HygieneEngine(advisory_feed=feed).scan(graph, drift=drift)

    # The static scan is done; the raw skill body is no longer needed and must
    # NOT be persisted — it can contain hardcoded secrets. Keep only the
    # redacted body_excerpt the collector already produced.
    for skill in graph.by_type(NodeType.SKILL):
        skill.props.pop("body", None)

    snapshot_id = None
    meta = {
        "title": f"Insikt — {', '.join(frameworks)} audit",
        "host": host,
        "scan_ts": scan_ts,
        "frameworks": frameworks,
        "detected_versions": detected,
        "hygiene": hygiene.to_dict(),
        "feed_version": feed.get("version"),
    }
    if store is not None:
        snapshot_id = store.write_snapshot(
            graph, tool_version=__version__, host=host, meta=meta, ts=scan_ts
        )
        if drift is not None:
            drift["to"]["id"] = snapshot_id
            report_diff = drift
        store.close()

    meta["snapshot_id"] = snapshot_id
    html = render_report(graph, meta=meta, hygiene=hygiene, diff=report_diff)
    out_path = Path(args.out).expanduser()
    out_path.write_text(html, encoding="utf-8")

    _print_scan_summary(graph, hygiene, frameworks, snapshot_id, out_path)
    if args.open:
        _open_in_browser(out_path)
    return 0


def _print_scan_summary(graph, hygiene, frameworks, snapshot_id, out_path) -> None:
    n = lambda t: len(graph.by_type(t))
    print(f"insikt {__version__} — scanned: {', '.join(frameworks)}")
    if graph.partial:
        print(f"  ⚠ partial: {'; '.join(graph.partial_reasons)}")
    print(
        f"  agents={n(NodeType.AGENT)} skills={n(NodeType.SKILL)} "
        f"tools={n(NodeType.TOOL)} connectors={n(NodeType.CONNECTOR)} "
        f"models={n(NodeType.MODEL)} creds={n(NodeType.CREDENTIAL_REF)} "
        f"actions={len(graph.actions())}"
    )
    findings = hygiene.findings
    if findings:
        by_sev: dict[str, int] = {}
        for f in findings:
            by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        sev_str = " ".join(f"{k}={v}" for k, v in sorted(by_sev.items(), key=lambda x: -len(x[0])))
        print(f"  hygiene: {len(findings)} finding(s) [{sev_str}]")
        worst = sorted(findings, key=lambda f: f.severity.weight, reverse=True)[:3]
        for f in worst:
            print(f"    • [{f.severity.value}] {f.title}")
    else:
        print("  hygiene: no findings ✓")
    if snapshot_id is not None:
        print(f"  snapshot #{snapshot_id} stored")
    print(f"  report → {out_path}")


def _open_in_browser(path: Path) -> None:
    import webbrowser

    webbrowser.open(path.resolve().as_uri())


def cmd_report(args) -> int:
    store = Store(args.db)
    try:
        sid = args.snapshot or store.latest_snapshot_id()
        if sid is None:
            print("No snapshots stored. Run `insikt scan` first.", file=sys.stderr)
            return 2
        graph = store.load_graph(sid)
        snap = store.get_snapshot(sid) or {}
        meta = snap.get("meta") or {}
        meta["snapshot_id"] = sid
        from .hygiene import HygieneResult
        from .model import Finding, RiskScore, Severity

        hy_dict = meta.get("hygiene") or {"findings": [], "scores": {}}
        hygiene = _hydrate_hygiene(hy_dict, Finding, RiskScore, Severity, HygieneResult)
        prev = store.previous_snapshot_id(sid)
        report_diff = store.diff(prev, sid) if prev is not None else None
        html = render_report(graph, meta=meta, hygiene=hygiene, diff=report_diff)
        out_path = Path(args.out).expanduser()
        out_path.write_text(html, encoding="utf-8")
        print(f"report (snapshot #{sid}) → {out_path}")
        if args.open:
            _open_in_browser(out_path)
        return 0
    finally:
        store.close()


def _hydrate_hygiene(hy_dict, Finding, RiskScore, Severity, HygieneResult):
    findings = [
        Finding(
            id=f["id"], severity=Severity(f["severity"]), title=f["title"], detail=f["detail"],
            node_id=f.get("node_id"), agent_id=f.get("agent_id"), factors=f.get("factors", []),
        )
        for f in hy_dict.get("findings", [])
    ]
    by_id = {f.id: f for f in findings}
    scores = {}
    for aid, s in hy_dict.get("scores", {}).items():
        rs_findings = [by_id[f["id"]] for f in s.get("findings", []) if f["id"] in by_id]
        scores[aid] = RiskScore(agent_id=s["agent_id"], score=s["score"], findings=rs_findings)
    return HygieneResult(findings=findings, scores=scores)


def cmd_diff(args) -> int:
    store = Store(args.db)
    try:
        to_id = args.to or store.latest_snapshot_id()
        if to_id is None:
            print("No snapshots stored.", file=sys.stderr)
            return 2
        since_id = args.since if args.since is not None else store.previous_snapshot_id(to_id)
        if since_id is None:
            print("Only one snapshot exists; nothing to diff against.", file=sys.stderr)
            return 2
        d = store.diff(since_id, to_id)
        if args.json:
            print(json.dumps(d, indent=2))
        else:
            print(f"diff #{since_id} → #{to_id}: {d['summary']}")
            for key, label in [
                ("new_skills", "new skill"),
                ("capability_drift", "capability drift"),
                ("new_credential_reads", "new credential read"),
                ("new_connectors", "new connector"),
                ("new_reachable_hosts", "new reachable host"),
                ("removed_skills", "removed skill"),
            ]:
                for item in d.get(key, []):
                    print(f"  + {label}: {item.get('label') or item.get('skill') or item}")
        return 0
    finally:
        store.close()


def cmd_snapshots(args) -> int:
    store = Store(args.db)
    try:
        snaps = store.list_snapshots()
        if not snaps:
            print("No snapshots stored.")
            return 0
        for s in snaps:
            counts = s.get("node_counts", {})
            flag = " PARTIAL" if s["partial"] else ""
            print(
                f"#{s['id']}  {s['ts']}  {s.get('host') or '-'}  "
                f"agents={counts.get('agent',0)} skills={counts.get('skill',0)} "
                f"actions={counts.get('action',0)}{flag}"
            )
        return 0
    finally:
        store.close()


def cmd_queries(args) -> int:
    store = Store(args.db)
    try:
        rows = store.list_queries(limit=args.limit)
        if not rows:
            print("No queries logged yet (meta-audit is empty).")
            return 0
        for r in rows:
            params = json.dumps(r["params"]) if r["params"] else ""
            print(f"{r['ts']}  {r['tool']}  {r.get('agent') or ''}  {params}")
        return 0
    finally:
        store.close()


def cmd_mcp(args) -> int:
    from .mcp_server import run

    run(db_path=args.db, transport=args.transport)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="insikt",
        description="Local-first, read-only auditor for self-hosted AI agents.",
    )
    p.add_argument("--version", action="version", version=f"insikt {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_db(sp):
        sp.add_argument("--db", default=DEFAULT_DB, help=f"snapshot store path (default {DEFAULT_DB})")

    sp = sub.add_parser("scan", help="collect, snapshot, and emit overview.html")
    add_db(sp)
    sp.add_argument("--hermes-home", default=None, help="path to a Hermes home (default $HERMES_HOME or ~/.hermes)")
    sp.add_argument("--openclaw-home", default=None, help="path to an OpenClaw home (default $OPENCLAW_HOME or ~/.openclaw)")
    sp.add_argument("--no-hermes", action="store_true", help="skip the Hermes collector")
    sp.add_argument("--no-openclaw", action="store_true", help="skip the OpenClaw collector")
    sp.add_argument("--out", default=DEFAULT_OUT, help=f"HTML output path (default {DEFAULT_OUT})")
    sp.add_argument("--feed", default=None, help="advisory feed JSON path (default: bundled sample)")
    sp.add_argument("--no-feed", action="store_true", help="do not load any advisory feed")
    sp.add_argument("--no-store", action="store_true", help="do not persist a snapshot (HTML only)")
    sp.add_argument("--open", action="store_true", help="open the report in a browser")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("report", help="re-render HTML for a stored snapshot")
    add_db(sp)
    sp.add_argument("--snapshot", type=int, default=None, help="snapshot id (default: latest)")
    sp.add_argument("--out", default=DEFAULT_OUT)
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("diff", help="show what changed between snapshots")
    add_db(sp)
    sp.add_argument("--since", type=int, default=None, help="baseline snapshot id (default: previous)")
    sp.add_argument("--to", type=int, default=None, help="target snapshot id (default: latest)")
    sp.add_argument("--json", action="store_true", help="emit JSON")
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("snapshots", help="list stored snapshots")
    add_db(sp)
    sp.set_defaults(func=cmd_snapshots)

    sp = sub.add_parser("queries", help="show the meta-audit log")
    add_db(sp)
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_queries)

    sp = sub.add_parser("mcp", help="run the read-only MCP server")
    add_db(sp)
    sp.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    sp.set_defaults(func=cmd_mcp)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
