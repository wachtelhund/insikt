import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
HERMES_HOME = FIXTURES / "hermes_home"
OPENCLAW_HOME = FIXTURES / "openclaw_home"

# Fixed clock so windowed queries are deterministic. currentDate in the spec is
# 2026-06-15, and the fixture actions are dated 2026-06-14, so "yesterday" hits.
NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session", autouse=True)
def _memory_db():
    """Generate the Hermes memory.db fixture (kept out of git; binary)."""
    db = HERMES_HOME / "memory" / "memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE memory (id INTEGER PRIMARY KEY, topic TEXT, content TEXT)")
    conn.executemany(
        "INSERT INTO memory (topic, content) VALUES (?, ?)",
        [
            ("pi", "the pi runs hermes"),
            ("user", "prefers terse replies"),
            ("backup", "nightly at 2am"),
            ("telegram", "chat id 12345"),
            ("weather", "stockholm"),
            ("temp", "alert above 70C"),
            ("project", "building insikt"),
        ],
    )
    conn.commit()
    conn.close()
    yield


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
