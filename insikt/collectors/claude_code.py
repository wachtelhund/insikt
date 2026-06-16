"""Claude Code collector — reads the real ``~/.claude`` layout (SPEC §3.3).

Profile-driven like the Hermes collector. Maps Claude Code's on-disk state:

* ``settings.json`` + ``settings.local.json`` -> agent, default model, permission
  posture (defaultMode, skip-prompt flags), the Bash/tool allow-list, enabled
  plugins.
* ``skills/**/SKILL.md``, ``commands/**/*.md``, ``agents/**/*.md`` -> ``Skill``
  nodes (kind = skill / command / subagent) with their declared tools + body.
* ``mcp-needs-auth-cache.json`` (+ enabled plugins) -> connected MCP servers
  (each a ``Resource``/tool source the agent can reach).
* ``.credentials.json`` -> ``CredentialRef`` names (never values).
* ``projects/**/*.jsonl`` sessions -> the ``Action`` stream (tool_use = shell /
  file writes / MCP calls; assistant usage = model calls + cost). Bounded to the
  most recent sessions so a huge history doesn't stall a scan.
* ``history.jsonl`` -> recent prompts.

Reads are defensive and bounded; a missing/oversized input degrades to a
``partial`` reason, never an exception.
"""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Optional

from ..model import ActionType, Graph, NodeType, Rel, ResourceKind, Source, ToolKind, action_id, make_id
from ..profiles import load_profile, scoped
from ..redact import redact_list, redact_secrets
from .base import Collector, CollectorResult
from .hermes import _parse_frontmatter, _resource_kind

FRAMEWORK = "claude-code"

# tool_use name -> normalized action type
_TOOL_ACTION = {
    "Bash": ActionType.SHELL.value,
    "Edit": ActionType.FILE_WRITE.value,
    "Write": ActionType.FILE_WRITE.value,
    "MultiEdit": ActionType.FILE_WRITE.value,
    "NotebookEdit": ActionType.FILE_WRITE.value,
    "WebFetch": "web",
    "WebSearch": "web",
    "Task": ActionType.SUBAGENT_RUN.value,
}
_SKILL_KIND = {"skills": "skill", "commands": "command", "agents": "subagent"}


def _load_json(path: Optional[Path]):
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _frontmatter_tools(fm: dict) -> list[str]:
    raw = fm.get("tools") or fm.get("allowed-tools") or fm.get("allowed_tools") or []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    return [str(t) for t in raw]


