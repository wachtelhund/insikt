# CLAUDE.md — Insikt

Architecture, patterns, and domain context for working in this repo. The product
spec lives in [SPEC.md](SPEC.md). [README.md](README.md) is the short install/use
guide. This file is the map of the code.

## What this is

A **local-first, read-only observability dashboard** for a self-hosted AI
homelab: a Raspberry Pi running **Hermes**, with optional **Honcho** and **Home
Assistant**. `insikt scan` writes a single offline `overview.html`; `insikt serve`
runs a live read-only web server (reachable over a ZeroTier/Tailscale overlay).
The same state is exposed back to the agent as a **read-only MCP toolset**.

Read-only and local by default. Insikt reports **counts, versions, health and
metrics** — never coordinates, entity/peer/workspace names, memory contents, or
secret values. Credential key *names* are read; key *material* never is.

## The architecture that matters

```
collectors/   each data source → ONE Section (system / honcho / homeassistant)
  base.py       Collector ABC + Section dataclass + status constants (OK/WARN/CRIT/OFF)
  system.py     Raspberry Pi host metrics (/proc, /sys, vcgencmd)         [always on]
  honcho.py     Honcho v3 API counts (optional)
  homeassistant.py  Home Assistant REST version/health/entity counts (optional)
  hermes.py     HermesGraphScanner → Graph;  build_hermes() → (Section, agent payload)
      │
      ▼
state.py      collect_state(profile) → {meta, status, sections{…}, agent}
      │        the SINGLE contract read by everything below
      ├── report/dashboard.py   self-contained offline HTML (render_dashboard)
      ├── server.py             live read-only web server + StateCache (SSE)
      └── mcp_server.py         read-only MCP tools
```

**A new data source = a new `Collector` subclass emitting a `Section`.** It must
not raise (use `safe_collect`/status), and it gathers counts/health only. If you
find a source leaking names/values/coordinates, that's a bug.

**`state.collect_state` is the single source of truth.** The dashboard, the live
server, and the MCP tools all read the same dict. Don't compute section data
anywhere else. `fast_only=True` collects just host metrics (the live ticker); a
full pass adds Hermes + the optional sources.

## Collector contract (`collectors/base.py`)

- A `Section` is JSON-serializable: `key, title, available, status, summary,
  data, partial, reasons`. Status ∈ `OK|WARN|CRIT|OFF`.
- `Collector.safe_collect()` NEVER raises — a dead/absent source becomes
  `status=off` or a `partial` reason, never an exception that aborts the scan.
- Optional collectors (`optional=True`, Honcho/HA) are dropped to `off` when not
  configured/reachable; `state._optional_section` honors `enabled: true|false|auto`.
- `interval` declares how often the live server should refresh this source
  (host = 3s fast loop; Hermes/Honcho/HA = slow loop).

## Hermes (`collectors/hermes.py`)

`HermesGraphScanner` reads `~/.hermes` into the normalized capability/action
`Graph` (`model.py`); `build_hermes(profile, now)` runs it + hygiene and returns
`(section_dict, agent_payload)`. The **agent payload** (`capability`, `timeline`,
`cost`, `hygiene`, `graph`) is produced by `views.py` and is what the dashboard's
Hermes sub-tabs and the `insikt_hermes` MCP tool render — compute it nowhere else.

- **Capability surface = the static graph** (what the agent *could* do).
  **Audit = `Action` nodes** (carry a `ts`) — what it *did*. Risk lives in the gap.
- **IDs are deterministic** (`make_id`, `action_id` content-hash) → idempotent
  diffs. Never random ids.
- Tools are scoped **per skill** (`tool:<kind>:<skill>`) so a skill's reachable
  hosts don't conflate across skills (this was a real bug — keep it fixed).
- **Names, not values.** `.env` → `CredentialRef` nodes by key name only. Raw
  skill `body` text is popped before the payload. The fixture's only secret
  literal is `FAKE-do-not-use`; `tests/test_hermes_build.py` fails if it ever
  reaches a Section or the payload. Keep that passing.

## Hygiene (`hygiene/`)

