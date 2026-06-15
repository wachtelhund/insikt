from insikt import mcp_server
from insikt.store import Store


def test_query_actions_impl(populated_db):
    res = mcp_server.query_actions_impl(populated_db, window="all")
    assert res["count"] == 6
    assert "model_call" in res["by_type"]


def test_query_actions_no_snapshot(tmp_db):
    res = mcp_server.query_actions_impl(tmp_db, window="all")
    assert res["error"] == "no_snapshot"


def test_capability_surface_impl(populated_db):
    res = mcp_server.capability_surface_impl(populated_db)
    assert res["totals"]["skills"] == 3


def test_risk_report_impl_reads_persisted(populated_db):
    res = mcp_server.risk_report_impl(populated_db)
    assert res["findings"]
    assert any(f["id"].startswith("triad:") for f in res["findings"])
    assert any(f["id"].startswith("fp:") for f in res["findings"])  # feed match persisted


def test_risk_report_impl_agent_filter(populated_db):
    res = mcp_server.risk_report_impl(populated_db, agent="research")
    assert all("research" in k for k in res["scores"])


def test_explain_impl(populated_db):
    res = mcp_server.explain_impl(populated_db, "skill:hermes:pi-temp-watch")
    assert res["detail"]["self_authored"] is True
    miss = mcp_server.explain_impl(populated_db, "nope")
    assert miss["error"] == "not_found"


def test_self_report_impl(populated_db):
    res = mcp_server.self_report_impl(populated_db)
    assert res["permissions"]["mode"] == "read-only"
    assert res["permissions"]["reads_secret_values"] is False
    assert res["provenance"]["signed"] is False


def test_diff_impl_single_snapshot(populated_db):
    res = mcp_server.diff_impl(populated_db)
    assert res["error"] == "no_baseline"


def test_every_query_is_meta_audited(populated_db):
    mcp_server.self_report_impl(populated_db)
    mcp_server.capability_surface_impl(populated_db)
    store = Store(populated_db)
    tools = {r["tool"] for r in store.list_queries()}
    store.close()
    assert {"insikt_self_report", "insikt_capability_surface"} <= tools


def test_build_server_registers_six_tools():
    import asyncio

    mcp = mcp_server.build_server(":memory:")
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "insikt_query_actions",
        "insikt_capability_surface",
        "insikt_risk_report",
        "insikt_diff",
        "insikt_explain",
        "insikt_self_report",
    }
