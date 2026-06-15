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
    INSIKT_SOURCE="$SCRIPT_DIR"
  else
    INSIKT_SOURCE="git+https://github.com/wachtelhund/insikt.git"
    # In a signed release, fetch the wheel + its checksum here and verify BEFORE install (§9.1).
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
if command -v uv >/dev/null 2>&1; then
  say "using uv"
  if [ -n "$GOODPY" ]; then uv venv --python "$GOODPY" "$VENV" >/dev/null
  else uv venv --python 3.13 "$VENV" >/dev/null; fi   # uv fetches 3.13 if no system Python works
  uv pip install --python "$VENV/bin/python" --quiet "$INSIKT_SOURCE"
else
  [ -n "$GOODPY" ] || die "No working Python >=3.10 found and 'uv' is not installed.
Install uv (https://docs.astral.sh/uv/) or a working Python 3.11/3.12/3.13, then re-run."
  say "using $($GOODPY --version 2>&1)"
  "$GOODPY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet "$INSIKT_SOURCE"
fi
ln -sf "$VENV/bin/insikt" "$BIN_DIR/insikt"
printf '%s\n' "$INSIKT_SOURCE" > "$INSIKT_HOME/source"   # remembered by `insikt update`
NEW="$("$VENV/bin/insikt" --version)"
if [ -n "$PRIOR" ] && [ "$PRIOR" != "$NEW" ]; then ok "updated $PRIOR → $NEW"
elif [ -n "$PRIOR" ]; then ok "reinstalled $NEW (already current)"
else ok "installed $NEW → $BIN_DIR/insikt"; fi

# --- 5. first run ---------------------------------------------------------
say "running first scan…"
"$VENV/bin/insikt" scan || say "no agent state found yet — run 'insikt scan' once an agent (Hermes/OpenClaw) is set up"

echo
ok "done"
case ":$PATH:" in *":$BIN_DIR:"*) :;; *) say "add this to your shell profile:  export PATH=\"$BIN_DIR:\$PATH\"";; esac
cat <<EOF

  insikt scan        refresh the snapshot + overview.html
  insikt mcp         run the read-only MCP server for your agent
  insikt --help

  Register with your agent (Hermes example):
    hermes mcp add insikt --command "$BIN_DIR/insikt mcp"
EOF
