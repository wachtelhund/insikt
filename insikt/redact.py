"""Secret redaction for any free text Insikt retains or re-exposes.

Insikt's contract is "never secret *values*" (README §1, §8.2). Key *names* from
``.env`` are safe and intended. But a skill body or an MCP server's args can
contain a *hardcoded* secret, and those strings are persisted and surfaced via
``insikt_explain`` / the report. This pass redacts well-known secret shapes from
such text before it is stored or returned.

It is intentionally conservative (clear token shapes + ``KEY=secret`` style
assignments) so it does not mangle legitimate content, and it runs *after* the
hygiene static scan so it never blinds the obfuscation/credential detectors.
"""

from __future__ import annotations

import re

_TOKEN_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{12,}"),          # Anthropic
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),              # OpenAI-style
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),          # GitHub
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),       # Slack
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access key id
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}"),  # JWT
]

# KEY = "secret" / "token": secret — keep the key, redact the value.
_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Za-z0-9_\-]*(?:api[_-]?key|secret|token|password|passwd|bearer)[A-Za-z0-9_\-]*)"
    r"(\s*[:=]\s*[\"']?)"
    r"([^\s\"',]{6,})"
)

REDACTED = "[REDACTED]"


def redact_secrets(text: str | None) -> str | None:
    """Replace recognizable secret material in ``text`` with ``[REDACTED]``."""
    if not text:
        return text
    out = text
    for pat in _TOKEN_PATTERNS:
        out = pat.sub(REDACTED, out)
    out = _ASSIGNMENT.sub(lambda m: m.group(1) + m.group(2) + REDACTED, out)
    return out


def redact_list(values) -> list:
    """Redact each string in a list (used for MCP server args)."""
    if not values:
        return values
    return [redact_secrets(str(v)) if isinstance(v, str) else v for v in values]
