from insikt.model import Graph, NodeType, Rel
from insikt.store import Store, diff_graphs


def test_snapshot_roundtrip(hermes_graph, tmp_db):
    store = Store(tmp_db)
    sid = store.write_snapshot(hermes_graph, tool_version="test", host="pi-hermes")
    loaded = store.load_graph(sid)
    assert len(loaded.nodes) == len(hermes_graph.nodes)
    assert set(e for e in loaded.edges) == set(hermes_graph.edges)
    assert loaded.partial == hermes_graph.partial
    snap = store.get_snapshot(sid)
    assert snap["host"] == "pi-hermes"
    assert snap["node_counts"]["skill"] == 3
    store.close()


def test_append_only_snapshots(hermes_graph, tmp_db):
    store = Store(tmp_db)
    s1 = store.write_snapshot(hermes_graph, tool_version="t")
    s2 = store.write_snapshot(hermes_graph, tool_version="t")
    assert s2 > s1
    assert len(store.list_snapshots()) == 2
    assert store.latest_snapshot_id() == s2
    assert store.previous_snapshot_id(s2) == s1
    store.close()


def test_meta_audit(tmp_db):
    store = Store(tmp_db)
    store.log_query("insikt_query_actions", {"window": "yesterday"}, agent="hermes/default")
    store.log_query("insikt_self_report", {}, None)
    rows = store.list_queries()
    assert len(rows) == 2
    assert rows[0]["tool"] == "insikt_self_report"  # newest first
    assert rows[1]["params"]["window"] == "yesterday"
    store.close()


def _skill_graph(*, with_shell):
    g = Graph()
    sid = g.node(NodeType.SKILL, "hermes", "evolver", label="evolver", name="evolver", self_authored=True)
    aid = g.node(NodeType.AGENT, "hermes", "default", label="hermes/default")
    g.add_edge(aid, Rel.USES, sid)
    if with_shell:
        tid = g.node(NodeType.TOOL, "shell", label="shell", kind="shell")
        g.add_edge(sid, Rel.REQUIRES, tid)
    return g


def test_diff_new_skill_and_drift():
    old = _skill_graph(with_shell=False)
    new = _skill_graph(with_shell=True)
    # add a brand-new skill to `new`
    new.node(NodeType.SKILL, "hermes", "fresh", label="fresh", name="fresh")
    d = diff_graphs(old, new, since_id=1, to_id=2)
    labels = {s["label"] for s in d["new_skills"]}
    assert "fresh" in labels
    # evolver (self-authored) gained shell -> drift, and is NOT a new skill
    assert any(x["skill"] == "evolver" and x["gained_tool"] == "shell" for x in d["capability_drift"])
    assert "evolver" not in labels


def test_diff_new_credential_read():
    old = Graph()
    s = old.node(NodeType.SKILL, "hermes", "s", label="s", name="s")
    new = Graph()
    s2 = new.node(NodeType.SKILL, "hermes", "s", label="s", name="s")
    c = new.node(NodeType.CREDENTIAL_REF, "OPENCLAW_API_KEY", label="OPENCLAW_API_KEY", name="OPENCLAW_API_KEY")
    new.add_edge(s2, Rel.READS, c)
    d = diff_graphs(old, new, since_id=1, to_id=2)
    assert any(x["credential"] == "OPENCLAW_API_KEY" for x in d["new_credential_reads"])


def test_store_diff_via_snapshots(tmp_db):
    store = Store(tmp_db)
    s1 = store.write_snapshot(_skill_graph(with_shell=False), tool_version="t")
    s2 = store.write_snapshot(_skill_graph(with_shell=True), tool_version="t")
    d = store.diff(s1, s2)
    assert d["since"]["id"] == s1 and d["to"]["id"] == s2
    assert any(x["gained_tool"] == "shell" for x in d["capability_drift"])
    store.close()
