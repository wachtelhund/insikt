from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
HERMES_HOME = FIXTURES / "hermes_home"
OPENCLAW_HOME = FIXTURES / "openclaw_home"
CLAUDE_CODE_HOME = FIXTURES / "claude_code_home"

# Fixed clock so windowed queries are deterministic. currentDate in the spec is
# 2026-06-15, and the fixture actions are dated 2026-06-14, so "yesterday" hits.
NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def hermes_home():
    return str(HERMES_HOME)


@pytest.fixture
def openclaw_home():
    return str(OPENCLAW_HOME)


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def hermes_graph(hermes_home):
    from insikt.collectors import HermesCollector

    return HermesCollector(home=hermes_home).collect().graph


@pytest.fixture
def openclaw_graph(openclaw_home):
    from insikt.collectors import OpenClawCollector

    return OpenClawCollector(home=openclaw_home).collect().graph


@pytest.fixture
def claude_code_home():
    return str(CLAUDE_CODE_HOME)


@pytest.fixture
def claude_code_graph(claude_code_home):
    from insikt.collectors import ClaudeCodeCollector

    return ClaudeCodeCollector(home=claude_code_home).collect().graph


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "insikt.db")


@pytest.fixture
def populated_db(tmp_db, hermes_graph):
    """A snapshot store with one Hermes snapshot + persisted hygiene results."""
    from insikt import __version__
    from insikt.hygiene import HygieneEngine, load_advisory_feed
    from insikt.store import Store

    feed = load_advisory_feed(
        Path(__file__).resolve().parents[1] / "insikt" / "data" / "advisory_feed.json"
    )
    hygiene = HygieneEngine(advisory_feed=feed).scan(hermes_graph)
    # mirror cmd_scan: never persist raw skill bodies
    from insikt.model import NodeType

    for skill in hermes_graph.by_type(NodeType.SKILL):
        skill.props.pop("body", None)
    store = Store(tmp_db)
    store.write_snapshot(
        hermes_graph,
        tool_version=__version__,
        host="pi-hermes",
        meta={"frameworks": ["hermes"], "hygiene": hygiene.to_dict()},
    )
    store.close()
    return tmp_db
