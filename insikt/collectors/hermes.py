"""Hermes collector (README/SPEC §3.1) — reads the real ``~/.hermes`` layout.

Driven by a declarative **profile** (:mod:`insikt.profiles`) so paths/field names
can be adjusted for version drift or a non-standard install without code changes.
Maps the live Hermes layout:

* ``config.yaml``            -> agent, default model, gateway/approvals/security
  posture, messaging connectors, and config-stored ``CredentialRef``s.
* ``.env``                   -> ``CredentialRef`` nodes (key **names** only).
* ``channel_directory.json`` -> messaging ``Connector`` inventory.
* ``skills/**/SKILL.md``     -> ``Skill`` nodes (frontmatter + body for hygiene);
  ``skills/.bundled_manifest`` distinguishes bundled vs. local/self-authored and
  provides ``origin_hash``; ``skills/.usage.json`` adds usage/state.
* ``cron/jobs.json``         -> scheduled-task inventory + run ``Action``s.
* ``sessions/sessions.json`` -> per-conversation model usage + cost ledger.
* ``memories/MEMORY.md``     -> memory inventory (count only).
* ``honcho.json``            -> Honcho integration (presence).

Every read is defensive: a missing/malformed input adds a ``partial`` reason
instead of raising (SPEC §3, §10.3).
"""

from __future__ import annotations

import json
import platform as _platform
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

import yaml

from ..model import ActionType, Graph, NodeType, Rel, ResourceKind, Source, ToolKind, action_id, make_id
from ..profiles import HERMES_LAYOUT, hermes_layout, scoped
from ..redact import redact_secrets
from .base import CRIT, OFF, OK, WARN, Collector, Section

FRAMEWORK = "hermes"
_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|credential|bearer|webhook)")