class ClaudeCodeCollector(Collector):
    framework = FRAMEWORK
    supported_versions = "live ~/.claude layout (2026)"

    def __init__(self, home: Optional[str | Path] = None, profile: Optional[dict] = None):
        self.profile = profile or load_profile(FRAMEWORK, home=str(home) if home else None)
        raw = home or self.profile.get("home") or os.environ.get("CLAUDE_HOME") or "~/.claude"
        self.home = Path(raw).expanduser()

    def _p(self, rel: str) -> Optional[Path]:
        return scoped(self.home, rel)

    def available(self) -> bool:
        return self.home.is_dir() and (
            (self.home / "settings.json").exists()
            or (self.home / "projects").is_dir()
            or (self.home / "commands").is_dir()
        )

    def collect(self) -> CollectorResult:
        g = Graph()
        settings = self._read_settings(g)
        agent_id = self._build_agent(g, settings)
        model_default = self._build_models(g, settings)
        self._build_credentials(g, settings)
        self._build_mcp(g, settings, agent_id)
        self._build_skills(g, agent_id)
        self._build_actions(g, agent_id, model_default)

        if len(g.nodes) <= 1:
            g.mark_partial("Claude Code home present but little readable state — run `insikt configure`")
        return CollectorResult(
            framework=FRAMEWORK, graph=g, available=self.available(),
            supported_versions=self.supported_versions,
            detected_version=settings.get("_version"),
        )

    # --- settings + agent -------------------------------------------------
    def _read_settings(self, g: Graph) -> dict:
        merged: dict = {}
        found = False
        for name in self.profile.get("settings_files", ["settings.json", "settings.local.json"]):
            data = _load_json(self._p(name))
            if isinstance(data, dict):
                found = True
                _deep_merge_settings(merged, data)
        if not found:
            g.mark_partial("settings.json not found")
        return merged

    def _build_agent(self, g: Graph, settings: dict) -> str:
        import platform as _platform

        perms = settings.get("permissions") or {}
        allow = perms.get("allow") or []
        return g.node(
            NodeType.AGENT, FRAMEWORK, self.profile.get("agent_id", "default"),
            label=f"claude-code/{self.profile.get('agent_id', 'default')}",
            framework=FRAMEWORK, profile=self.profile.get("agent_id", "default"),
            host=_platform.node() or None,
            permission_mode=perms.get("defaultMode"),
            skip_dangerous_prompt=settings.get("skipDangerousModePermissionPrompt"),
            skip_auto_prompt=settings.get("skipAutoPermissionPrompt"),
            allow_rules=len(allow),
            enabled_plugins=list((settings.get("enabledPlugins") or {}).keys()),
            # redact any secret-looking material in allow patterns before storing
            allow_sample=redact_list([str(a) for a in allow[:12]]),
            gateway_bind="terminal",
            auth_mode="local",
        )

    def _build_models(self, g: Graph, settings: dict) -> Optional[str]:
        name = settings.get("model")
        if not name:
            return None
        return g.node(
            NodeType.MODEL, "anthropic", name, label=f"anthropic/{name}",
            provider="anthropic", model_name=str(name), configured=True, is_default=True,
        )

    # --- credentials ------------------------------------------------------
    def _build_credentials(self, g: Graph, settings: dict) -> None:
        creds = _load_json(self._p(self.profile.get("credentials_file", ".credentials.json")))
        if isinstance(creds, dict):
            for name in creds.keys():
                g.node(NodeType.CREDENTIAL_REF, name, label=name, name=name,
                       scope=str(name).split(".")[0], storage="file")
        for name in (settings.get("env") or {}):
            g.node(NodeType.CREDENTIAL_REF, name, label=name, name=name,
                   scope=str(name).split("_")[0].lower(), storage="env")

    # --- mcp servers (the external reach) ---------------------------------
    def _build_mcp(self, g: Graph, settings: dict, agent_id: str) -> None:
        names: dict[str, dict] = {}
        for name in (_load_json(self._p(self.profile.get("mcp_auth_cache", ""))) or {}):
            names[name] = {"needs_auth": True}
        for name, spec in (settings.get("mcpServers") or {}).items():
            names[name] = {"command": (spec or {}).get("command")}
        if not names:
            return
        mcp_tool = g.node(NodeType.TOOL, ToolKind.MCP, FRAMEWORK, label="mcp", kind=ToolKind.MCP)
        for name, info in names.items():
            rid = g.node(NodeType.RESOURCE, ResourceKind.MCP_SERVER, name, label=name, kind=ResourceKind.MCP_SERVER,
                         value=name, needs_auth=info.get("needs_auth"),
                         command=redact_secrets(info.get("command")))
            g.add_edge(mcp_tool, Rel.CAN_ACCESS, rid)

    # --- skills (skills + commands + subagents) ---------------------------
    def _build_skills(self, g: Graph, agent_id: str) -> None:
        any_dir = False
        for glob in self.profile.get("skill_globs", []):
            top = glob.split("/", 1)[0]
            kind = _SKILL_KIND.get(top, "skill")
            if (self.home / top).is_dir():
                any_dir = True
            for path in sorted(self.home.glob(glob)):
                if scoped(self.home, str(path.relative_to(self.home))) is None:
                    continue
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                fm, body = _parse_frontmatter(raw.decode("utf-8", errors="replace"))
                name = str(fm.get("name") or path.stem)
                sid = g.node(
                    NodeType.SKILL, FRAMEWORK, f"{kind}:{name}", label=name, name=name,
                    description=fm.get("description"), source=kind, skill_kind=kind,
                    self_authored=(kind != "skill"),  # commands/subagents are user-authored
                    origin_hash=sha256(raw).hexdigest(), path=str(path),
                    body=body[:20000], body_excerpt=redact_secrets(body[:1000]),
                    declared_tools=_frontmatter_tools(fm), declared_network=[], declared_credentials=[],
                    model=fm.get("model"),
                )
                g.add_edge(agent_id, Rel.USES, sid)
                for tname in _frontmatter_tools(fm):
                    tid = g.node(NodeType.TOOL, tname.lower(), name, label=tname, kind=tname.lower())
                    g.add_edge(sid, Rel.REQUIRES, tid)
        if not any_dir:
            g.mark_partial("no skills/commands/agents directories found")

    # --- actions (bounded session parse) ----------------------------------
    def _build_actions(self, g: Graph, agent_id: str, model_default: Optional[str]) -> None:
        glob = self.profile.get("sessions_glob", "projects/**/*.jsonl")
        files = [p for p in self.home.glob(glob) if scoped(self.home, str(p.relative_to(self.home)))]
        try:
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            pass
        max_files = int(self.profile.get("max_session_files", 25))
        max_actions = int(self.profile.get("max_actions", 400))
        emitted = 0
        for path in files[:max_files]:
            if emitted >= max_actions:
                break
            emitted += self._ingest_session(g, path, agent_id, model_default, max_actions - emitted)
        if files[max_files:]:
            g.mark_partial(f"sessions truncated to most-recent {max_files} of {len(files)} files")

    def _ingest_session(self, g: Graph, path: Path, agent_id: str, model_default, budget: int) -> int:
        emitted = 0
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return 0
        for line in lines:
            if emitted >= budget:
                break
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            ts = rec.get("timestamp")
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            for block in content:
                if emitted >= budget:
                    break
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tname = block.get("name", "tool")
                atype = self._tool_type(tname)
                if atype is None:
                    continue
                summary = self._tool_summary(tname, block.get("input") or {})
                emitted += self._emit_action(g, agent_id, ts, atype, summary, tname)
            # assistant usage -> a model_call with tokens
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else None
            if usage and rec.get("type") == "assistant" and emitted < budget:
                tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
                if tokens:
                    mid = model_default
                    if msg.get("model"):
                        mid = g.node(NodeType.MODEL, "anthropic", msg["model"],
                                     label=f"anthropic/{msg['model']}", provider="anthropic",
                                     model_name=str(msg["model"]), used=True)
                    emitted += self._emit_action(g, agent_id, ts, ActionType.MODEL_CALL.value,
                                                 "assistant turn", None, model_id=mid, tokens=tokens)
        return emitted

    def _emit_action(self, g, agent_id, ts, atype, summary, tname, model_id=None, tokens=None) -> int:
        extra = f"{tname}|{tokens}"
        tail = action_id(FRAMEWORK, ts or "", atype, summary or atype, "", extra).split(":", 1)[1]
        props = {"type": atype, "agent_id": agent_id, "payload_summary": summary or atype,
                 "source": Source.BACKFILL.value}
        if atype not in {t.value for t in ActionType}:
            props["nonstandard_type"] = True
        if tname:
            props["tool"] = tname
        if model_id:
            props["model_id"] = model_id
        if tokens:
            props["tokens"] = tokens
        nid = g.node(NodeType.ACTION, tail, label=f"{atype}: {summary or atype}", ts=ts, **props)
        g.add_edge(nid, Rel.EXECUTED_BY, agent_id)
        if model_id:
            g.add_edge(agent_id, Rel.CALLED, model_id)
        return 1

    @staticmethod
    def _tool_type(tname: str) -> Optional[str]:
        if tname in _TOOL_ACTION:
            return _TOOL_ACTION[tname]
        if str(tname).startswith("mcp__"):
            return ActionType.MCP_CALL.value
        return None  # skip Read/Glob/Grep/etc — inventory noise, not audit-worthy

    @staticmethod
    def _tool_summary(tname: str, inp: dict) -> str:
        if tname == "Bash":
            return redact_secrets(str(inp.get("command", ""))[:120]) or "bash"
        for k in ("file_path", "path", "url", "pattern"):
            if inp.get(k):
                return f"{tname}: {str(inp[k])[:100]}"
        return tname


def _deep_merge_settings(base: dict, over: dict) -> None:
    for k, v in over.items():
        if k == "permissions" and isinstance(v, dict) and isinstance(base.get(k), dict):
            # union the allow/deny lists
            for sub in ("allow", "deny", "ask"):
                if isinstance(v.get(sub), list):
                    base[k][sub] = list(base[k].get(sub, [])) + v[sub]
            for kk, vv in v.items():
                if kk not in ("allow", "deny", "ask"):
                    base[k][kk] = vv
        else:
            base[k] = v
