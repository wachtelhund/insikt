# CLAUDE.md — Insikt

Architecture, patterns, and domain context for working in this repo. The product
spec lives in [SPEC.md](SPEC.md); read it first. [README.md](README.md) is the
short install/usage guide. This file is the map of the code that implements it.

## What this is

A **local-first, read-only auditor** for self-hosted AI agents (Hermes,
OpenClaw, …). It reads what each agent already persists on disk, normalizes it
into one graph + action timeline, tracks change over time, flags the dangerous
bits, and exposes all of it back to the agent as a **read-only MCP toolset** so
the agent can answer "what did I do?".

Read-only by default. Local-only by default. No secret *values* ever leave the
agent's own files — Insikt reads key *names*, not material.

## The one architectural split that matters

```
collectors/   framework-SPECIFIC  (the only place that knows ~/.hermes layout)
      │  emit
      ▼
model.py      normalized Graph (nodes + edges + Action stream)
      │
store.py      append-only SQLite snapshots + meta-audit
      │  (framework-AGNOSTIC from here down)
      ├── views.py        pure derivations (capability surface, timeline, cost, explain)
      ├── hygiene/        static risk scan + per-agent score
      ├── report/         self-contained overview.html
      └── mcp_server.py   read-only MCP tools
```

**New agent support = one new collector. Nothing downstream changes.** If you
find yourself special-casing a framework outside `collectors/`, that's a bug.

`views.py` is the **single source of truth** shared by the HTML report and the
MCP tools — what a human sees in the timeline is exactly what the agent gets from
`insikt_query_actions`. Don't compute view data anywhere else.

## Core model (`model.py`)

- One `Node` type with a `NodeType` discriminator + a `props` dict. One `Edge`
  type (`src, rel, dst`). One `Graph` container (union-merge, dedup).
- **Capability surface = the static graph** (what an agent *could* do).
  **Audit = `Action` nodes** (`type == ACTION`, carry a `ts`) — what it *did*.
  Keep these distinct; the risk lives in the gap.
- **IDs are deterministic** (`make_id`, `action_id` content-hash). Same real
  entity → same id across scans → diffs and idempotent backfill come for free.
  Never use random ids.
- Tools are scoped **per skill** (`tool:<kind>:<skill>`) so
  `Tool—can_access→Resource` attributes reach to the right skill. A shared web
  tool would conflate every skill's hosts (this was a real bug — keep it fixed).

## Collector rules (`collectors/`)

- **Read-only.** Never write to the agent's files.
- **Degrade gracefully.** A missing/unreadable path calls `graph.mark_partial(reason)`
  — it must never raise and abort the scan. The UI/MCP then say "incomplete"
  rather than silently lying.
- **Names, not values.** `.env` is parsed for key *names* only → `CredentialRef`
  nodes. There is a test (`test_hermes_no_secret_values_anywhere`) that fails if
  fake secret material ever appears in the graph. Keep it passing.
- Actions reconstructed from logs are tagged `source=backfill` (README §3.4);
  live capture (future) will be `source=live`.
- Each collector declares `supported_versions`; the fixtures under
  `tests/fixtures/` are the golden files for the format it expects.

## Hygiene (`hygiene/`)

Static, local, framework-agnostic (operates on the graph, not on paths).
`rules.py` = detectors; `engine.py` = orchestration + scoring + graph
annotation. Output is **always a per-agent score with enumerated factors —
never just a number**. The exfil triad (credential read + network + shell in one
skill) and the advisory-feed fingerprint match are the CRITICALs. The advisory
feed (`insikt/data/advisory_feed.json`) is a **sample, unsigned**; production
must use a signed/pinned feed (README §6, §8.2).

## MCP server (`mcp_server.py`)

Tool logic lives in module-level `*_impl(db_path, …)` functions (directly
testable); `build_server` wraps them as FastMCP tools. `mcp` is imported lazily
so `insikt scan` / the report work without the MCP SDK. Every tool logs to the
meta-audit (README §4.3). All tools are read-only.

## Report (`report/`)

`template.py` is a single offline HTML shell (inline CSS + vanilla-JS canvas
graph — **no CDN, no network**, Pi-friendly). Data is inlined as JSON.
`builder.py` assembles the payload from `views.py`. Skill bodies are stripped
from the graph payload (keep the file small; never embed secret-adjacent text).

## Conventions

- Python ≥ 3.10. Runtime deps: `pyyaml`, `mcp`. Keep deps minimal — this is a
  security tool; fewer deps = more auditable.
- Prefer the standard library. `store.py` is pure stdlib on purpose.
- Pure functions in `views.py`/`hygiene` take a `now` where time matters, so
  tests are deterministic.

## Running & testing

```sh
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -e . pytest
.venv/bin/python -m pytest                       # 67 tests, ~1s
.venv/bin/insikt scan --hermes-home tests/fixtures/hermes_home --out overview.html
.venv/bin/insikt mcp --db ~/.insikt/insikt.db    # read-only MCP server (stdio)
```

(Homebrew's Python 3.14 has a broken `pyexpat`; use 3.13 via `uv` as above.)

When you change collector output or views, re-run the scan against the fixtures
and eyeball `overview.html` — visual output beats raw data for catching
regressions (the per-skill-reach bug was caught this way, not by a unit test).

## Status / what's deferred

Built: v0 (Hermes collector → snapshot store → overview.html) **plus** the
read-only MCP server (v1 core) and the static hygiene engine (v2 core), plus a
lean OpenClaw collector to prove the cross-framework split. Deferred and kept
pluggable: live-capture hooks (§10.1), Honcho introspection, the live web-UI
server, signed/reproducible releases, and the Scanopy/Homelable overlay (v3+).
