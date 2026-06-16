"""``insikt configure`` — propose / apply the system **profile** (AI-first).

Insikt ships a built-in default profile (``DEFAULT_PROFILE``) that already fits the
standard "Hermes on a Raspberry Pi (+ optional Honcho + Home Assistant)" stack, so
``scan`` / ``serve`` work with zero config. ``configure`` is for when your layout
drifts from the defaults (a non-standard Hermes home, a different Honcho/HA URL, a
token in another place):

* ``--show``      print the effective profile (defaults + your overrides).
* ``--describe``  emit a secret-redacted layout digest + the profile schema as
                  JSON — what an agent reads to author a profile for *this* host.
* ``--agent``     drive your agent's own CLI (it knows its filesystem) to author
                  the profile from the digest, then validate + apply it.
* ``--apply F``   validate a profile file and write it to ``~/.insikt/profile.yaml``.
* ``--auto``      write the heuristic profile (detected paths + reachability).
* (no flag)       propose a profile, show what it would surface, and save it (with
                  ``--yes``) or drop a reviewable suggestion next to the profile.

Every path validates by actually running the collectors (``collect_state``) and
reporting what each section would show — no guessing.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Optional

from .profiles import (
    DEFAULT_PROFILE,
    PROFILE_PATH,
    hermes_layout,
    load_profile,
    save_profile,
)
from .redact import redact_secrets
from .state import collect_state

# Per-section field docs, surfaced by --describe so an agent knows what it's editing.
PROFILE_SCHEMA = {
    "system": {
        "enabled": "bool — collect host (Raspberry Pi) metrics",
        "temp_warn": "°C — SoC temperature that turns the host amber",
        "temp_crit": "°C — SoC temperature that turns the host red",
    },
    "hermes": {
        "home": "Hermes home directory (reads are scoped to it). Default ~/.hermes",
        "agent_id": "stable id label for the agent",
        "config_file": "main config, relative to home (default config.yaml)",
        "env_file": ".env file — KEY NAMES are read, never values",
        "skills_glob": "glob matching each skill manifest (default skills/**/SKILL.md)",
        "config": "dotted paths inside config_file (model_name, gateway_section, …)",
    },
    "honcho": {
        "enabled": "true | false | 'auto' (probe localhost)",
        "base_url": "Honcho v3 API base (default http://localhost:8000)",
    },
    "homeassistant": {
        "enabled": "true | false | 'auto'",
        "base_url": "Home Assistant base URL (default http://localhost:8123)",
        "token_file": "path to a file holding a long-lived token",
        "token_env": "env var holding the token (default HA_TOKEN)",
    },
    "server": {
        "bind": "bind address (default 0.0.0.0 — reachable over the overlay)",
        "port": "TCP port (default 8420)",
        "refresh": "live host-metric refresh seconds (default 5)",
        "chat": "{enabled,cmd,timeout} — opt-in chat box that runs the local agent "
        "CLI (default off; the server is read-only otherwise). cmd is run with the "
        "message appended as one argument, e.g. ['hermes','-z'].",
    },
}

_SKIP_DIRS = {
    ".git", "node", "node_modules", "sandboxes", "audio_cache", "image_cache",
    "vision", "cache", "tmp", "__pycache__", ".venv", "logs", "processes",
}

# How to drive a known agent's CLI for a one-shot, tool-less prompt.
AGENT_CLI = {
    "hermes": {"bin": "hermes", "args": lambda prompt: ["-z", prompt, "-t", ""]},
    "claude": {"bin": "claude", "args": lambda prompt: ["-p", prompt]},
}

_AGENT_INSTRUCTION = (
    "You are configuring Insikt — a read-only whole-system dashboard — for THIS host. "
    "Using the layout digest, reachability probes, and schema below, output ONLY a YAML "
    "profile for Insikt inside a single fenced ```yaml block (no prose). Keep the section "
    "keys (system / hermes / honcho / homeassistant / server); only include a key when it "
    "differs from the default shown in current_profile. Fix any path that is wrong for this "
    "install.\n\nDIGEST + SCHEMA:\n"
)


# --- layout inspection ----------------------------------------------------
def _hermes_home(profile: dict) -> Path:
    return Path((profile.get("hermes") or {}).get("home", "~/.hermes")).expanduser()


def layout_digest(home: Path, max_entries: int = 220) -> dict:
    """A bounded, secret-redacted snapshot of the Hermes home: a shallow tree
    (cache/log dirs skipped) plus a few redacted file samples."""
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
            tree.append(str(p.relative_to(home)) + ("/" if p.is_dir() else ""))
            if p.is_dir():
                walk(p, depth + 1)

    if home.is_dir():
        walk(home, 0)
    samples: dict[str, str] = {}
    for rel in ("config.yaml", "config.yml", "channel_directory.json", "honcho.json",
                "cron/jobs.json"):
        f = home / rel
        if f.exists():
            try:
                samples[rel] = redact_secrets(f.read_text(encoding="utf-8", errors="replace")[:900])
            except OSError:
                pass
    skill = next(iter(home.glob("skills/**/SKILL.md")), None) if home.is_dir() else None
    if skill:
        try:
            samples[str(skill.relative_to(home))] = redact_secrets(
                skill.read_text(encoding="utf-8", errors="replace")[:500])
        except OSError:
            pass
    return {"home": str(home), "exists": home.is_dir(), "tree": tree, "samples": samples}


def _reachability(profile: dict) -> dict:
    """Probe the optional sources so the agent/user sees what's actually live."""
    from .collectors.homeassistant import HomeAssistantCollector
    from .collectors.honcho import HonchoCollector

    out: dict = {}
    for cls in (HonchoCollector, HomeAssistantCollector):
        col = cls(profile)
        try:
            out[col.key] = {"base_url": getattr(col, "base", None), "reachable": bool(col.available())}
        except Exception:
            out[col.key] = {"base_url": getattr(col, "base", None), "reachable": False}
    return out


