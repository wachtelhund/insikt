# Insikt

A local-first, read-only auditor for self-hosted AI agents. It reads what an
agent (Hermes, Claude Code, OpenClaw, …) already writes to disk, normalizes it
into one graph plus an action timeline, flags the risky parts, and exposes the
result back to the agent as a read-only MCP toolset — so it can answer *"what did
I do yesterday?"* about itself.

Read-only and local by default. It reads credential key **names**, never their
values.

## Supported agents

| Agent | Reads | Status |
|---|---|---|
| **Hermes** (`~/.hermes`) | config, skills, connectors, cron, sessions/cost, memory, Honcho | ✅ validated against a live install |
| **Claude Code** (`~/.claude`) | settings + permission posture, commands/agents/skills, MCP servers, session tool-use + model usage | ✅ validated against a live install |
| **OpenClaw** (`~/.openclaw`) | config, connectors, skills, usage | ⚠️ best-effort — not yet validated against a real install |

Each collector is **profile-driven**: paths/field-names live in an editable
profile, so version/layout drift is fixed by `insikt configure` (below) — no code
change. A new framework needs one collector, or an agent-authored profile.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/wachtelhund/insikt/main/install.sh | sh
```

Detects your OS/arch (incl. Raspberry Pi arm64/armhf), installs into an isolated
environment, puts `insikt` on your `PATH`, and runs a first scan. Or clone and
run it directly:

```sh
git clone https://github.com/wachtelhund/insikt && cd insikt && ./install.sh
```

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
insikt configure       # adapt the collector to your setup (see below)
insikt diff            # what changed since the last scan
insikt snapshots       # snapshot history
insikt queries         # the meta-audit log (queries made to Insikt)
insikt --help
```

Open `overview.html` for the force-directed graph, capability surface, action
timeline, model-cost ledger, hygiene report, and diff — a single offline file.

## Configure (when your layout differs)

The built-in profiles fit a standard install. If yours differs, `insikt
configure` adapts it — AI-first:

```sh
insikt configure       # "Use your agent to find the optimal configuration? [Y/n]"
```

- **Yes** → Insikt drives your agent's own CLI (`hermes -z`, `claude -p`) to
  author a profile from a secret-redacted layout digest, validates it, and saves
  it on your confirmation. The agent knows its filesystem; Insikt validates and
  applies.
- **No / `--auto`** → a heuristic autodetect proposal instead.

Profiles are plain, editable YAML at `~/.insikt/profiles/<framework>.yaml`. A
connected agent can also do this over the read-only `insikt_describe_layout` MCP
tool plus `insikt configure --apply`.

## Connect it to your agent

```sh
hermes mcp add insikt --command "insikt mcp"
```

The agent gains read-only tools — `insikt_query_actions`,
`insikt_capability_surface`, `insikt_risk_report`, `insikt_diff`,
`insikt_explain`, `insikt_self_report`, and `insikt_describe_layout` — and
reaches for them when asked introspection questions. (Claude Code:
`claude mcp add insikt -- insikt mcp`.)

## Docs

- [`SPEC.md`](SPEC.md) — the full design spec: data model, collectors, MCP
  interface, hygiene scanning, architecture, and roadmap.
- [`CLAUDE.md`](CLAUDE.md) — code map and how to run the tests.

Built in Python. v0 is unsigned; the signed/reproducible-release integrity path
is in [`SPEC.md`](SPEC.md) §8–§9.
