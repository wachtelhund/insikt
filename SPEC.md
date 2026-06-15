# Insikt — Specification

> Working codename **Insikt** (Swedish for *insight*; placeholder).
> A local-first, read-only tool that makes a self-hosted AI agent's **capabilities, actions, model usage, and risk surface** legible — and exposes that knowledge back to the agent itself as an MCP tool, so the agent can finally answer *"what did I do?"*

> This is the design spec. To install and use the implementation see
> [`README.md`](README.md); for the code map and tests see [`CLAUDE.md`](CLAUDE.md).

---

## 1. Problem & positioning

You run several services on a box (Hermes, Honcho, Home Assistant, ZeroTier, …). Two different things are "in your head":

1. **Infrastructure topology** — what runs where and how it connects.
2. **Agent behaviour** — what your AI agents *can do*, *have done*, *which models* they used, and *what they touched on the system*.

**(1) is already solved.** Scanopy, Homelable (incl. a Home Assistant HACS build + Zigbee2MQTT import), OpenNetworkDiagram, HomeLabInfo, NetVisor all auto-discover and draw a live network/service map. Insikt does **not** rebuild this.

**(2) is not solved, and the agents are designed in a way that makes it hard.** Hermes deliberately trades inspectability for self-improvement: its effective capability set is spread across SQLite indices, cached prompts, and skills it *wrote for itself* during past optimization (GEPA) runs — so "show me exactly what this agent can do" has no single source of truth. OpenClaw's ClawHub skill ecosystem has been the target of credential-stealing supply-chain campaigns. When an agent installs community skills, writes its own, runs shell commands, and is reachable from Telegram/WhatsApp, *"what can it touch and what did it actually do"* is closer to a safety control than a dashboard.

**Insikt's job:** ingest what each agent already persists on disk, normalize it into one graph + timeline, track how it changes over time, flag the dangerous bits, and expose all of it back to the agent as a read-only MCP toolset. Read-only by default. Local-only by default.

### 1.1 North-star scenario (the flow Insikt is designed around)

```
User:    "Hermes, what did you do yesterday?"
Hermes:  (no Insikt yet) "I don't keep a structured record of that. There's a
          read-only audit tool, Insikt, that can reconstruct it from my logs —
          signed by <publisher>, here's what it would access. Install it?"
User:    "Yes."
Hermes:  (runs the approved install; Insikt registers as an MCP server and
          backfills from my existing logs)
          "Done. Yesterday you had me: patch the OpenClaw API key, run 3 shell
          commands in ~/projects, send 2 Telegram messages, and I wrote myself
          a new skill 'pi-temp-watch' that has shell access — flagging that one."
```

Two consequences that drive the architecture: the agent must be able to **query** Insikt (→ §4, MCP interface), and "yesterday" must be answerable on the *first* install (→ §3.4, backfill).

### Non-goals (v1)
- Not a network/topology mapper → *overlay onto* Scanopy/Homelable instead.
- Not a runtime firewall or policy enforcer → that is the natural sequel (see §11); Insikt is the observability that justifies it.
- No cloud, no multi-tenant, no write-back to the agents. The agent-facing MCP surface is strictly read-only — an agent can query its own audit but never mutate it.

---

## 2. Core data model

Everything normalizes to a small set of nodes and edges. This powers the graph, the audit views, and the MCP query responses.

### Nodes
| Node | Description | Key fields |
|---|---|---|
| `Agent` | A running agent instance/profile | id, framework (`hermes`/`openclaw`), profile, version, host, gateway_bind, auth_mode |
| `Skill` | A capability bundle (md file, ClawHub pkg, self-authored) | id, name, source (`builtin`/`clawhub`/`hub`/`self`/`local`), origin_hash, created_at, last_modified, self_authored: bool |
| `Tool` | A primitive capability | id, kind (`shell`/`file`/`web`/`mcp`/`cron`/`messaging`) |
| `Model` | An LLM endpoint actually used | id, provider, model_name, endpoint |
| `Connector` | A messaging surface | id, platform (telegram/discord/slack/whatsapp/…), accepts_strangers: bool |
| `Resource` | Something the agent can reach | id, kind (`fs_path`/`host`/`mcp_server`/`api`), value |
| `CredentialRef` | A *reference* to a secret — never the value | id, name, scope, storage (`env`/`secretref`/`file`) |
| `Action` | One thing the agent did (the audit atom) | id, ts, agent_id, type (`shell`/`file_write`/`message_sent`/`skill_written`/`model_call`), payload_summary, model_id?, tokens?, cost?, source (`backfill`/`live`) |

