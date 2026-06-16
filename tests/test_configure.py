from pathlib import Path

from insikt import configure as cfg


def test_detect_framework(hermes_home):
    assert cfg.detect_framework(Path(hermes_home)) == "hermes"


def test_autodetect_profile(hermes_home):
    prof = cfg.autodetect_profile(Path(hermes_home), "hermes")
    assert prof["config_file"] == "config.yaml"
    assert prof["skills_glob"] == "skills/**/SKILL.md"
    assert prof["sessions_file"] == "sessions/sessions.json"
    assert prof["channel_directory"] == "channel_directory.json"
    assert prof["memory_file"] == "memories/MEMORY.md"


def test_autodetect_drops_missing_paths(tmp_path):
    # a sparse home: only a config + one SKILL.md, no sessions/cron/etc
    (tmp_path / "config.yaml").write_text("model:\n  default: x\n")
    skill = tmp_path / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\n---\nbody")
    prof = cfg.autodetect_profile(tmp_path, "hermes")
    assert prof["skills_glob"] == "skills/**/SKILL.md"
    assert "sessions_file" not in prof  # built-in default dropped — not present here
    assert "cron_file" not in prof


def test_validate_profile(hermes_home):
    prof = cfg.autodetect_profile(Path(hermes_home), "hermes")
    v = cfg.validate_profile(Path(hermes_home), "hermes", prof)
    assert v["supported"] is True
    assert v["counts"]["skills"] == 3
    assert v["counts"]["connectors"] == 2


def test_validate_unknown_framework(tmp_path):
    v = cfg.validate_profile(tmp_path, "cursor", {"framework": "cursor"})
    assert v["supported"] is False
    assert "collector" in v["message"]


def test_describe_is_redacted(hermes_home):
    d = cfg.describe(Path(hermes_home), "hermes")
    assert d["framework"] == "hermes"
    assert "profile_schema" in d and "skills_glob" in d["profile_schema"]
    assert d["layout"]["tree"]
    blob = str(d)
    # the secret VALUES (api_key/token) are redacted from the config sample ...
    assert "FAKE-do-not-use" not in blob
    assert "[REDACTED]" in d["layout"]["samples"]["config.yaml"]


def test_propose(hermes_home):
    fw, profile, validation = cfg.propose(Path(hermes_home), None)
    assert fw == "hermes"
    assert validation["counts"]["skills"] == 3


def test_extract_profile_from_fenced_block():
    text = "sure, here it is:\n```yaml\nframework: hermes\nskills_glob: a/**/X.md\n```\ndone"
    p = cfg._extract_profile(text)
    assert p["skills_glob"] == "a/**/X.md"
    assert cfg._extract_profile("not yaml at all <<<") is None


def test_agent_author_profile_drives_cli(hermes_home, monkeypatch):
    import shutil
    import subprocess

    monkeypatch.setattr(shutil, "which", lambda b: f"/usr/bin/{b}")

    class _R:
        returncode = 0
        stdout = "```yaml\nframework: hermes\nskills_glob: skills/**/SKILL.md\nconfig_file: config.yaml\n```"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    assert cfg.agent_driver_available("hermes") is True
    profile, note = cfg.agent_author_profile(Path(hermes_home), "hermes", timeout=5)
    assert note == "ok"
    assert profile["framework"] == "hermes"
    assert profile["home"] == hermes_home


def test_agent_author_profile_no_cli(hermes_home, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda b: None)
    profile, note = cfg.agent_author_profile(Path(hermes_home), "hermes")
    assert profile is None and "not found" in note