# --- proposal / validation ------------------------------------------------
def detect_profile() -> dict:
    """Heuristic profile: defaults, with the Hermes home repaired to wherever it
    actually lives and the optional sources toggled by reachability."""
    import os

    prof = copy.deepcopy(DEFAULT_PROFILE)
    for cand in (os.environ.get("HERMES_HOME"), "~/.hermes", "~/hermes", "~/.config/hermes"):
        if cand and Path(cand).expanduser().is_dir():
            prof["hermes"]["home"] = cand
            break
    reach = _reachability(prof)
    prof["honcho"]["enabled"] = bool(reach.get("honcho", {}).get("reachable"))
    prof["homeassistant"]["enabled"] = bool(reach.get("homeassistant", {}).get("reachable"))
    return prof


def validate(profile: dict) -> dict:
    """Run the collectors with this profile and report what each section finds."""
    state = collect_state(profile)
    sections = {}
    for key, sec in state["sections"].items():
        sections[key] = {
            "status": sec["status"],
            "available": sec["available"],
            "summary": sec["summary"],
            "partial": sec.get("partial", False),
            "reasons": sec.get("reasons", [])[:4],
        }
    return {"overall": state["status"], "host": state["meta"]["host"], "sections": sections}


def describe(profile: Optional[dict] = None) -> dict:
    """The --describe payload an agent consumes to author/repair a profile."""
    profile = profile or load_profile()
    home = _hermes_home(profile)
    return {
        "current_profile": profile,
        "profile_schema": PROFILE_SCHEMA,
        "hermes_layout": layout_digest(home),
        "reachability": _reachability(profile),
        "instructions": (
            "Author or repair an Insikt profile for this host. Return YAML matching the "
            "schema (only keys that differ from current_profile). A human applies it with "
            "`insikt configure --apply <file>` (or you may write it to ~/.insikt/profile.yaml)."
        ),
    }


# --- agent-driven authoring -----------------------------------------------
def _detect_agent_cli() -> Optional[str]:
    import shutil

    for name, drv in AGENT_CLI.items():
        if shutil.which(drv["bin"]):
            return name
    return None


