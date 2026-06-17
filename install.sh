#!/bin/sh
# Insikt installer (README §9.1) — one command, sets everything up.
#
#   curl -fsSL https://raw.githubusercontent.com/wachtelhund/insikt/main/install.sh | sh
#   ./install.sh                                      # from a local clone
#
# It: detects OS/arch (incl. Raspberry Pi arm64/armhf), finds a working Python
# (or uses uv to fetch one), installs Insikt into an isolated environment, puts
# `insikt` on your PATH, and runs the first scan. This is the SAME doorway the
# agent-install skill (§8) shells out to — one installer, two doorways.
#
# CAVEAT, kept in view on purpose (README §9.1): `curl | sh` is the exact
# pipe-the-internet-into-your-shell pattern Insikt's own hygiene scanner flags.
# Acceptable as a v0 expedient while the audience is small and you control the
# endpoint; the graduation path is signed/pinned/reproducible releases (§8). Even
# now: serve over HTTPS from a domain you control and verify a published checksum
# before running anything.
set -eu

# Fail fast instead of hanging on a credential prompt if the repo is private.
export GIT_TERMINAL_PROMPT=0
export PIP_DISABLE_PIP_VERSION_CHECK=1

INSIKT_HOME="${INSIKT_HOME:-$HOME/.insikt}"
BIN_DIR="${INSIKT_BIN_DIR:-$HOME/.local/bin}"
VENV="$INSIKT_HOME/venv"

say()  { printf '\033[1;33m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# --- 1. platform ----------------------------------------------------------
OS="$(uname -s)"; ARCH="$(uname -m)"
say "platform: ${OS} ${ARCH}"
case "$ARCH" in
  aarch64|arm64) say "arm64 (Raspberry Pi 64-bit / Apple Silicon)";;
  armv7l|armhf)  say "armhf (Raspberry Pi 32-bit)";;
esac

# --- 2. where to install from --------------------------------------------
# Local clone if present, else the published package (override with INSIKT_SOURCE).
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || echo "")"
if [ -z "${INSIKT_SOURCE:-}" ]; then
  if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ] && grep -q '^name = "insikt"' "$SCRIPT_DIR/pyproject.toml" 2>/dev/null; then
    INSIKT_SOURCE="$SCRIPT_DIR"   # running from a local clone
  else
    # Prefer the published release wheel — a single ~75KB download, no full repo clone.
    # (Pure-Python wheel, so one artifact works on every OS/arch; deps come from PyPI.)
    WHEEL_URL="$(curl -fsSL "https://api.github.com/repos/wachtelhund/insikt/releases/latest" 2>/dev/null | grep -o 'https://[^"]*\.whl' | head -1 || true)"
    if [ -n "$WHEEL_URL" ]; then
      INSIKT_SOURCE="$WHEEL_URL"
      # In a signed release, fetch the wheel's checksum/signature here and verify BEFORE install (§9.1).
    else
      INSIKT_SOURCE="git+https://github.com/wachtelhund/insikt.git"   # no release yet → install from source
    fi
  fi
fi
say "source: $INSIKT_SOURCE"

# --- 3. pick a working Python (>=3.10 with a functional venv/pyexpat) -----
# Homebrew's Python 3.14 currently ships a broken pyexpat that breaks pip's
# bootstrap, so we test each candidate rather than trusting `python3`.
python_works() {
  command -v "$1" >/dev/null 2>&1 || return 1
  "$1" - >/dev/null 2>&1 <<'PY'
import sys
assert sys.version_info >= (3, 10)
import ensurepip, xml.parsers.expat   # both must import for `python -m venv` + pip to work
PY
}
GOODPY=""
for c in "${INSIKT_PYTHON:-}" python3.13 python3.12 python3.11 python3.10 python3; do
  [ -n "$c" ] || continue
  if python_works "$c"; then GOODPY="$c"; break; fi
done

# --- 4. create the isolated env + install (idempotent: re-run to update) --
mkdir -p "$INSIKT_HOME" "$BIN_DIR"
PRIOR="$("$VENV/bin/insikt" --version 2>/dev/null || true)"
rm -rf "$VENV"
NOTE="installing insikt + dependencies — the first run fetches the MCP SDK and can take a minute or two on a Raspberry Pi (progress below)…"
FAIL="install failed (see the error above). If the repo is private, make it public or re-run with INSIKT_SOURCE=<path-to-a-local-clone>."
if command -v uv >/dev/null 2>&1; then
  say "using uv to build the environment"
  if [ -n "$GOODPY" ]; then uv venv --python "$GOODPY" "$VENV" >/dev/null
  else uv venv --python 3.13 "$VENV" >/dev/null; fi   # uv fetches 3.13 if no system Python works
  say "$NOTE"
  uv pip install --python "$VENV/bin/python" "$INSIKT_SOURCE" || die "$FAIL"
