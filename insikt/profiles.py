"""Declarative collector **profiles** — where each thing lives + how to read it.

A profile is plain data (a dict, persisted as YAML). Insikt ships a built-in
profile per known framework, and a user (or their agent, via ``insikt
configure``) can drop an override at ``~/.insikt/profiles/<framework>.yaml`` —
the override is shallow-merged over the built-in. This is how Insikt adapts to
real-world layout and version drift without code changes (README/SPEC §3, §10.3):
the agent already knows its own filesystem, so it can describe it.

Reads are scoped to the agent's home directory (a footgun guard, not a trust
control): a path that escapes the home is ignored.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

PROFILE_DIR = Path("~/.insikt/profiles").expanduser()

# Built-in profile for the real Hermes layout (reverse-engineered from a live
# ~/.hermes). Paths are relative to `home`; dotted strings index into config.yaml.
HERMES_PROFILE: dict = {
    "framework": "hermes",
    "home": "~/.hermes",
    "agent_id": "main",
    "config_file": "config.yaml",
    "env_file": ".env",
    "config": {
        "version_key": "_config_version",
        "model_name": "model.default",
        "model_provider": "model.provider",
        "gateway_section": "gateway",
        "approvals_section": "approvals",
        "security_section": "security",
        "skills_section": "skills",
        "memory_section": "memory",
        # platform sections that, if present, indicate a messaging connector
        "platform_sections": [
            "slack", "telegram", "discord", "whatsapp", "matrix", "signal",
            "mattermost", "email", "sms", "teams", "google_chat", "line",
        ],
    },
    "channel_directory": "channel_directory.json",
    "skills_glob": "skills/**/SKILL.md",
    "skills_usage": "skills/.usage.json",
    "bundled_manifest": "skills/.bundled_manifest",
    "sessions_file": "sessions/sessions.json",
    "cron_file": "cron/jobs.json",
    "memory_file": "memories/MEMORY.md",
    "honcho_file": "honcho.json",
}

# Built-in profile for OpenClaw (lean; the layout used by the v0 fixture).
OPENCLAW_PROFILE: dict = {
    "framework": "openclaw",
    "home": "~/.openclaw",
    "agent_id": "default",
    "config_file": "openclaw.json",
    "credentials_dir": "credentials",
    "skills_dir": "skills",
    "usage_file": "usage.jsonl",
}

BUILTINS = {"hermes": HERMES_PROFILE, "openclaw": OPENCLAW_PROFILE}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile(framework: str, *, home: Optional[str] = None) -> dict:
    """Built-in profile for ``framework``, shallow-merged with any user override
    at ``~/.insikt/profiles/<framework>.yaml``. ``home`` overrides the root dir."""
    profile = dict(BUILTINS.get(framework, {"framework": framework}))
    override_path = PROFILE_DIR / f"{framework}.yaml"
    if override_path.exists():
        try:
            import yaml

            override = yaml.safe_load(override_path.read_text(encoding="utf-8")) or {}
            if isinstance(override, dict):
                profile = _deep_merge(profile, override)
        except Exception:
            pass  # a broken override must never block a scan
    if home:
        profile["home"] = home
    return profile


def save_profile(framework: str, profile: dict) -> Path:
    """Persist a profile override (used by ``insikt configure``)."""
    import yaml

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILE_DIR / f"{framework}.yaml"
    path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    return path


def scoped(home: Path, rel: str) -> Optional[Path]:
    """Resolve ``rel`` under ``home``, refusing paths that escape the home dir."""
    if not rel:
        return None
    p = (home / rel).resolve()
    try:
        p.relative_to(home.resolve())
    except ValueError:
        return None
    return p
