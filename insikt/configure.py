"""``insikt configure`` — propose/validate/apply a collector **profile**.

The agent-assisted, low-ceremony config flow (SPEC §3, §10.3):

* For a **known** framework the built-in profile already works; configure just
  confirms/repairs paths against the real install (layout / version drift).
* For a **variant** it doesn't recognize, the agent — which knows its own
  filesystem — reads ``insikt configure --describe`` (a bounded, secret-redacted
  layout digest + the profile schema) and emits a profile, which a human applies
  with ``insikt configure --apply <file>`` (a single yes/no, or ``--yes``).

The result is a plain, editable YAML at ``~/.insikt/profiles/<framework>.yaml``.

Honest scope: a profile is consumed by a framework-specific collector. Path /
version drift of a *known* framework is fully handled here; a brand-new
framework still needs its own collector (or the future generic interpreter) —
``validate`` says so plainly rather than pretending.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .profiles import BUILTINS, PROFILE_DIR, load_profile, save_profile
from .redact import redact_secrets

# Markers that identify a framework's home directory.
FRAMEWORK_MARKERS = {
    "hermes": ["config.yaml", "skills"],
    "openclaw": ["openclaw.json"],
}

# Candidate paths probed by autodetect, keyed by profile field.
_AUTODETECT = {
    "config_file": ["config.yaml", "config.yml", "config.json", "openclaw.json"],
    "env_file": [".env"],
    "skills_glob": ["skills/**/SKILL.md", "skills/**/*.md", "**/SKILL.md", "skills/*/skill.json"],
    "bundled_manifest": ["skills/.bundled_manifest"],
    "skills_usage": ["skills/.usage.json"],
    "channel_directory": ["channel_directory.json", "channels.json"],
    "sessions_file": ["sessions/sessions.json", "sessions.json", "usage.jsonl"],
    "cron_file": ["cron/jobs.json", "cron.json"],
    "memory_file": ["memories/MEMORY.md", "memory/MEMORY.md", "MEMORY.md"],
    "honcho_file": ["honcho.json"],
}

# Short docs shown by --describe so an agent knows what each field means.
PROFILE_SCHEMA = {
    "framework": "framework key, e.g. 'hermes'",
    "home": "agent home directory (reads are scoped to it)",
    "agent_id": "stable id for the agent/profile",
    "config_file": "main config file (yaml/json), relative to home",
    "env_file": ".env file — KEY NAMES are read, never values",
    "skills_glob": "glob (relative to home) matching each skill's manifest",
    "bundled_manifest": "name:hash manifest distinguishing bundled vs self-authored",
    "skills_usage": "per-skill usage json (use_count, state, created_by)",
    "channel_directory": "json mapping platform -> [channels] for connectors",
    "sessions_file": "json/jsonl of conversations with token/cost totals",
    "cron_file": "scheduled jobs json",
    "memory_file": "memory file (markdown/db) — counted, not dumped",
    "honcho_file": "Honcho integration config (presence)",
    "config": "dotted paths into config_file (model_name, gateway_section, …)",
}

_SKIP_DIRS = {".git", "node", "sandboxes", "audio_cache", "image_cache", "vision",
              "cache", "tmp", "__pycache__", ".venv", "logs", "processes"}


def detect_framework(home: Path) -> Optional[str]:
    for fw, markers in FRAMEWORK_MARKERS.items():
        if all((home / m).exists() for m in markers):
            return fw
    for fw, markers in FRAMEWORK_MARKERS.items():
        if any((home / m).exists() for m in markers):
            return fw
    return None


def autodetect_profile(home: Path, framework: str) -> dict:
    """Build a profile by probing the home dir: start from the built-in (if
    known) and confirm/repair each path against what's actually present."""
    prof = dict(BUILTINS.get(framework, {"framework": framework, "agent_id": "default"}))
    prof["home"] = str(home)
    for field, candidates in _AUTODETECT.items():
        found = None
        for cand in candidates:
            if "*" in cand:
                if next(iter(home.glob(cand)), None) is not None:
                    found = cand
                    break
            elif (home / cand).exists():
                found = cand
                break
        if found:
            prof[field] = found
        elif field in prof and field not in ("config",):
            # built-in pointed somewhere that doesn't exist here — drop it
            if not (home / str(prof[field])).exists() and "*" not in str(prof[field]):
                prof.pop(field, None)
    return prof