def _extract_profile(text: str) -> Optional[dict]:
    import re

    import yaml

    m = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", text, re.DOTALL)
    blob = m.group(1) if m else text
    try:
        data = yaml.safe_load(blob)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def agent_author_profile(profile: dict, timeout: int = 240) -> tuple[Optional[dict], str]:
    """Drive a known agent CLI to author a profile from the digest. The agent
    supplies the intelligence; Insikt validates + applies, so the agent never
    runs a command itself. Returns (profile, note)."""
    import shutil
    import subprocess

    name = _detect_agent_cli()
    if not name:
        return None, "no known agent CLI (hermes/claude) found on PATH"
    drv = AGENT_CLI[name]
    binpath = shutil.which(drv["bin"])
    prompt = _AGENT_INSTRUCTION + json.dumps(describe(profile), indent=2, default=str)
    try:
        r = subprocess.run([binpath, *drv["args"](prompt)], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"{name} timed out after {timeout}s"
    except OSError as exc:
        return None, f"could not run {name}: {exc}"
    authored = _extract_profile(r.stdout or "")
    if not authored:
        return None, f"{name} did not return a parseable YAML profile"
    return authored, f"authored by {name}"


# --- output helpers -------------------------------------------------------
_FLAG = {"ok": "ok ", "warn": "warn", "crit": "CRIT", "off": "off "}


def _print_validation(val: dict) -> None:
    print(f"  host: {val['host']}    overall: {val['overall']}")
    for key, s in val["sections"].items():
        print(f"  [{_FLAG.get(s['status'], '?'):4}] {key:<14} {s['summary'][:64]}")
        for r in s.get("reasons", []):
            print(f"         · {r}")


def _load_profile_file(path: Path) -> Optional[dict]:
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"could not read {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"{path} is not a YAML mapping", file=sys.stderr)
        return None
    return data


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# --- entry point ----------------------------------------------------------
def run_configure(args) -> int:
    profile = load_profile()

    if getattr(args, "show", False):
        import yaml

        print(yaml.safe_dump(profile, sort_keys=False).rstrip())
        return 0

    if getattr(args, "describe", False):
        print(json.dumps(describe(profile), indent=2, default=str))
        return 0

    if getattr(args, "apply", None):
        candidate = _load_profile_file(Path(args.apply).expanduser())
        if candidate is None:
            return 1
        print("validating profile…")
        _print_validation(validate(candidate))
        if _confirm("apply and save to ~/.insikt/profile.yaml? [y/N] ", args.yes):
            print(f"saved → {save_profile(candidate)}")
            return 0
        print("not saved.")
        return 0

    if getattr(args, "agent", False):
        print("asking your agent to author a profile for this host…")
        authored, note = agent_author_profile(profile, timeout=getattr(args, "timeout", 240))
        if authored is None:
            print(f"agent path unavailable: {note}", file=sys.stderr)
            print("fall back to: insikt configure --describe  (hand the JSON to your agent),")
            print("then:        insikt configure --apply <file>")
            return 1
        print(f"profile {note}; validating…")
        _print_validation(validate(authored))
        if _confirm("apply and save? [y/N] ", args.yes):
            print(f"saved → {save_profile(authored)}")
            return 0
        sug = PROFILE_PATH.with_suffix(".suggested.yaml")
        save_profile_to(authored, sug)
        print(f"not saved. review it at {sug}, then: insikt configure --apply {sug}")
        return 0

    if getattr(args, "auto", False):
        prof = detect_profile()
        print("detected profile; validating…")
        _print_validation(validate(prof))
        print(f"saved → {save_profile(prof)}")
        return 0

    # default: propose + (optionally) save, never dead-end.
    prof = detect_profile()
    print("proposed profile for this host:\n")
    import yaml

    print(yaml.safe_dump(prof, sort_keys=False).rstrip() + "\n")
    print("this would surface:")
    _print_validation(validate(prof))
    print()
    if _confirm("save this as ~/.insikt/profile.yaml? [y/N] ", args.yes):
        print(f"saved → {save_profile(prof)}")
        return 0
    sug = PROFILE_PATH.with_suffix(".suggested.yaml")
    save_profile_to(prof, sug)
    print(f"not saved (the built-in defaults still work). Next steps:")
    print(f"  • review/edit {sug}, then  insikt configure --apply {sug}")
    print(f"  • or let your agent do it:  insikt configure --agent")
    return 0


def save_profile_to(profile: dict, path: Path) -> Path:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    return path