### Edges
- `Agent —uses→ Skill`
- `Skill —requires→ Tool`
- `Tool —can_access→ Resource`
- `Skill —reads→ CredentialRef`
- `Agent —reachable_via→ Connector`
- `Agent —called→ Model`
- `Action —executed_by→ Agent` / `—via→ Skill` / `—touched→ Resource`

> **Capability surface = static graph** (what it *could* do). **Audit = the `Action` stream** (what it *did*). Keeping these distinct is the whole point — most of the risk lives in the gap between them.

---

## 3. Collectors (the ingestion layer)

The thing that keeps Insikt from being a fragile single-target wrapper: every framework gets a versioned **collector** that reads its on-disk state and emits the normalized model above. Collectors are read-only and degrade gracefully when a path/schema is missing. They are framework-specific by necessity; everything downstream (store, MCP interface, UI) is framework-agnostic — see §7.

### 3.1 Hermes collector
Reads from `HERMES_HOME` (default `~/.hermes`):
- `config.yaml` + `.env` → models, providers, connectors, gateway bind/auth. **Read key *names* from `.env`, never values** → emit `CredentialRef`s.
- `skills/*.md` → `Skill` nodes; hash each file (`origin_hash`); flag `self_authored` by source/metadata; static-scan contents (§6).
- `mcp/config.json`, `mcp/servers/`, `mcp/logs/` → connected MCP servers (each a `Resource`/tool source) and their call logs (a rich `Action` source).
- sessions + gateway logs → `Action` stream (commands run, files written, messages sent, approvals). ⚠ *Action fidelity depends on what Hermes logs structurally — see §10.*
- SQLite memory DB (FTS5) → memory/knowledge inventory (counts, topics; not full dump). ⚠ table layout to be confirmed against your version.
- Honcho → optional: pull the user/peer **representation summary** via Honcho's API (works for both managed cloud and self-hosted). Surface as a "what it believes about me" panel; read-only.
- Profiles (`-p`) → one `Agent` node per profile.

### 3.2 OpenClaw collector
Reads from `~/.openclaw`:
- `openclaw.json` → gateway port/bind, auth mode, tailscale exposure, model config.
- `credentials/<platform>/…` → `Connector` inventory (presence only; never secret material).
- installed skills (ClawHub + local) → `Skill` nodes with `source=clawhub`, capture pkg name/version for hygiene lookups.
- dashboard data / local DB (the same source feeding the `:18789` dashboard: sessions, API usage & cost, cron jobs) → `Model` usage, cost ledger, `Action` stream, scheduled-task inventory. ⚠ confirm whether to read the DB directly or call the dashboard's local API.

### 3.3 Future collectors
- **Claude Code** (`~/.claude`) — skills, sessions, MCP config.
- Generic **MCP server** introspection — enumerate tools each connected server exposes.

Each collector declares the framework version range it supports and emits a `partial: true` flag with reasons when something couldn't be read, so the UI and MCP responses can say "incomplete" rather than silently lie.

### 3.4 Backfill on install (makes the north-star flow land on day one)
Insikt is usually installed *at the moment* the user first asks "what did you do yesterday?" — so forward-only capture would answer "I can tell you from now on," which kills the magic. **The first action after install is a backfill pass:** the collector ingests the agent's already-retained history (Hermes conversation history, sessions, `mcp/logs/`; OpenClaw sessions + usage DB) and reconstructs the recent `Action` stream, tagged `source=backfill`. Live capture (§10.1) takes over from then on, tagged `source=live`. The reconstruction ceiling is whatever the agent actually logged — surface that honestly (e.g. "reconstructed from logs; may be incomplete before <date>").

---

## 4. The MCP query interface (the agent-facing contract)

This is the mechanism that makes the north-star flow work. Insikt runs as a **local MCP server**. Both target agents register MCP servers and merge their tools into the same registry as native tools, so once Insikt is connected the agent simply *has* these tools and picks them when the user asks an introspection question. No bespoke per-framework integration — MCP is the universal surface, which is also how Insikt stays cross-framework (one server serves Hermes, OpenClaw, Claude Code, Cursor, …).