Static, local, framework-agnostic (operates on the graph). `rules.py` =
detectors; `engine.py` = orchestration + scoring + graph annotation. Output is
**always a per-agent score with enumerated factors — never just a number**, and
each `Finding` carries a `kind` (capability/config/alert) and a `remediation`.
The exfil triad (credential read + network + shell in one skill) and an
advisory-feed fingerprint match are the CRITICALs. `insikt/data/advisory_feed.json`
is a **sample, unsigned**; production needs a signed/pinned feed.

## Dashboard (`report/dashboard.py`)

One offline HTML shell: inline CSS + vanilla-JS canvas graph — **no CDN, no
network** (Pi-friendly). State is inlined as JSON; `render_dashboard(state, live)`
toggles the live SSE subscription. Colors come from a fixed brand palette in
`:root` (navy ramp `#080F25…#FFFFFF`, primary `#6C72FF` w/ a `#C95CFF→#6C72FF`
gradient, secondaries cyan `#57C3FF` / lavender `#9A91FB` / amber `#FDB52A`;
status ok=cyan, warn=amber, crit=rose). Any new color must come from this set.
Anything injected from state is escaped (`</` → `<\/`) so it can't break the
script tag.

## Live server (`server.py`)

Pure stdlib `ThreadingHTTPServer`. `StateCache` holds the latest state and
refreshes it with two daemon loops (fast host loop + slow full loop), reusing one
persistent `SystemCollector` so CPU% deltas are real. Strictly read-only: only
`GET` (`/`, `/api/state`, `/api/host`, `/healthz`, `/events` SSE) — POST/PUT/etc.
return `405`. Binds `0.0.0.0` by default for overlay reachability.

## MCP server (`mcp_server.py`)

Tool logic lives in module-level `*_impl(profile)` functions (directly testable);
`build_server` wraps them as FastMCP tools. `mcp` is imported lazily so `scan` /
`serve` work without the SDK. Tools: `insikt_system_state`, `insikt_host`,
`insikt_hermes(view)`, `insikt_source(name)`, `insikt_describe_layout`,
`insikt_self_report`. All read-only and live (no DB).

## Profile (`profiles.py`) & configure (`configure.py`)

One profile describes the whole homelab: `system` (thresholds), `hermes` (home +
layout overrides), `honcho`, `homeassistant`, `server`. `DEFAULT_PROFILE` fits the
standard stack so `scan`/`serve` work with zero config; a user/agent override goes
at `~/.insikt/profile.yaml` (deep per-section merge). `configure.py` is the
AI-first flow: `--describe` (redacted layout digest + schema), `--agent` (drive
`hermes -z` / `claude -p` to author it), `--apply FILE`, `--auto`, or a default
propose-and-save. It validates by actually running `collect_state`.

## Conventions

- Python ≥ 3.10. Runtime deps: `pyyaml`, `mcp` only — fewer deps = more auditable.
- Prefer the standard library. Pure functions in `views.py`/`hygiene` take a
  `now` where time matters, so tests are deterministic.
- Collectors gather **counts/versions/health/metrics**, never identifying data.

## Running & testing

```sh
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -e . pytest
.venv/bin/python -m pytest                                   # full suite, ~seconds
.venv/bin/insikt scan --hermes-home tests/fixtures/hermes_home --out overview.html
.venv/bin/insikt serve                                       # live dashboard on :8420
.venv/bin/insikt mcp                                         # read-only MCP (stdio)
```

(Homebrew's Python 3.14 has a broken `pyexpat`; use 3.13 via `uv` as above.)

When you change collector output or the dashboard, re-render against the fixtures
and **eyeball the HTML** — visual output beats raw data for catching regressions
(the per-skill-reach and gauge-threshold bugs were both caught this way).

## Status / what's deferred

Built: section collectors (system/honcho/HA + Hermes), `collect_state`, the
offline dashboard, the live read-only server, the static hygiene engine, the
read-only MCP server, and agent-assisted `insikt configure`. Deferred and kept
pluggable: live-capture hooks, signed/reproducible releases, a generic profile
interpreter for sources with no collector, and the Scanopy/Homelable network
overlay.
