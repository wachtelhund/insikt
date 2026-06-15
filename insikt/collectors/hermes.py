"""Hermes collector (README §3.1).

Reads ``HERMES_HOME`` (default ``~/.hermes``) read-only and normalizes it:

* ``config.yaml`` + ``.env``  -> agents/profiles, models, connectors, gateway
  bind/auth, and ``CredentialRef`` nodes (key **names** only — never values).
* ``skills/*.md``            -> ``Skill`` nodes (hashed; ``self_authored`` flagged;
  body retained for the static hygiene scan), their required tools, reachable
  hosts, and credential reads.
* ``mcp/config.json`` + ``mcp/logs/*.jsonl`` -> connected MCP servers (a tool
  source) and their call logs (an ``Action`` source).
* ``sessions/*.jsonl``       -> the reconstructed ``Action`` stream (shell, file
  writes, messages, self-authored skills, model calls). Tagged
  ``source=backfill`` — this is the day-one backfill (README §3.4).
* ``memory/memory.db``       -> a memory/knowledge inventory (counts only).

Every read is defensive: a missing or malformed input adds a ``partial`` reason
to the graph instead of raising.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

import yaml

from ..model import (
    ActionType,
    Graph,
    NodeType,
    Rel,
    Source,
    action_id,
    make_id,
)
from ..redact import redact_list, redact_secrets
from .base import Collector, CollectorResult

FRAMEWORK = "hermes"
_VALID_ACTION_TYPES = {t.value for t in ActionType}


def _credential_scope(name: str) -> str:
    base = name.lower()
    for suffix in ("_api_key", "_token", "_secret", "_key", "_password", "_pat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base.split("_")[0] if base else "general"


def _resource_kind(value: str) -> str:
    v = value.strip()
    if v.startswith(("http://", "https://")):
        return "api"
    if v.startswith(("/", "~", "./", "../")):
        return "fs_path"
    if "/" not in v and ("." in v or ":" in v):
        return "host"
    return "fs_path"


def _iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")


def _as_iso(value) -> Optional[str]:
    """Coerce a YAML-parsed timestamp (datetime/date) or string to an ISO string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split ``--- yaml --- body`` markdown. Returns (frontmatter, body)."""
    if text.startswith("---"):
        parts = text.split("\n")
        # find closing fence
        for i in range(1, len(parts)):
            if parts[i].strip() == "---":
                fm_text = "\n".join(parts[1:i])
                body = "\n".join(parts[i + 1 :])
                try:
                    fm = yaml.safe_load(fm_text) or {}
                    if not isinstance(fm, dict):
                        fm = {}
                except yaml.YAMLError:
                    fm = {}
                return fm, body
    return {}, text


def _read_jsonl(path: Path) -> tuple[list[dict], int]:
    """Read a .jsonl file, skipping malformed lines. Returns (records, skipped)."""
    records: list[dict] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
            else:
                skipped += 1
        except json.JSONDecodeError:
            skipped += 1
    return records, skipped


class HermesCollector(Collector):
    framework = FRAMEWORK
    supported_versions = ">=0.9,<1.0"

    def __init__(self, home: Optional[str | Path] = None):
        raw = home or os.environ.get("HERMES_HOME") or "~/.hermes"
        self.home = Path(raw).expanduser()

    # --- contract ---------------------------------------------------------
    def available(self) -> bool:
        return self.home.is_dir() and (
            (self.home / "config.yaml").exists()
            or (self.home / "skills").is_dir()
            or (self.home / "sessions").is_dir()
        )

    def collect(self) -> CollectorResult:
        g = Graph()
        config = self._read_config(g)
        detected_version = str(config.get("version")) if config.get("version") else None
        host = config.get("host")

        agents = self._build_agents(g, config, host)
        self._build_models(g, config)
        self._build_connectors(g, config, agents)
        cred_names = self._read_env_names(g)
        self._build_credentials(g, cred_names)
        self._build_skills(g, agents, cred_names)
        self._build_mcp(g, agents)
        self._build_actions(g, agents, host)
        self._build_memory(g, agents)

        if not g.nodes:
            g.mark_partial("Hermes home present but no readable state found")

        return CollectorResult(
            framework=FRAMEWORK,
            graph=g,
            available=self.available(),
            supported_versions=self.supported_versions,
            detected_version=detected_version,
        )

    # --- readers ----------------------------------------------------------
    def _read_config(self, g: Graph) -> dict:
        path = self.home / "config.yaml"
        if not path.exists():
            g.mark_partial("config.yaml not found")
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError) as exc:
            g.mark_partial(f"config.yaml unreadable: {exc}")
            return {}

    def _read_env_names(self, g: Graph) -> list[str]:
        """Read .env key **names** only. Values are never read into memory."""
        path = self.home / ".env"
        if not path.exists():
            return []
        names: list[str] = []
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key = line.split("=", 1)[0].strip()
                if key.startswith("export "):
                    key = key[len("export "):].strip()
                if key:
                    names.append(key)
        except OSError as exc:
            g.mark_partial(f".env unreadable: {exc}")
        return names

    def _build_agents(self, g: Graph, config: dict, host: Optional[str]) -> list[str]:
        gateway = config.get("gateway") or {}
        bind = gateway.get("bind")
        auth = gateway.get("auth", "unknown")
        version = config.get("version")
        profiles = config.get("profiles") or ["default"]
        if isinstance(profiles, str):
            profiles = [profiles]

        agent_ids = []
        for profile in profiles:
            aid = g.node(
                NodeType.AGENT,
                FRAMEWORK,
                profile,
                label=f"hermes/{profile}",
                framework=FRAMEWORK,
                profile=profile,
                version=version,
                host=host,
                gateway_bind=bind,
                auth_mode=auth,
            )
            agent_ids.append(aid)
        return agent_ids

    def _build_models(self, g: Graph, config: dict) -> None:
        for m in config.get("models") or []:
            if not isinstance(m, dict):
                continue
            provider = m.get("provider", "unknown")
            name = m.get("name") or m.get("model") or "unknown"
            g.node(
                NodeType.MODEL,
                provider,
                name,
                label=f"{provider}/{name}",
                provider=provider,
                model_name=name,
                endpoint=m.get("endpoint"),
                configured=True,
            )
            # Note: the Agent--called-->Model edge is added from the *action*
            # stream (a model is "called" only when it was actually used).

    def _build_connectors(self, g: Graph, config: dict, agents: list[str]) -> None:
        for c in config.get("connectors") or []:
            if not isinstance(c, dict):
                continue
            platform = c.get("platform", "unknown")
            cid = g.node(
                NodeType.CONNECTOR,
                platform,
                label=platform,
                platform=platform,
                accepts_strangers=bool(c.get("accepts_strangers", False)),
            )
            for aid in agents:
                g.add_edge(aid, Rel.REACHABLE_VIA, cid)

    def _build_credentials(self, g: Graph, names: list[str]) -> None:
        for name in names:
            g.node(
                NodeType.CREDENTIAL_REF,
                name,
                label=name,
                name=name,
                scope=_credential_scope(name),
                storage="env",
            )

    def _build_skills(self, g: Graph, agents: list[str], cred_names: list[str]) -> None:
        skills_dir = self.home / "skills"
        if not skills_dir.is_dir():
            g.mark_partial("skills/ directory not found")
            return
        cred_set = set(cred_names)
        for path in sorted(skills_dir.glob("*.md")):
            try:
                raw = path.read_bytes()
            except OSError as exc:
                g.mark_partial(f"skill {path.name} unreadable: {exc}")
                continue
            text = raw.decode("utf-8", errors="replace")
            fm, body = _parse_frontmatter(text)
            name = str(fm.get("name") or path.stem)
            source = str(fm.get("source") or "local")
            self_authored = bool(fm.get("self_authored", source == "self"))
            origin_hash = sha256(raw).hexdigest()
            # PyYAML coerces ISO timestamps to datetime objects; normalize to
            # strings so the graph stays JSON-serializable.
            created_at = _as_iso(fm.get("created_at"))
            last_modified = _as_iso(fm.get("last_modified")) or _iso_mtime(path)

            declared_tools = [str(t) for t in (fm.get("tools") or [])]
            declared_network = [str(h) for h in (fm.get("network") or [])]
            declared_creds = [str(c) for c in (fm.get("requires_credentials") or [])]

            sid = g.node(
                NodeType.SKILL,
                FRAMEWORK,
                name,
                label=name,
                name=name,
                source=source,
                origin_hash=origin_hash,
                created_at=created_at,
                last_modified=last_modified,
                self_authored=self_authored,
                path=str(path),
                body=body[:20000],
                body_excerpt=redact_secrets(body[:1000]),
                declared_tools=declared_tools,
                declared_network=declared_network,
                declared_credentials=declared_creds,
            )
            for aid in agents:
                g.add_edge(aid, Rel.USES, sid)

            # Required tools (declared lower bound; the static scan in hygiene/
            # catches undeclared capability). Tools are scoped per skill so that
            # Tool--can_access-->Resource attributes reach to the right skill
            # (a shared web tool would conflate every skill's hosts).
            web_tool = None
            for kind in declared_tools:
                if kind == "web":
                    web_tool = web_tool or g.node(NodeType.TOOL, "web", name, label="web", kind="web")
                    g.add_edge(sid, Rel.REQUIRES, web_tool)
                else:
                    tid = g.node(NodeType.TOOL, kind, name, label=kind, kind=kind)
                    g.add_edge(sid, Rel.REQUIRES, tid)

            # Reachable hosts -> this skill's web tool can_access each host
            # (host Resource nodes are shared, so the graph shows which skills
            # reach a common host).
            if declared_network:
                if web_tool is None:
                    web_tool = g.node(NodeType.TOOL, "web", name, label="web", kind="web")
                    g.add_edge(sid, Rel.REQUIRES, web_tool)
                for host in declared_network:
                    rid = g.node(
                        NodeType.RESOURCE,
                        "host",
                        host,
                        label=host,
                        kind="host",
                        value=host,
                    )
                    g.add_edge(web_tool, Rel.CAN_ACCESS, rid)

            # Credential reads (declared); only link to creds we actually saw.
            for cname in declared_creds:
                cid = g.node(
                    NodeType.CREDENTIAL_REF,
                    cname,
                    label=cname,
                    name=cname,
                    scope=_credential_scope(cname),
                    storage="env" if cname in cred_set else "secretref",
                )
                g.add_edge(sid, Rel.READS, cid)

    def _build_mcp(self, g: Graph, agents: list[str]) -> None:
        cfg_path = self.home / "mcp" / "config.json"
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                g.mark_partial(f"mcp/config.json unreadable: {exc}")
                data = {}
            servers = (data or {}).get("servers") or {}
            mcp_tool = None
            for name, spec in servers.items():
                rid = g.node(
                    NodeType.RESOURCE,
                    "mcp_server",
                    name,
                    label=name,
                    kind="mcp_server",
                    value=name,
                    command=redact_secrets((spec or {}).get("command")),
                    args=redact_list((spec or {}).get("args")),
                )
                if mcp_tool is None:
                    mcp_tool = g.node(NodeType.TOOL, "mcp", label="mcp", kind="mcp")
                g.add_edge(mcp_tool, Rel.CAN_ACCESS, rid)
        else:
            g.mark_partial("mcp/config.json not found")

    def _build_actions(self, g: Graph, agents: list[str], host: Optional[str]) -> None:
        agent_by_profile = {}
        for aid in agents:
            node = g.get(aid)
            if node:
                agent_by_profile[node.props.get("profile", "default")] = aid
        default_agent = agents[0] if agents else g.node(NodeType.AGENT, FRAMEWORK, "default", label="hermes/default", framework=FRAMEWORK, profile="default")
        if not agents:
            agent_by_profile["default"] = default_agent

        def resolve_agent(profile: Optional[str]) -> str:
            if profile and profile in agent_by_profile:
                return agent_by_profile[profile]
            if profile:
                # An action references a profile not in config — create it.
                return g.node(
                    NodeType.AGENT, FRAMEWORK, profile, label=f"hermes/{profile}",
                    framework=FRAMEWORK, profile=profile, host=host,
                )
            return default_agent

        self._ingest_sessions(g, resolve_agent)
        self._ingest_mcp_logs(g, resolve_agent)

    def _ingest_sessions(self, g: Graph, resolve_agent) -> None:
        sessions_dir = self.home / "sessions"
        if not sessions_dir.is_dir():
            g.mark_partial("sessions/ directory not found")
            return
        for path in sorted(sessions_dir.glob("*.jsonl")):
            records, skipped = _read_jsonl(path)
            if skipped:
                g.mark_partial(f"{skipped} malformed line(s) in sessions/{path.name}")
            for rec in records:
                self._ingest_action(g, rec, resolve_agent, default_type=None)

    def _ingest_mcp_logs(self, g: Graph, resolve_agent) -> None:
        logs_dir = self.home / "mcp" / "logs"
        if not logs_dir.is_dir():
            return  # optional source; absence is not "partial"
        for path in sorted(logs_dir.glob("*.jsonl")):
            records, skipped = _read_jsonl(path)
            if skipped:
                g.mark_partial(f"{skipped} malformed line(s) in mcp/logs/{path.name}")
            for rec in records:
                server = rec.get("server")
                tool = rec.get("tool")
                summary = (
                    rec.get("args_summary")
                    or rec.get("summary")
                    or (f"{server}.{tool}" if tool else server or "mcp call")
                )
                # Normalize into the shared action shape and reuse _ingest_action.
                self._ingest_action(
                    g,
                    {
                        "type": ActionType.MCP_CALL.value,
                        "ts": rec.get("ts"),
                        "profile": rec.get("profile"),
                        "summary": summary,
                        "server": server,
                        "tool": tool,
                    },
                    resolve_agent,
                    default_type=ActionType.MCP_CALL.value,
                )

    def _ingest_action(self, g: Graph, rec: dict, resolve_agent, default_type) -> None:
        atype = str(rec.get("type") or default_type or "").strip()
        if not atype:
            return
        ts = rec.get("ts")
        profile = rec.get("profile")
        summary = str(rec.get("summary") or rec.get("payload_summary") or atype)
        aid = resolve_agent(profile)
        extra = "|".join(
            str(rec.get(k, "")) for k in ("model", "tokens", "cost", "resource", "connector", "server", "tool")
        )
        aid_full = action_id(FRAMEWORK, ts or "", atype, summary, profile or "", extra)
        nid_tail = aid_full.split(":", 1)[1]

        props: dict = {
            "type": atype,
            "agent_id": aid,
            "payload_summary": summary,
            "source": Source.BACKFILL.value,
        }
        if atype not in _VALID_ACTION_TYPES:
            props["nonstandard_type"] = True

        # model_call: attach tokens/cost and the Agent--called-->Model edge.
        model_id = None
        if rec.get("model"):
            model_name = str(rec["model"])
            provider = str(rec.get("provider") or self._provider_for_model(g, model_name) or "unknown")
            model_id = g.node(
                NodeType.MODEL, provider, model_name,
                label=f"{provider}/{model_name}", provider=provider,
                model_name=model_name, used=True,
            )
            props["model_id"] = model_id
            if rec.get("tokens") is not None:
                props["tokens"] = rec["tokens"]
            if rec.get("cost") is not None:
                props["cost"] = rec["cost"]

        if rec.get("connector"):
            props["connector"] = rec["connector"]

        if rec.get("server"):
            props["server"] = rec["server"]
        if rec.get("tool"):
            props["mcp_tool"] = rec["tool"]

        nid = g.node(
            NodeType.ACTION,
            nid_tail,
            label=f"{atype}: {summary}",
            ts=ts,
            **props,
        )
        g.add_edge(nid, Rel.EXECUTED_BY, aid)
        if model_id:
            g.add_edge(aid, Rel.CALLED, model_id)

        # MCP server touched (links the call to its server Resource if known).
        if rec.get("server"):
            rid = make_id(NodeType.RESOURCE, "mcp_server", str(rec["server"]))
            if g.get(rid):
                g.add_edge(nid, Rel.TOUCHED, rid)

        # via skill
        skill_name = rec.get("skill")
        if skill_name:
            sid = make_id(NodeType.SKILL, FRAMEWORK, skill_name)
            if not g.get(sid):
                # action references a skill we didn't see on disk (e.g. deleted)
                sid = g.node(
                    NodeType.SKILL, FRAMEWORK, skill_name, label=str(skill_name),
                    name=str(skill_name), source="unknown", inferred_from_action=True,
                )
            g.add_edge(nid, Rel.VIA, sid)

        # touched resource
        res = rec.get("resource")
        if res:
            kind = _resource_kind(str(res))
            rid = g.node(
                NodeType.RESOURCE, kind, str(res), label=str(res), kind=kind, value=str(res),
            )
            g.add_edge(nid, Rel.TOUCHED, rid)

    @staticmethod
    def _provider_for_model(g: Graph, model_name: str) -> Optional[str]:
        for m in g.by_type(NodeType.MODEL):
            if m.props.get("model_name") == model_name:
                return m.props.get("provider")
        return None

    def _build_memory(self, g: Graph, agents: list[str]) -> None:
        db_path = self.home / "memory" / "memory.db"
        if not db_path.exists():
            return  # optional
        count = None
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                    ).fetchall()
                ]
                for candidate in ("memory", "memories", "knowledge", "documents"):
                    if candidate in tables:
                        count = conn.execute(f"SELECT COUNT(*) FROM {candidate}").fetchone()[0]
                        break
            finally:
                conn.close()
        except sqlite3.Error as exc:
            g.mark_partial(f"memory.db unreadable: {exc}")
            return
        if count is not None:
            for aid in agents:
                node = g.get(aid)
                if node:
                    node.props["memory_items"] = count
