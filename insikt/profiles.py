"""The system **profile** — config-driven, never hardcoded.

One profile describes a homelab: where Hermes lives, the Honcho / Home Assistant
URLs + token, host thresholds, and the web-server bind. Built-in defaults fit the
standard "Hermes on a Raspberry Pi (+ optional Honcho + Home Assistant)" setup,
so anyone with a similar stack uses Insikt unchanged; a user — or their agent via
``insikt configure`` — drops an override at ``~/.insikt/profile.yaml`` (shallow,
per-section merge). Reads stay scoped to the agent home (a footgun guard).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

PROFILE_PATH = Path("~/.insikt/profile.yaml").expanduser()

# Hermes on-disk layout (what the scanner reads). Override paths under
# profile["hermes"]; defaults match a live ~/.hermes.
HERMES_LAYOUT: dict = {
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

DEFAULT_PROFILE: dict = {
    "system": {"enabled": True, "temp_warn": 70, "temp_crit": 80},
    "hermes": {"home": "~/.hermes"},
    "honcho": {"enabled": "auto", "base_url": "http://localhost:8000"},
    "homeassistant": {
        "enabled": "auto",
        "base_url": "http://localhost:8123",
        "token_file": "~/.hermes/ha_token.txt",
        "token_env": "HA_TOKEN",
    },
    "server": {"bind": "0.0.0.0", "port": 8420, "refresh": 5},
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile(overrides: Optional[dict] = None) -> dict:
    """Default profile, merged with ~/.insikt/profile.yaml and any explicit overrides."""
    profile = dict(DEFAULT_PROFILE)
    if PROFILE_PATH.exists():
        try:
            import yaml

            data = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                profile = _deep_merge(profile, data)
        except Exception:
            pass  # a broken override must never block a scan
    if overrides:
        profile = _deep_merge(profile, overrides)
    return profile


def save_profile(profile: dict) -> Path:
    import yaml

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    return PROFILE_PATH


def hermes_layout(profile: dict) -> dict:
    """Effective Hermes layout = built-in defaults + profile['hermes'] overrides."""
    return _deep_merge(HERMES_LAYOUT, profile.get("hermes") or {})


def scoped(home: Path, rel: str) -> Optional[Path]:
    """Resolve ``rel`` under ``home``, refusing paths that escape it."""
    if not rel:
        return None
    p = (home / rel).resolve()
    try:
        p.relative_to(home.resolve())
    except ValueError:
        return None
    return p