### 4.1 Exposed tools (all read-only)
| Tool | Input | Returns |
|---|---|---|
| `insikt_query_actions` | `agent?`, `window` (e.g. `yesterday`, ISO range), `type?` | Structured, summarized action list for the window. The answer to "what did you do?" |
| `insikt_capability_surface` | `agent?` | Skills/tools/connectors and what each can reach. The "what can I do" answer. |
| `insikt_risk_report` | `agent?` | Hygiene findings + per-agent risk score with contributing factors (§6). |
| `insikt_diff` | `since` (timestamp/snapshot) | What changed: new skills, new credential reads, new connectors, new reachable hosts. |
| `insikt_explain` | `node_id` (skill/action) | Detail on one node: origin, hash, tools, resources, credential reads. |
| `insikt_self_report` | — | Insikt's own version, signature/provenance, and exact permissions. Lets the agent prove the tool to the user before/after install. |

Tools return **structured data, not prose** — the agent phrases the natural-language reply. Keep summaries token-light (the agent pays for the context).

### 4.2 Registration
- **Hermes:** `hermes mcp add insikt --command <…>` (or it auto-discovers on restart); tools appear in the registry immediately, and `notifications/tools/list_changed` keeps them in sync.
- **OpenClaw:** register Insikt as an MCP tool provider via its config/skill.
- The packaging skill (§8) does this wiring as part of install so the user never touches config.

### 4.3 Meta-audit
Insikt logs every query made *to* it — including the agent's own — into the append-only store. This gives tamper-evidence and a tidy recursion: you can see "the agent asked itself what it did at 09:00," and because Insikt is itself an MCP server, its calls also show up in the agent's own MCP logs.

---

## 5. Views (human-facing)

1. **Graph** — force-directed node/edge view (the Obsidian feel). Filter by node type; color by risk; click a `Skill` to see its tools, resources, credential reads, and origin. Agents are roots.
2. **Capability surface** — flat, sortable inventory: every skill/tool/connector and what it can reach. The "if a compliance team asked, here's the answer" view.
3. **Action timeline** — chronological audit of what each agent did; filter by type/agent/skill; highlight `skill_written` events (capability drift) and `source=backfill` vs `live`.
4. **Model + cost ledger** — models used, token volume, spend, per agent and combined. (Context: third-party harnesses were moved off Claude subscription quotas to API billing — cost visibility matters.)
5. **Hygiene** — the risk panel (§6).
6. **Diff** — "what changed since last snapshot." Highest-signal view for a self-modifying agent.

---

## 6. Hygiene / risk scanning

Timely because of the ClawHub supply-chain campaigns. All static, all local.

- **Skill fingerprinting** — hash installed skills; compare against known-bad hashes / community advisory feeds (pluggable, signed feed); flag matches.
- **Static content scan** of every skill for risky patterns: shell exec, network egress to non-allowlisted hosts, credential/`.env` reads, base64/obfuscated blobs, auto-update hooks.
- **Capability blast radius** — per skill: does it combine *credential read* + *network egress* + *shell*? (the exfil triad) → escalate.
- **Exposure checks** — gateway bound to `0.0.0.0` without auth; connectors that accept messages from strangers; agent reachable outside the ZeroTier/Tailscale overlay.
- **Drift alerts** — a self-authored skill that newly gained shell or network access since the last snapshot.

Output: a per-agent risk score with the contributing factors enumerated (never just a number). Same engine backs `insikt_risk_report` and the self-scan in §8.

---

## 7. Architecture

```
┌─────────────┐  read-only   ┌───────────────┐
│ Hermes FS   │◄────────────│               │
│ OpenClaw FS │◄────────────│  Collectors   │──► normalized model
│ Honcho API  │◄────────────│  (versioned,  │
└─────────────┘              │  per-frmwk)   │
                             └──────┬────────┘
                                    │
                          ┌─────────▼──────────┐
                          │  Normalized store   │  SQLite, append-only
                          │  (snapshots + meta- │  snapshots over time
                          │   audit log)        │
                          └─────────┬──────────┘
                                    │  (framework-agnostic from here down)
          ┌──────────────┬──────────┼───────────────┬────────────────┐
          ▼              ▼          ▼                ▼                ▼
   MCP server      Local web UI  Static HTML   Export adapter   Self-report
   (agent-facing,  graph+timeline report (v0)  → Scanopy/        (provenance)
    read-only)     (v1)                         Homelable (v3)
```

