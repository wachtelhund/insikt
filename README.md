# Insikt

A local-first, read-only auditor for self-hosted AI agents. It reads what an
agent (Hermes, OpenClaw, …) already writes to disk, normalizes it into one graph
plus an action timeline, flags the risky parts, and exposes the result back to
the agent as a read-only MCP toolset — so it can answer *"what did I do
yesterday?"* about itself.

Read-only and local by default. It reads credential key **names**, never their
values.

## Install

```sh
curl -fsSL https://insikt.dev/install.sh | sh
```

Detects your OS/arch (incl. Raspberry Pi arm64/armhf), installs into an isolated
environment, puts `insikt` on your `PATH`, and runs a first scan. From a clone
(until the hosted script is published): `./install.sh`.

## Update

```sh
insikt update          # re-installs the latest from the recorded source
```

Or just re-run the install command — it's idempotent and rebuilds the
environment from the latest release. (Once releases are signed and packaged, the
norm becomes the OS package manager: `brew upgrade insikt` / `apt upgrade` with
pinned versions — see [`SPEC.md`](SPEC.md) §8.)

## Use

```sh
insikt scan            # snapshot the agent(s) and write overview.html
insikt mcp             # read-only MCP server (stdio) for your agent
insikt diff            # what changed since the last scan
insikt snapshots       # snapshot history
insikt queries         # the meta-audit log (queries made to Insikt)
insikt --help
```

Open `overview.html` for the force-directed graph, capability surface, action
timeline, model-cost ledger, hygiene report, and diff — a single offline file.

## Connect it to your agent

```sh
hermes mcp add insikt --command "insikt mcp"
```

The agent gains six read-only tools — `insikt_query_actions`,
`insikt_capability_surface`, `insikt_risk_report`, `insikt_diff`,
`insikt_explain`, `insikt_self_report` — and reaches for them when asked
introspection questions.

## Docs

- [`SPEC.md`](SPEC.md) — the full design spec: data model, collectors, MCP
  interface, hygiene scanning, architecture, and roadmap.
- [`CLAUDE.md`](CLAUDE.md) — code map and how to run the tests.

Built in Python. v0 is unsigned; the signed/reproducible-release integrity path
is in [`SPEC.md`](SPEC.md) §8–§9.
