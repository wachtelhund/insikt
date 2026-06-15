#!/bin/sh
# Insikt v0 installer (README §9.1).
#
#   curl -fsSL https://insikt.dev/install.sh | sh   # (once published)
#   ./install.sh                                    # from a local checkout
#
# This is the SAME doorway the agent-install skill (README §8) shells out to —
# one installer, two doorways (human via curl|sh, agent via the skill).
#
# CAVEAT, kept in view on purpose (README §9.1): `curl | sh` is the exact
# pipe-the-internet-into-your-shell pattern Insikt's own hygiene scanner flags.
# It is an acceptable v0 expedient while the audience is small and you control
# the endpoint, but it is a stepping stone, not the destination. The integrity
# model in README §8 (signed/pinned/reproducible releases, a verified Homebrew
# tap, signed .debs) is the graduation path that must land before Insikt asks
# anyone to trust it as a security tool. Even in v0: serve over HTTPS from a
# domain you control, publish checksums next to the release, and verify them
# before running anything.
#
# Deviation from the spec: the spec leans toward a single static Go binary. This
# implementation is Python (it matches Hermes's runtime and FastMCP), so v0
# installs into an isolated environment instead of dropping a prebuilt binary.
set -eu

INSIKT_HOME="${INSIKT_HOME:-$HOME/.insikt}"
BIN_DIR="${INSIKT_BIN_DIR:-$HOME/.local/bin}"
# Where to install from. Defaults to a local checkout if present, else a pinned
# remote ref (placeholder until published).
INSIKT_SOURCE="${INSIKT_SOURCE:-}"

say() { printf '\033[1;33m▸\033[0m %s\n' "$1"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# 1. Detect OS + arch (incl. arm64 / armhf for the Raspberry Pi — the primary target).
OS="$(uname -s)"; ARCH="$(uname -m)"
say "platform: ${OS} ${ARCH}"
case "$ARCH" in
  aarch64|arm64) say "arm64 detected (Raspberry Pi 64-bit / Apple Silicon)";;
  armv7l|armhf)  say "armhf detected (Raspberry Pi 32-bit)";;
esac

# 2. Require Python >= 3.10.
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 not found. Install Python >= 3.10 and re-run."
"$PY" - <<'PYEOF' || die "Python >= 3.10 required."
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
PYEOF
say "python: $($PY --version 2>&1)"

# 3. Decide the source.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -z "$INSIKT_SOURCE" ]; then
  if [ -f "$SCRIPT_DIR/pyproject.toml" ] && grep -q '^name = "insikt"' "$SCRIPT_DIR/pyproject.toml" 2>/dev/null; then
    INSIKT_SOURCE="$SCRIPT_DIR"
    say "installing from local checkout: $INSIKT_SOURCE"
  else
    INSIKT_SOURCE="git+https://github.com/sourceful/insikt.git"
    say "installing from $INSIKT_SOURCE"
    # NOTE: in a signed release, fetch the wheel + its published checksum here
    # and verify the checksum BEFORE installing (README §9.1).
  fi
fi

# 4. Install into an isolated environment (pipx if available, else a venv).
if command -v pipx >/dev/null 2>&1; then
  say "installing with pipx"
  pipx install --force "$INSIKT_SOURCE"
else
  say "installing into venv at $INSIKT_HOME/venv"
  mkdir -p "$INSIKT_HOME" "$BIN_DIR"
  "$PY" -m venv "$INSIKT_HOME/venv"
  "$INSIKT_HOME/venv/bin/pip" install --quiet --upgrade pip
  "$INSIKT_HOME/venv/bin/pip" install --quiet "$INSIKT_SOURCE"
  ln -sf "$INSIKT_HOME/venv/bin/insikt" "$BIN_DIR/insikt"
  case ":$PATH:" in *":$BIN_DIR:"*) :;; *) say "add $BIN_DIR to your PATH";; esac
fi

# 5. First run: scan and emit overview.html (README §9.1, §11 v0).
say "running first scan…"
if command -v insikt >/dev/null 2>&1; then INSIKT=insikt; else INSIKT="$INSIKT_HOME/venv/bin/insikt"; fi
"$INSIKT" scan || say "no agent state found yet — run 'insikt scan' once an agent is set up"

say "done. Next:"
echo "    insikt scan            # refresh the snapshot + overview.html"
echo "    insikt mcp             # run the read-only MCP server for your agent"
echo "    insikt --help"