else
  [ -n "$GOODPY" ] || die "No working Python >=3.10 found and 'uv' is not installed.
Install uv (https://docs.astral.sh/uv/) or a working Python 3.11/3.12/3.13, then re-run."
  say "using $($GOODPY --version 2>&1) to build the environment"
  "$GOODPY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
  say "$NOTE"
  "$VENV/bin/python" -m pip install "$INSIKT_SOURCE" || die "$FAIL"
fi
ln -sf "$VENV/bin/insikt" "$BIN_DIR/insikt"
printf '%s\n' "$INSIKT_SOURCE" > "$INSIKT_HOME/source"   # remembered by `insikt update`
NEW="$("$VENV/bin/insikt" --version)"
if [ -n "$PRIOR" ] && [ "$PRIOR" != "$NEW" ]; then ok "updated $PRIOR → $NEW"
elif [ -n "$PRIOR" ]; then ok "reinstalled $NEW (already current)"
else ok "installed $NEW → $BIN_DIR/insikt"; fi

# --- 5. one-time check: what can Insikt see on this host? -----------------
say "checking what Insikt can see on this host…"
"$VENV/bin/insikt" scan --out "$INSIKT_HOME/overview.html" || say "nothing to read yet — set up Hermes, then re-run 'insikt scan'"

# --- 6. live dashboard service (keeps serving across reboots/logout) -------
PORT="${INSIKT_PORT:-8420}"
_ips() { hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || echo "localhost"; }
setup_serve() {
  command -v systemctl >/dev/null 2>&1 || return 1
  systemctl --user show-environment >/dev/null 2>&1 || return 1   # need a user systemd bus
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/insikt.service" <<UNIT
[Unit]
Description=Insikt read-only homelab dashboard
After=network-online.target

[Service]
Environment=PATH=/usr/local/bin:/usr/bin:/bin:%h/.local/bin:%h/.insikt/venv/bin
ExecStart=%h/.insikt/venv/bin/insikt serve --port ${PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload || return 1
  systemctl --user enable --now insikt.service >/dev/null 2>&1 || return 1
  loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || true   # survive logout (best effort)
  return 0
}
if [ -z "${INSIKT_NO_SERVE:-}" ]; then
  if setup_serve; then
    sleep 2
    ok "live dashboard running as a service (auto-starts on boot) — manage with: systemctl --user {status,restart,stop} insikt"
    for ip in $(_ips); do say "  → http://${ip}:${PORT}"; done
    say "  read-only. If a firewall is active, allow port ${PORT} on your overlay interface, e.g.:"
    say "    sudo ufw allow in on <zerotier-iface> to any port ${PORT} proto tcp"
  else
    say "no user-systemd here — start the dashboard yourself (and add it to your init):  insikt serve"
  fi
else
  say "dashboard service skipped (INSIKT_NO_SERVE set) — start it with:  insikt serve"
fi

# --- 7. register Insikt with a local agent's MCP (best effort) ------------
if command -v hermes >/dev/null 2>&1; then
  if hermes mcp add insikt --command "$VENV/bin/insikt mcp" >/dev/null 2>&1; then
    ok "registered Insikt with Hermes MCP (restart the Hermes gateway/session to load the tools)"
  else
    say "register Insikt with your agent yourself:  hermes mcp add insikt --command \"$BIN_DIR/insikt mcp\""
  fi
fi

echo
ok "done"
case ":$PATH:" in *":$BIN_DIR:"*) :;; *) say "add this to your shell profile:  export PATH=\"$BIN_DIR:\$PATH\"";; esac
cat <<EOF

  The dashboard is live at the URL above. Other commands:
    insikt configure   adapt to a non-standard layout (your agent can author it)
    insikt scan        write a one-off offline overview.html
    insikt mcp         read-only MCP server for your agent
    insikt --help

  Register with your agent (Hermes example):
    hermes mcp add insikt --command "$BIN_DIR/insikt mcp"
EOF
