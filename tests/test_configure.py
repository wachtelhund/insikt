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
