"""OpenClaw collector (README §3.2).

Reads ``~/.openclaw`` read-only:

* ``openclaw.json``        -> gateway bind/port, auth mode, tailscale exposure,
  configured models, host.
* ``credentials/<platform>/`` -> ``Connector`` inventory (**presence only**, never
  secret material).
* ``skills/<pkg>/``        -> ``Skill`` nodes (``source=clawhub``) with package
  name/version for hygiene/advisory lookups; the entry script body is retained
  for the static scan.
* ``usage.jsonl``          -> model usage, cost ledger, ``Action`` stream, cron
  jobs (tagged ``source=backfill``).

OpenClaw is a v1 target; this collector is intentionally lean and marks itself
``partial`` so downstream never overstates completeness. It exists primarily to
prove the cross-framework split: it shares zero code with Hermes below the
collector line.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

from ..model import ActionType, Graph, NodeType, Rel, Source, action_id
from ..redact import redact_secrets
from .base import Collector, CollectorResult
from .hermes import _read_jsonl, _resource_kind

FRAMEWORK = "openclaw"
_VALID_ACTION_TYPES = {t.value for t in ActionType}


class OpenClawCollector(Collector):
    framework = FRAMEWORK
    supported_versions = ">=2.0,<3.0"

    def __init__(self, home: Optional[str | Path] = None, profile: Optional[dict] = None):
        from ..profiles import load_profile

        self.profile = profile or load_profile(FRAMEWORK, home=str(home) if home else None)
        raw = home or self.profile.get("home") or os.environ.get("OPENCLAW_HOME") or "~/.openclaw"
        self.home = Path(raw).expanduser()

    def available(self) -> bool:
        return self.home.is_dir() and (
            (self.home / "openclaw.json").exists() or (self.home / "skills").is_dir()
        )

    def collect(self) -> CollectorResult:
        g = Graph()
        config = self._read_config(g)
        detected_version = str(config.get("version")) if config.get("version") else None
        host = config.get("host")

        agent_id = self._build_agent(g, config, host)
        self._build_models(g, config)
        self._build_connectors(g, agent_id)
        self._build_skills(g, agent_id)
        self._build_actions(g, agent_id)

        # OpenClaw support is preliminary; never claim completeness.
        g.mark_partial("OpenClaw collector is preliminary (v1 target)")

        return CollectorResult(
            framework=FRAMEWORK,
            graph=g,
            available=self.available(),
            supported_versions=self.supported_versions,
            detected_version=detected_version,
        )

    # --- readers ----------------------------------------------------------
    def _read_config(self, g: Graph) -> dict:
        path = self.home / "openclaw.json"
        if not path.exists():
            g.mark_partial("openclaw.json not found")
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            g.mark_partial(f"openclaw.json unreadable: {exc}")
            return {}

    def _build_agent(self, g: Graph, config: dict, host: Optional[str]) -> str:
        gateway = config.get("gateway") or {}
        bind = gateway.get("bind")
        port = gateway.get("port")
        bind_full = f"{bind}:{port}" if bind and port else bind
        tailscale = (config.get("tailscale") or {}).get("exposed")
        return g.node(
            NodeType.AGENT,
            FRAMEWORK,
            "default",
            label="openclaw/default",
            framework=FRAMEWORK,
            profile="default",
            version=config.get("version"),
            host=host,
            gateway_bind=bind_full,
            auth_mode=gateway.get("auth", "unknown"),
            tailscale_exposed=tailscale,
        )

    def _build_models(self, g: Graph, config: dict) -> None:
        for m in config.get("models") or []:
            if not isinstance(m, dict):
                continue
            provider = m.get("provider", "unknown")
            name = m.get("model") or m.get("name") or "unknown"
            g.node(
                NodeType.MODEL, provider, name, label=f"{provider}/{name}",
                provider=provider, model_name=name, endpoint=m.get("endpoint"),
                configured=True,
            )

    def _build_connectors(self, g: Graph, agent_id: str) -> None:
        creds_dir = self.home / "credentials"
        if not creds_dir.is_dir():
            return
        for platform_dir in sorted(p for p in creds_dir.iterdir() if p.is_dir()):
            cid = g.node(
                NodeType.CONNECTOR, platform_dir.name, label=platform_dir.name,
                platform=platform_dir.name, accepts_strangers=False,
            )
            g.add_edge(agent_id, Rel.REACHABLE_VIA, cid)

    def _build_skills(self, g: Graph, agent_id: str) -> None:
        skills_dir = self.home / "skills"
        if not skills_dir.is_dir():
            g.mark_partial("skills/ directory not found")
            return
        for pkg_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            meta = {}
            pkg_json = pkg_dir / "package.json"
            if pkg_json.exists():
                try:
                    meta = json.loads(pkg_json.read_text(encoding="utf-8")) or {}
                except (OSError, json.JSONDecodeError):
                    g.mark_partial(f"skills/{pkg_dir.name}/package.json unreadable")
            name = str(meta.get("name") or pkg_dir.name)
            version = meta.get("version")
            # Concatenate entry scripts for the static scan + hash.
            body_parts, raw = [], b""
            for src in sorted(pkg_dir.glob("*.js")) + sorted(pkg_dir.glob("*.md")):
                try:
                    b = src.read_bytes()
                    raw += b
                    body_parts.append(b.decode("utf-8", errors="replace"))
                except OSError:
                    continue
            origin_hash = sha256(raw).hexdigest() if raw else None
            body = "\n".join(body_parts)
            sid = g.node(
                NodeType.SKILL, FRAMEWORK, name, label=name, name=name,
                source="clawhub", package_version=version, origin_hash=origin_hash,
                self_authored=False, path=str(pkg_dir), body=body[:20000],
                body_excerpt=redact_secrets(body[:1000]),
                declared_tools=[], declared_network=[], declared_credentials=[],
            )
            g.add_edge(agent_id, Rel.USES, sid)

    def _build_actions(self, g: Graph, agent_id: str) -> None:
        path = self.home / "usage.jsonl"
        if not path.exists():
            g.mark_partial("usage.jsonl not found")
            return
        records, skipped = _read_jsonl(path)
        if skipped:
            g.mark_partial(f"{skipped} malformed line(s) in usage.jsonl")
        for rec in records:
            atype = str(rec.get("type") or "").strip()
            if not atype:
                continue
            ts = rec.get("ts")
            summary = str(rec.get("summary") or rec.get("payload_summary") or atype)
            props: dict = {
                "type": atype,
                "agent_id": agent_id,
                "payload_summary": summary,
                "source": Source.BACKFILL.value,
            }
            if atype not in _VALID_ACTION_TYPES:
                props["nonstandard_type"] = True
            model_id = None
            if rec.get("model"):
                provider = str(rec.get("provider") or "unknown")
                model_id = g.node(
                    NodeType.MODEL, provider, str(rec["model"]),
                    label=f"{provider}/{rec['model']}", provider=provider,
                    model_name=str(rec["model"]), used=True,
                )
                props["model_id"] = model_id
                if rec.get("tokens") is not None:
                    props["tokens"] = rec["tokens"]
                if rec.get("cost") is not None:
                    props["cost"] = rec["cost"]
            if rec.get("connector"):
                props["connector"] = rec["connector"]
            if rec.get("cron"):
                props["cron"] = rec["cron"]

            extra = "|".join(
                str(rec.get(k, "")) for k in ("model", "tokens", "cost", "resource", "connector", "cron")
            )
            tail = action_id(FRAMEWORK, ts or "", atype, summary, "", extra).split(":", 1)[1]
            nid = g.node(NodeType.ACTION, tail, label=f"{atype}: {summary}", ts=ts, **props)
            g.add_edge(nid, Rel.EXECUTED_BY, agent_id)
            if model_id:
                g.add_edge(agent_id, Rel.CALLED, model_id)
            if rec.get("resource"):
                kind = _resource_kind(str(rec["resource"]))
                rid = g.node(
                    NodeType.RESOURCE, kind, str(rec["resource"]),
                    label=str(rec["resource"]), kind=kind, value=str(rec["resource"]),
                )
                g.add_edge(nid, Rel.TOUCHED, rid)
