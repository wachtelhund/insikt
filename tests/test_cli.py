from pathlib import Path

from insikt.cli import main
from insikt.store import Store


def test_scan_end_to_end(hermes_home, openclaw_home, tmp_path, capsys):
    db = str(tmp_path / "insikt.db")
    out = tmp_path / "overview.html"
    rc = main(["scan", "--hermes-home", hermes_home, "--openclaw-home", openclaw_home, "--db", db, "--out", str(out)])
    assert rc == 0
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")

    store = Store(db)
    sid = store.latest_snapshot_id()
    assert sid is not None
    snap = store.get_snapshot(sid)
    assert set(snap["meta"]["frameworks"]) == {"hermes", "openclaw"}
    assert snap["meta"]["hygiene"]["findings"]
    store.close()

    captured = capsys.readouterr().out
    assert "report →" in captured
    assert "hygiene:" in captured


def test_scan_no_state_returns_2(tmp_path, capsys):
    db = str(tmp_path / "insikt.db")
    out = tmp_path / "o.html"
    rc = main([
        "scan", "--hermes-home", str(tmp_path / "nohermes"),
        "--openclaw-home", str(tmp_path / "noclaw"),
        "--db", db, "--out", str(out),
    ])
    assert rc == 2
    assert not out.exists()


def test_scan_then_snapshots_and_diff(hermes_home, tmp_path, capsys):
    db = str(tmp_path / "insikt.db")
    out = str(tmp_path / "o.html")
    main(["scan", "--hermes-home", hermes_home, "--no-openclaw", "--db", db, "--out", out])
    main(["scan", "--hermes-home", hermes_home, "--no-openclaw", "--db", db, "--out", out])

    rc = main(["snapshots", "--db", db])
    assert rc == 0
    assert "#2" in capsys.readouterr().out

    rc = main(["diff", "--db", db])
    assert rc == 0
    # re-scanning identical state yields no capability changes
    assert "no capability changes" in capsys.readouterr().out


def test_report_subcommand(hermes_home, tmp_path, capsys):
    db = str(tmp_path / "insikt.db")
    out = str(tmp_path / "o.html")
    main(["scan", "--hermes-home", hermes_home, "--no-openclaw", "--db", db, "--out", out])
    out2 = tmp_path / "regen.html"
    rc = main(["report", "--db", db, "--out", str(out2)])
    assert rc == 0
    assert out2.exists()
    assert "pi-temp-watch" in out2.read_text(encoding="utf-8")


def test_configure_agent_handoff(hermes_home, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("insikt.profiles.PROFILE_DIR", tmp_path / "profiles")
    rc = main(["configure", "--home", hermes_home, "--framework", "hermes", "--agent"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "insikt_describe_layout" in out  # the agent is told what to call
    assert (tmp_path / "configure-request.json").exists()


def test_configure_auto_heuristic(hermes_home, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("insikt.profiles.PROFILE_DIR", tmp_path / "profiles")
    rc = main(["configure", "--home", hermes_home, "--framework", "hermes", "--auto", "--yes"])
    assert rc == 0
    assert "proposed profile" in capsys.readouterr().out
    assert (tmp_path / "profiles" / "hermes.yaml").exists()


def test_queries_subcommand_after_mcp_impl(populated_db, capsys):
    from insikt import mcp_server

    mcp_server.self_report_impl(populated_db)
    rc = main(["queries", "--db", populated_db])
    assert rc == 0
    assert "insikt_self_report" in capsys.readouterr().out
