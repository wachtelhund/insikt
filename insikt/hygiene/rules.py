"""Static detectors used by the hygiene engine.

These operate on the *normalized graph* (skill bodies, declared metadata, gateway
config) — never on framework-specific paths — so the engine stays
framework-agnostic. The static scan is treated as a **lower bound** on capability
(README §10.4): a skill may do more than its text reveals, which is why the
action audit and diff exist alongside it.
"""

from __future__ import annotations

import re
from typing import Iterable

# Capability category -> compiled patterns. Presence of a category is a *factor*;
# severity comes from the category and from dangerous combinations (the engine).
_CAPABILITY_PATTERNS: dict[str, list[re.Pattern]] = {
    "shell": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bsubprocess\b",
            r"\bos\.system\b",
            r"\bos\.popen\b",
            r"child_process",
            r"\bexecSync\b|\bexec\(",
            r"\bspawn\(",
            r"\b(?:ba)?sh\s+-c\b",
            r"\bvcgencmd\b",
            r"`[^`]*\b(?:rm|curl|wget|cat|sh|bash|sudo)\b[^`]*`",
        )
    ],
    "network": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\brequests\.(?:get|post|put|delete|patch)\b",
            r"\burllib(?:\.request)?\b",
            r"\bhttpx\b",
            r"\bfetch\(",
            r"\baxios\b",
            r"\bsocket\.socket\b",
            r"\bcurl\b|\bwget\b",
            r"https?://",
        )
    ],
    "credential_read": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\.env\b",
            r"\bos\.environ\b",
            r"\bprocess\.env\b",
            r"\bgetenv\b",
            r"\b[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)\b",
            r"read[_-]?secret",
        )
    ],
    "obfuscation": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bbase64\.b64decode\b",
            r"\batob\(",
            r"\bfromCharCode\b",
            r"\beval\(",
            r"\bexec\(\s*(?:base64|bytes|codecs|''\.join)",
            r"[A-Za-z0-9+/]{120,}={0,2}",  # long base64-ish blob
        )
    ],
    "auto_update": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"auto[-_]?update",
            r"self[-_]?update",
            r"git\s+pull",
            r"npm\s+install",
            r"pip\s+install",
            r"curl[^\n|]*\|\s*(?:sh|bash)",
        )
    ],
}

# Severity each detected category contributes on its own (string keys map to
# model.Severity in the engine).
CATEGORY_SEVERITY = {
    "shell": "low",
    "network": "low",
    "credential_read": "low",
    "obfuscation": "high",
    "auto_update": "medium",
}

CATEGORY_TITLE = {
    "shell": "Skill can execute shell commands",
    "network": "Skill performs network egress",
    "credential_read": "Skill reads credentials / environment",
    "obfuscation": "Skill contains obfuscated / encoded payload",
    "auto_update": "Skill has an auto-update / self-modifying hook",
}

_URL_RE = re.compile(r"https?://([A-Za-z0-9._-]+)")

# Default allowlist of egress hosts considered routine for an agent box.
DEFAULT_HOST_ALLOWLIST = {
    "api.anthropic.com",
    "api.openai.com",
    "api.telegram.org",
    "localhost",
    "127.0.0.1",
}


def detect_capabilities(body: str) -> dict[str, list[str]]:
    """Return {category: [evidence snippets]} found in skill text."""
    found: dict[str, list[str]] = {}
    if not body:
        return found
    for category, patterns in _CAPABILITY_PATTERNS.items():
        evidence: list[str] = []
        for pat in patterns:
            m = pat.search(body)
            if m:
                snippet = m.group(0)
                evidence.append(snippet[:80])
        if evidence:
            # de-dup while preserving order
            seen = set()
            found[category] = [e for e in evidence if not (e in seen or seen.add(e))]
    return found


def extract_hosts(body: str, declared: Iterable[str] = ()) -> set[str]:
    hosts = set(declared or ())
    for m in _URL_RE.finditer(body or ""):
        hosts.add(m.group(1).lower())
    return hosts


def non_allowlisted_hosts(hosts: Iterable[str], allowlist: Iterable[str]) -> list[str]:
    allow = {h.lower() for h in allowlist}
    return sorted(h for h in {x.lower() for x in hosts} if h not in allow)