- **Split that matters:** collectors are framework-specific; the store, MCP interface, UI, and exports are framework-agnostic. New agent support = one new collector, nothing else changes.
- **Snapshots are append-only.** Each scan writes a timestamped snapshot; diffs come for free; you get an immutable-ish history of how the agent evolved.
- **Two bind targets, both loopback by default:** the MCP server (for the local agent) and the optional web UI. An audit tool that's itself an exposed service would be self-defeating.
- **No secret values ever leave the agent's own files** — Insikt reads names/scopes, not material.

---

## 8. Distribution & integrity model

The whole point of "ask your agent to install it" is real and easy on both targets — and it is *also the exact supply-chain pattern Insikt exists to police.* That tension is not a footnote; it dictates the design. The tool must be the single most trustworthy thing in the skill ecosystem, and must visibly prove it.

### 8.1 Packaging
- **Hermes:** publish to the public Skills Hub (`hermes skills install <id>`, also installable by direct `SKILL.md` URL; compatible with the agentskills.io open standard). The skill installs the Insikt binary and runs `hermes mcp add` to register the server.
- **OpenClaw:** publish as a ClawHub package (npm-backed) that does the equivalent install + MCP registration.
- Either way the agent already knows the gesture (`skills search` → `skills inspect` → `skills install`); Insikt rides the native mechanism rather than inventing one.

### 8.2 Integrity as the product's signature feature
- **Signed, pinned, reproducible.** Signed releases; the skill manifest pins the binary hash; reproducible builds with published provenance (SLSA-style).
- **Verifiable publisher**, single canonical name. Get into the **curated** catalogs (e.g. the Nous-reviewed MCP catalog) — reviewed placement beats raw download count for trust.
- **Self-proving.** On install, Insikt runs its own hygiene engine against itself and prints its exact permissions + signature; `insikt_self_report` lets the agent surface that to the user on demand. "The one skill that proves its own trustworthiness."
- **Minimal scopes, read-only.** It reads config/logs/skill files and names of credentials; it never reads secret values and never writes to the agent.

### 8.3 Install is a confirmed action, never silent
Both frameworks pause for human approval on side-effectful tool calls (Hermes `/approve`/`/deny`; gateway approval prompts). Route the install through that: the agent presents what Insikt is, who signed it, and what it will access, and waits for a yes. This keeps the magic moment while *not* normalizing the blind-install behaviour Insikt is meant to flag.

### 8.4 Impersonation
Once "the popular audit tool" is a name agents say aloud, lookalikes (`insikt-pro`, typosquats) will appear. Mitigate with: canonical publisher identity, signature verification the agent performs *before* install, `skills inspect` (preview-without-install) showing provenance, and registry-side namespace protection. Treat the name as a trust anchor and defend it.

---

## 9. Tech choices (suggested, not load-bearing)