# --- shared helpers (also imported by the OpenClaw collector) -------------
def _credential_scope(name: str) -> str:
    base = name.lower().split(".")[-1]
    for suffix in ("_api_key", "_token", "_secret", "_key", "_password", "_pat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    head = name.lower().split(".")[0]
    return head or (base.split("_")[0] if base else "general")


def _resource_kind(value: str) -> str:
    v = value.strip()
    if v.startswith(("http://", "https://")):
        return ResourceKind.API
    if v.startswith(("/", "~", "./", "../")):
        return ResourceKind.FS_PATH
    if "/" not in v and ("." in v or ":" in v):
        return ResourceKind.HOST
    return ResourceKind.FS_PATH


def _read_jsonl(path: Path) -> tuple[list[dict], int]:
    records, skipped = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            records.append(obj) if isinstance(obj, dict) else None
            skipped += 0 if isinstance(obj, dict) else 1
        except json.JSONDecodeError:
            skipped += 1
    return records, skipped


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        parts = text.split("\n")
        for i in range(1, len(parts)):
            if parts[i].strip() == "---":
                try:
                    fm = yaml.safe_load("\n".join(parts[1:i])) or {}
                    fm = fm if isinstance(fm, dict) else {}
                except yaml.YAMLError:
                    fm = {}
                return fm, "\n".join(parts[i + 1:])
    return {}, text


def _as_iso(value) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _dig(d: dict, dotted: Optional[str]):
    if not dotted:
        return None
    cur = d
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _json(path: Optional[Path]):
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class HermesGraphScanner:
    """Reads a Hermes home into the normalized capability/action graph. Plain
    class (not a dashboard Collector) — the agent-audit graph is its product;
    ``build_hermes`` below turns it into a dashboard Section."""

    def __init__(self, home: Optional[str | Path] = None, layout: Optional[dict] = None):
        import os

        self.profile = {**HERMES_LAYOUT, **(layout or {})}
        raw = home or self.profile.get("home") or os.environ.get("HERMES_HOME") or "~/.hermes"
        self.home = Path(raw).expanduser()

    def _p(self, rel: str) -> Optional[Path]:
        return scoped(self.home, rel)

    def available(self) -> bool:
        return self.home.is_dir() and (
            (self.home / self.profile.get("config_file", "config.yaml")).exists()
            or (self.home / "skills").is_dir()
        )

    def scan(self) -> Graph:
        g = Graph()
        config = self._read_config(g)
        agent_id = self._build_agent(g, config)
        model_default = self._build_models(g, config)
        self._build_credentials(g, config)
        self._build_connectors(g, config, agent_id)
        self._build_skills(g, agent_id)
        self._build_cron(g, agent_id)
        self._build_sessions(g, agent_id, model_default)
        self._build_memory(g, agent_id)
        self._build_honcho(g, agent_id, config)
        if len(g.nodes) <= 1:
            g.mark_partial("Hermes home present but little readable state — run `insikt configure`")
        return g

    # --- config + agent ---------------------------------------------------
    def _read_config(self, g: Graph) -> dict:
        path = self._p(self.profile.get("config_file", "config.yaml"))
        if not path or not path.exists():
            g.mark_partial("config.yaml not found")
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except (OSError, yaml.YAMLError) as exc:
            g.mark_partial(f"config.yaml unreadable: {exc}")
            return {}

    def _build_agent(self, g: Graph, config: dict) -> str:
        cfg = self.profile.get("config", {})
        gateway = _dig(config, cfg.get("gateway_section")) or {}
        approvals = _dig(config, cfg.get("approvals_section")) or {}
        security = _dig(config, cfg.get("security_section")) or {}
        skills_cfg = _dig(config, cfg.get("skills_section")) or {}
        command_allowlist = config.get("command_allowlist")
        return g.node(
            NodeType.AGENT, FRAMEWORK, self.profile.get("agent_id", "main"),
            label=f"hermes/{self.profile.get('agent_id', 'main')}",
            framework=FRAMEWORK, profile=self.profile.get("agent_id", "main"),
            host=_platform.node() or None,
            version=_dig(config, cfg.get("version_key")),
            gateway_platforms=gateway.get("platforms") if isinstance(gateway, dict) else None,
            gateway_strict=gateway.get("strict") if isinstance(gateway, dict) else None,
            approvals_mode=approvals.get("mode"),
            cron_mode=approvals.get("cron_mode"),
            tirith_enabled=security.get("tirith_enabled"),
            allow_lazy_installs=security.get("allow_lazy_installs"),
            redact_secrets=security.get("redact_secrets"),
            guard_agent_created=skills_cfg.get("guard_agent_created"),
            inline_shell=skills_cfg.get("inline_shell"),
            command_allowlist_empty=(not command_allowlist),
            # Hermes reaches OUT to messaging platforms; it is not a 0.0.0.0 service.
            gateway_bind="messaging",
            auth_mode="platform-auth",
        )

    def _build_models(self, g: Graph, config: dict) -> Optional[str]:
        cfg = self.profile.get("config", {})
        name = _dig(config, cfg.get("model_name"))
        provider = _dig(config, cfg.get("model_provider")) or "unknown"
        if not name:
            return None
        return g.node(
            NodeType.MODEL, provider, name, label=f"{provider}/{name}",
            provider=provider, model_name=str(name), configured=True, is_default=True,
        )

    # --- credentials ------------------------------------------------------
    def _build_credentials(self, g: Graph, config: dict) -> None:
        # .env key names
        env_path = self._p(self.profile.get("env_file", ".env"))
        if env_path and env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key = line.split("=", 1)[0].strip()
                    key = key[len("export "):].strip() if key.startswith("export ") else key
                    if key:
                        g.node(NodeType.CREDENTIAL_REF, key, label=key, name=key,
                               scope=_credential_scope(key), storage="env")
            except OSError as exc:
                g.mark_partial(f".env unreadable: {exc}")
        # config-stored secret keys (names/paths only — values never read)
        for dotted in _walk_secret_keys(config):
            g.node(NodeType.CREDENTIAL_REF, dotted, label=dotted, name=dotted,
                   scope=_credential_scope(dotted), storage="config")

    # --- connectors -------------------------------------------------------
    def _build_connectors(self, g: Graph, config: dict, agent_id: str) -> None:
        platforms: dict[str, dict] = {}
        # 1. channel_directory.json: platform -> [channels]
        cd = _json(self._p(self.profile.get("channel_directory", "")))
        for plat, channels in ((cd or {}).get("platforms") or {}).items():
            if channels:
                platforms.setdefault(plat, {})["channels"] = len(channels)
        # 2. config platform sections present (with content)
        for plat in self.profile.get("config", {}).get("platform_sections", []):
            sect = config.get(plat)
            if isinstance(sect, dict) and sect:
                platforms.setdefault(plat, {})["config"] = sect
        for plat, info in platforms.items():
            sect = info.get("config") or {}
            cid = g.node(
                NodeType.CONNECTOR, plat, label=plat, platform=plat,
                channels=info.get("channels"),
                accepts_strangers=_accepts_strangers(plat, sect),
            )
            g.add_edge(agent_id, Rel.REACHABLE_VIA, cid)

    # --- skills -----------------------------------------------------------
    def _build_skills(self, g: Graph, agent_id: str) -> None:
        skills_root = self.home / "skills"
        if not skills_root.is_dir():
            g.mark_partial("skills/ directory not found")
            return
        bundled = self._read_bundled_manifest()
        usage = _json(self._p(self.profile.get("skills_usage", ""))) or {}
        cred_names = {c.props.get("name", "") for c in g.by_type(NodeType.CREDENTIAL_REF)}
        glob = self.profile.get("skills_glob", "skills/**/SKILL.md")
        # glob is relative to home; restrict to skills/
        for path in sorted(self.home.glob(glob)):
            if scoped(self.home, str(path.relative_to(self.home))) is None:
                continue
            try:
                raw = path.read_bytes()
            except OSError as exc:
                g.mark_partial(f"skill {path.name} unreadable: {exc}")
                continue
            fm, body = _parse_frontmatter(raw.decode("utf-8", errors="replace"))
            name = str(fm.get("name") or path.parent.name)
            category = "/".join(path.parent.relative_to(skills_root).parts[:-1]) or None
            is_bundled = name in bundled
            origin_hash = bundled.get(name) or sha256(raw).hexdigest()
            u = usage.get(name, {}) if isinstance(usage, dict) else {}
            sid = g.node(
                NodeType.SKILL, FRAMEWORK, name, label=name, name=name,
                description=fm.get("description"),
                version=_as_iso(fm.get("version")) if hasattr(fm.get("version"), "isoformat") else fm.get("version"),
                source="bundled" if is_bundled else "local",
                self_authored=not is_bundled,
                origin_hash=origin_hash,
                category=category,
                created_at=_as_iso(u.get("created_at")),
                created_by=u.get("created_by"),
                last_used_at=_as_iso(u.get("last_used_at")),
                use_count=u.get("use_count"),
                state=u.get("state"),
                pinned=u.get("pinned"),
                tags=(_dig(fm, "metadata.hermes.tags") or fm.get("tags")),
                path=str(path),
                body=body[:20000],
                body_excerpt=redact_secrets(body[:1000]),
                declared_tools=[], declared_network=[], declared_credentials=[],
            )
            g.add_edge(agent_id, Rel.USES, sid)
            self._enrich_capabilities(g, sid, name, body, cred_names)

    def _enrich_capabilities(self, g: Graph, sid: str, name: str, body: str, cred_names: set[str]) -> None:
        """Create per-skill Tool/Resource nodes + credential-read edges from what
        the skill body actually does (the static scan is the lower bound, SPEC
        §10.4). Tools are scoped per skill so reach is attributed correctly."""
        from ..hygiene.rules import detect_capabilities, extract_hosts

        caps = detect_capabilities(body)
        for cat, kind in (("shell", "shell"), ("file", "file")):
            if cat in caps:
                tid = g.node(NodeType.TOOL, kind, name, label=kind, kind=kind)
                g.add_edge(sid, Rel.REQUIRES, tid)
        hosts = extract_hosts(body)
        if "network" in caps or hosts:
            web = g.node(NodeType.TOOL, ToolKind.WEB, name, label="web", kind=ToolKind.WEB)
            g.add_edge(sid, Rel.REQUIRES, web)
            for host in sorted(hosts):
                rid = g.node(NodeType.RESOURCE, ResourceKind.HOST, host, label=host, kind=ResourceKind.HOST, value=host)
                g.add_edge(web, Rel.CAN_ACCESS, rid)
        # credential reads: env-style names that literally appear in the body
        for cn in cred_names:
            if cn and cn.isupper() and cn in body:
                g.add_edge(sid, Rel.READS, make_id(NodeType.CREDENTIAL_REF, cn))

    def _read_bundled_manifest(self) -> dict:
        path = self._p(self.profile.get("bundled_manifest", ""))
        out: dict = {}
        if path and path.exists():
            try:
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if ":" in line:
                        n, h = line.split(":", 1)
                        out[n.strip()] = h.strip()
            except OSError:
                pass
        return out

    # --- cron -------------------------------------------------------------
    def _build_cron(self, g: Graph, agent_id: str) -> None:
        data = _json(self._p(self.profile.get("cron_file", "")))
        if not data:
            return
        for job in data.get("jobs", []):
            if not isinstance(job, dict):
                continue
            name = str(job.get("name") or job.get("id") or "cron job")
            ts = job.get("last_run_at") or job.get("created_at")
            model_id = self._model_node(g, job.get("model"), job.get("provider"))
            tail = action_id(FRAMEWORK, ts or "", ActionType.SCHEDULED_RUN.value, name, "", str(job.get("id"))).split(":", 1)[1]
            nid = g.node(
                NodeType.ACTION, tail, label=f"scheduled_run: {name}", ts=_as_iso(ts),
                type=ActionType.SCHEDULED_RUN.value, agent_id=agent_id, payload_summary=name,
                schedule=_dig(job, "schedule.display") or job.get("schedule_display"),
                enabled=job.get("enabled"), last_status=job.get("last_status"),
                model_id=model_id, source=Source.BACKFILL.value, nonstandard_type=True,
            )
            g.add_edge(nid, Rel.EXECUTED_BY, agent_id)
            if model_id:
                g.add_edge(agent_id, Rel.CALLED, model_id)
            skill = job.get("skill") or (job.get("skills") or [None])[0]
            if skill:
                sid = make_id(NodeType.SKILL, FRAMEWORK, skill)
                if g.get(sid):
                    g.add_edge(nid, Rel.VIA, sid)

    # --- sessions (model usage + cost ledger) -----------------------------
    def _build_sessions(self, g: Graph, agent_id: str, model_default: Optional[str]) -> None:
        data = _json(self._p(self.profile.get("sessions_file", "")))
        if not isinstance(data, dict):
            if self.profile.get("sessions_file"):
                g.mark_partial("sessions/sessions.json not found")
            return
        for key, s in data.items():
            if not isinstance(s, dict):
                continue
            tokens = s.get("total_tokens") or 0
            cost = s.get("estimated_cost_usd") or 0
            plat = s.get("platform") or (s.get("origin") or {}).get("platform")
            chat = s.get("display_name") or (s.get("origin") or {}).get("chat_name") or key
            ts = s.get("updated_at") or s.get("created_at")
            summary = f"conversation on {plat}: {chat}" if plat else f"conversation: {chat}"
            # If the instance tracks usage, it's a model_call (cost ledger);
            # otherwise still surface it as messaging activity.
            atype = ActionType.MODEL_CALL.value if (tokens or cost) else ActionType.MESSAGE_SENT.value
            tail = action_id(FRAMEWORK, ts or "", atype, key, "", f"{tokens}|{cost}").split(":", 1)[1]
            nid = g.node(
                NodeType.ACTION, tail, label=f"{atype}: {summary}", ts=_as_iso(ts),
                type=atype, agent_id=agent_id, payload_summary=summary,
                tokens=(tokens or None), cost=(cost or None), connector=plat,
                model_id=(model_default if (tokens or cost) else None),
                source=Source.BACKFILL.value,
            )
            g.add_edge(nid, Rel.EXECUTED_BY, agent_id)
            if (tokens or cost) and model_default:
                g.add_edge(agent_id, Rel.CALLED, model_default)

    # --- memory + honcho --------------------------------------------------
    def _build_memory(self, g: Graph, agent_id: str) -> None:
        path = self._p(self.profile.get("memory_file", ""))
        if not path or not path.exists():
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        entries = sum(1 for ln in text.splitlines() if ln.lstrip().startswith(("- ", "* ", "## ")))
        node = g.get(agent_id)
        if node:
            node.props["memory_items"] = entries or len([ln for ln in text.splitlines() if ln.strip()])

    def _build_honcho(self, g: Graph, agent_id: str, config: dict) -> None:
        data = _json(self._p(self.profile.get("honcho_file", "")))
        node = g.get(agent_id)
        if data and node:
            hosts = list((data.get("hosts") or {}).keys())
            node.props["honcho"] = True
            node.props["honcho_hosts"] = hosts

    # --- model helper -----------------------------------------------------
    def _model_node(self, g: Graph, name, provider) -> Optional[str]:
        if not name:
            return None
        provider = provider or "unknown"
        return g.node(NodeType.MODEL, provider, name, label=f"{provider}/{name}",
                      provider=provider, model_name=str(name), used=True)


def _walk_secret_keys(config: dict, prefix: str = "") -> list[str]:
    """Dotted paths of config keys whose name looks secret AND has a scalar value.
    Values are never returned — only the key path (a CredentialRef name)."""
    out: list[str] = []
    if not isinstance(config, dict):
        return out
    for k, v in config.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.extend(_walk_secret_keys(v, path))
        elif _SECRET_KEY.search(str(k)) and isinstance(v, str) and v.strip():
            # Only string values are credential material; bool/int flags like
            # `redact_secrets: true` are config, not secrets.
            out.append(path)
    return out


def _accepts_strangers(platform: str, section: dict) -> bool:
    """Heuristic: does this connector accept unsolicited messages from strangers?"""
    if not isinstance(section, dict):
        return False
    if section.get("require_mention") is True or section.get("strict_mention") is True:
        return False
    # an explicit allow-list of chats/channels narrows exposure. For Hermes
    # telegram, `group_allowed_chats` is a hard gate (messages outside it are
    # dropped) and `allowed_chats` whitelists where the bot responds — either,
    # if set, means it is NOT open to arbitrary senders.
    for k in ("allowed_chats", "allowed_channels", "group_allowed_chats"):
        v = section.get(k)
        if isinstance(v, str) and v.strip():
            return False
        if isinstance(v, (list, tuple)) and v:
            return False
    return True


def build_hermes(profile: dict, now=None) -> tuple[dict, Optional[dict]]:
    """Turn a Hermes home into (dashboard Section, agent-audit payload).

    The Section is the at-a-glance summary (version/memories/skills/models/
    findings); the payload carries the full capability / timeline / cost /
    hygiene / graph views the dashboard's Hermes tabs render. Raw skill bodies
    are dropped before the payload is built (never persisted/exposed)."""
    from ..hygiene import HygieneEngine, load_advisory_feed
    from ..views import capability_surface, cost_ledger, graph_payload, query_actions

    home = (profile.get("hermes") or {}).get("home")
    scanner = HermesGraphScanner(home=home, layout=hermes_layout(profile))
    if not scanner.available():
        return (
            Section("hermes", "Hermes", available=False, status=OFF,
                    summary="not found", data={"home": str(scanner.home)}).to_dict(),
            None,
        )
    g = scanner.scan()
    feed = load_advisory_feed(Path(__file__).resolve().parents[1] / "data" / "advisory_feed.json")
    hygiene = HygieneEngine(advisory_feed=feed).scan(g)

    agents = g.by_type(NodeType.AGENT)
    a = agents[0] if agents else None
    skills = g.by_type(NodeType.SKILL)
    models = g.by_type(NodeType.MODEL)
    conns = g.by_type(NodeType.CONNECTOR)
    actions = g.actions()
    sev = {}
    for f in hygiene.findings:
        sev[f.severity.value] = sev.get(f.severity.value, 0) + 1

    status = CRIT if sev.get("critical") else WARN if (sev.get("high") or sev.get("medium")) else OK
    memories = a.props.get("memory_items") if a else None
    data = {
        "config_version": a.props.get("version") if a else None,
        "host": a.props.get("host") if a else None,
        "gateway_platforms": a.props.get("gateway_platforms") if a else None,
        "memories": memories,
        "skills": len(skills),
        "self_authored": sum(1 for s in skills if s.props.get("self_authored")),
        "risky_skills": sum(1 for s in skills if s.props.get("risk") in ("critical", "high")),
        "models": len(models),
        "default_model": next((m.label for m in models if m.props.get("is_default")), None),
        "connectors": len(conns),
        "open_connectors": [c.props.get("platform") for c in conns if c.props.get("accepts_strangers")],
        "actions": len(actions),
        "findings": sev,
    }
    bits = []
    if memories is not None:
        bits.append(f"{memories} memories")
    bits.append(f"{len(skills)} skills")
    bits.append(f"{len(models)} models")
    if actions:
        bits.append(f"{len(actions)} actions")
    if sev.get("critical") or sev.get("high"):
        bits.append(f"⚠ {sev.get('critical',0)+sev.get('high',0)} to review")

    # privacy / size: never carry raw skill bodies into the payload
    for s in skills:
        s.props.pop("body", None)

    section = Section("hermes", "Hermes", available=True, status=status,
                      summary="  ·  ".join(bits), data=data,
                      partial=g.partial, reasons=g.partial_reasons[:5]).to_dict()
    payload = {
        "capability": capability_surface(g),
        "timeline": query_actions(g, window="all", now=now, limit=1000),
        "cost": cost_ledger(g),
        "hygiene": hygiene.to_dict(),
        "graph": graph_payload(g),
    }
    return section, payload
