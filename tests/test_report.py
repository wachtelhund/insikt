import json
import re

from insikt.hygiene import HygieneEngine
from insikt.report import render_report


def _render(graph, now):
    hygiene = HygieneEngine().scan(graph)
    return render_report(graph, meta={"frameworks": ["hermes"], "snapshot_id": 1, "host": "pi-hermes"}, hygiene=hygiene, now=now)


def test_report_renders(hermes_graph, now):
    html = _render(hermes_graph, now)
    assert html.startswith("<!DOCTYPE html>")
    assert "insikt-data" in html
    assert "pi-temp-watch" in html


def test_report_is_self_contained(hermes_graph, now):
    html = _render(hermes_graph, now)
    # No external assets: no remote scripts/stylesheets/CDNs.
    assert "<script src" not in html.lower()
    assert "<link" not in html.lower()
    assert "cdn" not in html.lower()
    assert "googleapis" not in html.lower()


def test_report_embedded_json_is_valid(hermes_graph, now):
    html = _render(hermes_graph, now)
    m = re.search(r'<script id="insikt-data" type="application/json">(.*?)</script>', html, re.DOTALL)
    assert m
    raw = m.group(1).replace("<\\/", "</")  # undo the </script> guard
    payload = json.loads(raw)
    assert payload["summary"]["skills"] == 3
    assert payload["meta"]["host"] == "pi-hermes"
    assert payload["graph"]["nodes"]
    # bodies are stripped from the graph payload (report stays small / no secret-adjacent text)
    assert all("body" not in n["props"] for n in payload["graph"]["nodes"])


def test_report_includes_hygiene_and_cost(hermes_graph, now):
    html = _render(hermes_graph, now)
    m = re.search(r'<script id="insikt-data" type="application/json">(.*?)</script>', html, re.DOTALL)
    payload = json.loads(m.group(1).replace("<\\/", "</"))
    assert payload["hygiene"]["findings"]
    assert payload["cost"]["total_tokens"] == 5140
