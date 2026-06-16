"""``insikt`` command-line interface.

* ``scan``      one-shot whole-system report -> overview.html
* ``serve``     live read-only dashboard web server (reachable over ZeroTier)
* ``configure`` propose / apply a system profile (AI-first; agent-assisted)
* ``update``    update Insikt to the latest release
* ``mcp``       read-only MCP server for the agent
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .profiles import load_profile
from .report import render_dashboard
from .state import collect_state

DEFAULT_OUT = "overview.html"


def _overrides(args) -> dict:
    o: dict = {}
    if getattr(args, "hermes_home", None):
        o.setdefault("hermes", {})["home"] = args.hermes_home
    if getattr(args, "honcho_url", None):
        o.setdefault("honcho", {})["base_url"] = args.honcho_url
    if getattr(args, "ha_url", None):
        o.setdefault("homeassistant", {})["base_url"] = args.ha_url
    return o


def _print_summary(state: dict, out: Optional[Path] = None) -> None:
    m = state["meta"]
    print(f"insikt {__version__} — {m['host']}  ({m.get('model') or 'host'})")
    for key, s in state["sections"].items():
        flag = {"ok": "·", "warn": "!", "crit": "✗", "off": "–"}.get(s["status"], "·")
        print(f"  [{flag}] {s['title']:<14} {s['summary'][:70]}")
    print(f"  overall: {state['status']}")
    if out:
        print(f"  report → {out}")


def cmd_scan(args) -> int:
    profile = load_profile(_overrides(args))
    state = collect_state(profile)
    out = Path(args.out).expanduser()
    out.write_text(render_dashboard(state, live=False), encoding="utf-8")
    _print_summary(state, out)
    if args.open:
        import webbrowser

        webbrowser.open(out.resolve().as_uri())
    return 0


def cmd_serve(args) -> int:
    from .server import serve

    serve(load_profile(_overrides(args)), bind=args.bind, port=args.port)
    return 0


def cmd_configure(args) -> int:
    from .configure import run_configure

    return run_configure(args)


def cmd_mcp(args) -> int:
    from .mcp_server import run

    run(transport=args.transport)
    return 0


REPO = "wachtelhund/insikt"
GIT_SOURCE = f"git+https://github.com/{REPO}.git"


def _latest_wheel_url(repo: str = REPO) -> Optional[str]:
    """Resolve the latest GitHub release's wheel asset URL (stdlib; never raises)."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "insikt"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        for asset in data.get("assets", []):
            url = asset.get("browser_download_url", "")
            if url.endswith(".whl"):
                return url
    except Exception:
        return None
    return None


def cmd_update(args) -> int:
    import os
    import shutil
    import subprocess

    venv_python = sys.executable
    home = Path(sys.prefix).parent
    marker = home / "source"
    recorded = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    # Prefer: explicit override → a local-clone (dev) install → the latest release
    # wheel → the recorded source → git. This keeps `insikt update` a small download
    # (one wheel) for normal installs while still working for dev checkouts.
    if os.environ.get("INSIKT_SOURCE"):
        source = os.environ["INSIKT_SOURCE"]
    elif recorded and Path(recorded).expanduser().is_dir():
        source = recorded
    else:
        source = _latest_wheel_url() or recorded or GIT_SOURCE
    print(f"updating insikt from: {source}")
    if shutil.which("uv"):
        rc = subprocess.call(["uv", "pip", "install", "--python", venv_python, "--reinstall-package", "insikt", source])
    else:
        subprocess.call([venv_python, "-m", "pip", "install", "--upgrade", source])
        rc = subprocess.call([venv_python, "-m", "pip", "install", "--force-reinstall", "--no-deps", source])
    if rc != 0:
        print("update failed — re-run the installer:\n  curl -fsSL https://raw.githubusercontent.com/wachtelhund/insikt/main/install.sh | sh", file=sys.stderr)
        return rc
    ver = subprocess.run([venv_python, "-m", "insikt", "--version"], capture_output=True, text=True)
    print((ver.stdout or ver.stderr).strip() or "updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="insikt", description="Local-first whole-system observability for a self-hosted homelab (Raspberry Pi + Hermes + optional Honcho/Home Assistant).")
    p.add_argument("--version", action="version", version=f"insikt {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def src_args(sp):
        sp.add_argument("--hermes-home", default=None, help="Hermes home (default ~/.hermes)")
        sp.add_argument("--honcho-url", default=None, help="Honcho base URL")
        sp.add_argument("--ha-url", default=None, help="Home Assistant base URL")

    sp = sub.add_parser("scan", help="one-shot system report -> overview.html")
    src_args(sp)
    sp.add_argument("--out", default=DEFAULT_OUT)
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("serve", help="run the live read-only dashboard web server")
    src_args(sp)
    sp.add_argument("--bind", default=None, help="bind address (default 0.0.0.0 — reachable over the overlay)")
    sp.add_argument("--port", type=int, default=None, help="port (default 8420)")
    sp.set_defaults(func=cmd_serve)

    sp = sub.add_parser("configure", help="propose/apply a system profile (agent-assisted)")
    sp.add_argument("--agent", action="store_true", help="have your agent author the profile")
    sp.add_argument("--auto", action="store_true", help="use the heuristic profile")
    sp.add_argument("--apply", default=None, metavar="FILE")
    sp.add_argument("--describe", action="store_true")
    sp.add_argument("--show", action="store_true")
    sp.add_argument("--yes", action="store_true")
    sp.add_argument("--timeout", type=int, default=240)
    sp.set_defaults(func=cmd_configure)

    sp = sub.add_parser("update", help="update insikt to the latest release")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("mcp", help="run the read-only MCP server")
    sp.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    sp.set_defaults(func=cmd_mcp)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
