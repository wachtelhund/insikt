"""Persistent host-metric history.

The live ``serve`` process appends a compact sample (~1/min) to a JSONL file so
host metrics survive restarts and — crucially — are readable by the **MCP server**
(a separate, on-demand process). That is how the agent answers questions like
*"how was the Pi temperature overnight?"*: the in-memory buffer the dashboard
draws is only minutes deep, but this file spans days.

Privacy: only the same non-identifying numbers the dashboard already shows —
``{t, temp, cpu, mem, disk}`` (an ISO timestamp + four metrics). Never raises.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path("~/.insikt/metrics.jsonl").expanduser()
MAX_LINES = 20160  # ~14 days at one sample/minute
_writes = {"n": 0}


def append(sample: dict, path: Path = DEFAULT_PATH) -> None:
    """Append one ``{t,temp,cpu,mem,disk}`` sample. Never raises; trims occasionally."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample, default=str) + "\n")
        _writes["n"] += 1
        if _writes["n"] % 500 == 0:
            _trim(path)
    except OSError:
        pass


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > MAX_LINES:
            path.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def _parse_ts(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        s = str(ts)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load(path: Path = DEFAULT_PATH, *, since=None, until=None, limit: Optional[int] = None) -> list:
    """Read samples, optionally filtered to ``[since, until)`` and downsampled to
    ``limit`` evenly-spaced points (keeping the most recent)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(s, dict):
            continue
        if since or until:
            t = _parse_ts(s.get("t"))
            if t is None or (since and t < since) or (until and t >= until):
                continue
        out.append(s)
    if limit and len(out) > limit:
        step = len(out) / limit
        out = [out[int(i * step)] for i in range(limit - 1)] + [out[-1]]
    return out


def summarize(samples: list, metric: str) -> Optional[dict]:
    vals = [s[metric] for s in samples
            if isinstance(s, dict) and isinstance(s.get(metric), (int, float))]
    if not vals:
        return None
    return {
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
        "avg": round(sum(vals) / len(vals), 1),
        "count": len(vals),
    }