def validate_profile(home: Path, framework: str, profile: dict) -> dict:
    """Run the matching collector with this profile and report what it found."""
    from .collectors import HermesCollector, OpenClawCollector
    from .model import NodeType

    if framework == "hermes":
        graph = HermesCollector(home=str(home), profile=profile).collect().graph
    elif framework == "openclaw":
        graph = OpenClawCollector(home=str(home)).collect().graph
    else:
        return {
            "supported": False,
            "message": f"No built-in collector for framework {framework!r}. The profile is "
            "saved, but reading it needs a framework collector (or the future generic "
            "interpreter). Path/version drift of a known framework IS handled.",
        }
    n = lambda t: len(graph.by_type(t))
    return {
        "supported": True,
        "partial": graph.partial,
        "reasons": graph.partial_reasons[:6],
        "counts": {
            "agents": n(NodeType.AGENT), "skills": n(NodeType.SKILL),
            "connectors": n(NodeType.CONNECTOR), "models": n(NodeType.MODEL),
            "credentials": n(NodeType.CREDENTIAL_REF), "actions": len(graph.actions()),
        },
    }


def layout_digest(home: Path, max_entries: int = 250) -> dict:
    """A bounded, secret-redacted snapshot of the home for an agent to reason
    about: a shallow tree (cache/log dirs skipped) + a few file samples."""
    tree: list[str] = []

    def walk(d: Path, depth: int) -> None:
        if depth > 3 or len(tree) >= max_entries:
            return
        try:
            entries = sorted(d.iterdir())
        except OSError:
            return
        for p in entries:
            if len(tree) >= max_entries:
                return
            if p.name in _SKIP_DIRS or p.name.endswith((".log", ".lock", ".pid")):
                continue
            rel = str(p.relative_to(home)) + ("/" if p.is_dir() else "")
            tree.append(rel)
            if p.is_dir():
                walk(p, depth + 1)

    walk(home, 0)
    samples: dict[str, str] = {}
    for rel in ("config.yaml", "openclaw.json", "channel_directory.json",
                "cron/jobs.json", "sessions/sessions.json", "honcho.json"):
        f = home / rel
        if f.exists():
            try:
                samples[rel] = redact_secrets(f.read_text(encoding="utf-8", errors="replace")[:900])
            except OSError:
                pass
    skill = next(iter(home.glob("skills/**/SKILL.md")), None) or next(iter(home.glob("**/*.md")), None)
    if skill:
        try:
            samples[str(skill.relative_to(home))] = redact_secrets(
                skill.read_text(encoding="utf-8", errors="replace")[:500])
        except OSError:
            pass
    return {"home": str(home), "framework_guess": detect_framework(home), "tree": tree, "samples": samples}


def propose(home: Path, framework: Optional[str]) -> tuple[str, dict, dict]:
    """Return (framework, proposed_profile, validation)."""
    fw = framework or detect_framework(home) or "unknown"
    profile = autodetect_profile(home, fw)
    validation = validate_profile(home, fw, profile)
    return fw, profile, validation


def describe(home: Path, framework: Optional[str]) -> dict:
    """The --describe payload an agent consumes to author/repair a profile."""
    fw = framework or detect_framework(home) or "unknown"
    return {
        "framework": fw,
        "current_profile": load_profile(fw, home=str(home)),
        "profile_schema": PROFILE_SCHEMA,
        "layout": layout_digest(home),
        "instructions": (
            "Author or repair a profile for this home so insikt can read it. Return YAML/JSON "
            "matching the schema (paths relative to home). A human applies it with "
            "`insikt configure --framework <fw> --apply <file>`."
        ),
    }
