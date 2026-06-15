---
name: summarize
source: builtin
self_authored: false
created_at: 2026-01-02T00:00:00Z
tools: [web]
network: [api.anthropic.com]
requires_credentials: [ANTHROPIC_API_KEY]
---
# summarize

Built-in skill. Summarizes a block of text by calling the configured model.
Network egress is limited to the model provider (api.anthropic.com), which is on
the default allowlist, so this should not raise an egress finding.
