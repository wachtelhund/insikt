"""Tests for insikt/report/dashboard.py :: render_dashboard.

render_dashboard(state, live) builds a single self-contained HTML page:
  - __TITLE__  -> html.escape(f"Insikt — {state['meta']['host']}")
  - __LIVE__   -> "true" if live else "false"   (injected as `const LIVE=__LIVE__;`)
  - __DATA__   -> json.dumps(state, default=str).replace("</", "<\\/")
                  embedded inside <script id="d" type="application/json">...</script>

The "</" -> "<\\/" replacement is the script-tag breakout guard: it must turn any
"</script>" (or any "</") inside the inlined JSON into a "<\\/" sequence so the
browser never sees a real closing tag. Because "\\/" is a legal JSON string escape
for "/", the data still round-trips through JSON.parse back to the original dict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from insikt.report.dashboard import render_dashboard

# Self-contained fixture path (exists in the repo; render_dashboard itself takes a
# state dict and does not read it, but we keep the derivation per project convention).
FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"


def _state(**overrides):
    """A small valid state dict shaped like report builder output."""
    state = {
        "meta": {
            "host": "raspberrypi.local",
            "model": "Raspberry Pi 5",
            "generated": "2026-06-15T12:34:56Z",
        },
        "status": "warn",
        "sections": {
            "system": {
                "status": "ok",
                "available": True,
                "title": "Host",
                "summary": "all good",
                "data": {"cpu_percent": 12.0, "temp_c": 41.2},
            },
            "hermes": {
                "status": "warn",
                "available": True,
                "title": "Hermes",
                "summary": "1 risky skill",
                "data": {"memories": 3, "skills": 2, "actions": 7},
            },
        },
        "agent": None,
    }
    state.update(overrides)
    return state


def _extract_embedded_json(html: str) -> str:
    """Pull the raw text inside <script id="d" ...>...</script>."""
    m = re.search(
        r'<script id="d"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert m, "could not find <script id=\"d\"> block in output"
    return m.group(1)


def test_fixture_dir_present():
    # Sanity: the self-contained fixture path resolves (used across the suite).
    assert FIX.is_dir()


def test_starts_with_doctype_and_is_full_page():
    html = render_dashboard(_state(), live=False)
    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    # It is a single self-contained document: no external network references.
    assert "http://" not in html
    assert "https://" not in html


def test_title_and_host_present():
    html = render_dashboard(_state(host_override=None), live=False)
    # host name shows up in the <title> via the escaped "Insikt — <host>" string.
    assert "raspberrypi.local" in html
    assert "<title>Insikt — raspberrypi.local</title>" in html


def test_no_template_placeholders_left():
    html = render_dashboard(_state(), live=True)
    for ph in ("__TITLE__", "__LIVE__", "__DATA__"):
        assert ph not in html, f"placeholder {ph} was not substituted"


def test_embedded_json_roundtrips_to_equal_state():
    state = _state()
    html = render_dashboard(state, live=False)
    raw = _extract_embedded_json(html)
    parsed = json.loads(raw)
    # status + sections are preserved verbatim through the inline-JSON round trip.
    assert parsed["status"] == state["status"]
    assert parsed["sections"] == state["sections"]
    assert parsed["meta"]["host"] == state["meta"]["host"]
    # Whole dict round-trips (no string values here contain "</", so byte-equal too).
    assert parsed == state


def test_live_true_injects_boolean_true():
    html = render_dashboard(_state(), live=True)
    assert "const LIVE=true;" in html
    assert "const LIVE=false;" not in html


def test_live_false_injects_boolean_false():
    html = render_dashboard(_state(), live=False)
    assert "const LIVE=false;" in html
    assert "const LIVE=true;" not in html


def test_live_defaults_to_false():
    html = render_dashboard(_state())
    assert "const LIVE=false;" in html


def test_script_breakout_is_escaped():
    """A value containing </script> must NOT appear as a real closing tag inside
    the data block; it must be neutralised to "<\\/script>" so it cannot break out."""
    state = _state()
    state["sections"]["hermes"]["summary"] = "</script><x>"
    html = render_dashboard(state, live=False)

    raw = _extract_embedded_json(html)
    # The dangerous closing tag must not survive inside the data block...
    assert "</script>" not in raw
    # ...the breakout sequence is rewritten to the escaped form.
    assert r"<\/script>" in raw

    # There must be exactly one real </script> closing tag for the data block region,
    # i.e. the injected value did not introduce an extra premature </script>.
    # Count closing script tags before the data-block's own terminator.
    data_block_start = html.index('<script id="d"')
    # The first real </script> after the data block start closes the data block.
    first_close = html.index("</script>", data_block_start)
    inner = html[data_block_start:first_close]
    assert "</script>" not in inner[inner.index(">") + 1:], (
        "injected </script> leaked into the data block as a real closing tag"
    )


def test_script_breakout_still_roundtrips():
    """The escape must be a *JSON* escape so JSON.parse / json.loads recovers it."""
    state = _state()
    state["sections"]["hermes"]["summary"] = "</script><x>"
    html = render_dashboard(state, live=False)
    parsed = json.loads(_extract_embedded_json(html))
    # "<\\/" is the JSON escape for "</" -> json.loads gives the original string back.
    assert parsed["sections"]["hermes"]["summary"] == "</script><x>"
    assert parsed["sections"] == state["sections"]


def test_generic_closing_angle_slash_escaped():
    """Any "</" (not just "</script>") is escaped — covers "</div>", "</a>", etc."""
    state = _state()
    state["sections"]["hermes"]["summary"] = "danger </div> and </a>"
    html = render_dashboard(state, live=False)
    raw = _extract_embedded_json(html)
    assert "</div>" not in raw
    assert "</a>" not in raw
    assert r"<\/div>" in raw
    assert r"<\/a>" in raw
    # round-trips back to the original
    assert json.loads(raw)["sections"]["hermes"]["summary"] == "danger </div> and </a>"


def test_non_serializable_values_degrade_via_default_str():
    """default=str means a non-JSON-native value (e.g. a Path) doesn't crash render."""
    state = _state()
    state["meta"]["generated"] = FIX  # a Path object — not natively JSON serializable
    html = render_dashboard(state, live=False)
    assert html.startswith("<!DOCTYPE html>")
    parsed = json.loads(_extract_embedded_json(html))
    # serialized as its string form
    assert parsed["meta"]["generated"] == str(FIX)


def test_missing_meta_host_uses_system_fallback():
    """Degrade path: no meta.host -> title falls back to 'system', no crash."""
    state = _state()
    state["meta"] = {}  # no host key
    html = render_dashboard(state, live=False)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>Insikt — system</title>" in html


def test_completely_empty_state_does_not_crash():
    """Degrade path: empty dict still produces a full page with safe defaults."""
    html = render_dashboard({}, live=False)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>Insikt — system</title>" in html
    parsed = json.loads(_extract_embedded_json(html))
    assert parsed == {}


def test_title_html_is_escaped():
    """A host containing HTML metacharacters must be html-escaped in <title>."""
    state = _state()
    state["meta"]["host"] = '<b>"x"&y</b>'
    html = render_dashboard(state, live=False)
    # raw angle brackets from the host must not appear unescaped in the title.
    assert "<title>Insikt — &lt;b&gt;" in html
    assert "&amp;y" in html
    assert "<title>Insikt — <b>" not in html