- **Backend / collectors:** Go (single static binary, trivial to `scp` to the Pi, easy to sign/reproduce) or Python (matches Hermes's runtime; FastMCP makes the MCP server trivial). Go favours the "downloadable single binary"; Python favours reusing Hermes internals.
- **MCP server:** FastMCP (Python) or the Go MCP SDK. Read-only tools only.
- **Store:** SQLite (snapshots + normalized nodes/edges + meta-audit).
- **Frontend:** small web app; graph via **Cytoscape.js** or **Sigma.js** (handles larger graphs better than raw D3-force); timeline as a virtualized list.
- **v0 shortcut:** skip the server entirely — the CLI emits a single self-contained `overview.html`. Matches "a downloadable tool that creates a good overview" and is a one-evening build.

### 9.1 Install (v0: `curl | sh`)

For v0, distribution is a single one-line installer — the fastest path to getting it into people's hands:

```
curl -fsSL https://insikt.dev/install.sh | sh
```

What the script does: detect OS + arch (**including arm64/armhf for the Raspberry Pi**, your primary target), fetch the matching prebuilt binary from GitHub Releases, place it on `PATH`, and run `insikt scan` once to emit `overview.html`. With a static Go binary there are no runtime dependencies to drag along. This same installer is what the agent-install skill (§8) shells out to under the hood — **one installer, two doorways** (human via `curl|sh`, agent via the skill).

> **Caveat, kept in view on purpose:** `curl | sh` is the exact pipe-the-internet-into-your-shell pattern Insikt's own hygiene scanner flags. It's an acceptable v0 expedient while the audience is small and you control the endpoint — but it is explicitly a stepping stone, not the destination. The integrity model in §8 (signed/pinned/reproducible releases, a verified Homebrew tap, signed `.deb`s) is the graduation path that must land **before** Insikt asks anyone to trust it as a security tool. Even in v0: serve the script over HTTPS from a domain you control, publish the binary checksums next to the release, and have the installer verify the checksum before it runs anything.

---

## 10. The genuinely hard parts (don't hand-wave these)

1. **Action-audit fidelity.** Capability surface is easy (it's on disk). The *action* stream is the hard part — agents may not emit clean structured "I ran X" events. Options, increasing fidelity: (a) parse logs/sessions/`mcp/logs` best-effort (also powers backfill, §3.4); (b) tail the gateway's structured logs live; (c) a thin **execution hook/wrapper** around the shell/file tools that records a structured event before forwarding. (c) is the only way to get trustworthy live audit and is the bridge toward the firewall sequel. Ship (a) first; design the `Action` schema so (b)/(c) drop in later.
2. **Backfill ceiling.** "Yesterday" is only as good as what the agent retained; older history may be rotated away. Label reconstructed actions and the cutoff date; never imply completeness you can't back.
3. **Schema/version drift.** Both projects move weekly. Mitigate: versioned collectors, golden-file fixtures per supported version, `partial` degradation, CI running collectors against captured sample `~/.hermes` / `~/.openclaw` trees.
4. **Static vs. effective capability.** A skill may *declare* less than it does. Treat the static scan as a lower bound; lean on action audit + diff to catch the rest.
5. **Honcho introspection.** Pull the representation via API read-only; don't reverse the SQLite/pgvector store. Optional, so a missing/cloud Honcho doesn't break a scan.
6. **Not becoming attack surface.** Loopback-only, read-only MCP, no write-back in v1, and the hygiene/advisory feed must be signed/pinned — or you reintroduce the supply-chain risk you're auditing for.

---

## 11. Milestones

- **v0 — Inventory + static report.** Hermes collector only. Capability surface + skills + models + credential refs → self-contained `overview.html`, shipped via `curl|sh` (§9.1). *Proves the data is reachable.*
- **v1 — MCP server + backfill + OpenClaw collector.** The north-star flow end-to-end: agent installs Insikt, it backfills from logs, and `insikt_query_actions` answers "what did you do yesterday?" Plus the live web UI (graph + timeline + cost ledger), snapshot store, and **diff view**. *This is the version that delivers the demo.*
- **v2 — Hygiene + integrity hardening.** Skill fingerprinting, static risk scan, exposure checks, drift alerts, signed advisory feed; signed/reproducible releases, self-scan-on-install, publish to both skill hubs.
- **v3 — Cross-agent + overlay.** Claude Code collector; export agent nodes as an overlay layer into Scanopy/Homelable so the agent graph sits on top of the network map.
- **v4 (sequel, optional) — Enforcement.** Promote the execution hook from §10.1 from *recorder* to *gate*: scoped, time-boxed, confirm-required capabilities. This is where Insikt becomes the capability firewall — build it only once the read-only audit has proven what needs gating.

---

## 12. Why this is worth building

- The topology half is saturated; this half is **empty and getting more urgent** as agents self-modify and the skill marketplaces get attacked.
- It's **read-only**, low-risk to build and run, and useful from v0.
- **No single upstream owns the cross-framework agent-introspection layer**, and the MCP interface means one server serves every MCP-speaking agent — so unlike a setup wrapper, it isn't obsoleted by the next Hermes/OpenClaw release; collectors absorb their changes.
- The agent-installs-it loop gives it a **distribution mechanism most tools don't have** — the agent recommends and installs it on demand — *provided* the integrity model in §8 earns that trust.
- It's a clean on-ramp to the one genuinely open, defensible thing in this space (the capability firewall) without committing to it up front.
