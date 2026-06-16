"""Tests for insikt/collectors/base.py — the Collector contract.

Covers:
  * Section.to_dict() round-trips every field, and `reasons` is a fresh copy.
  * Collector.safe_collect() never raises: a raising collect() degrades to a
    CRIT/partial/unavailable Section whose reason names the exception type.
  * A well-behaved collect() passes straight through safe_collect() unchanged.
"""

from __future__ import annotations

from pathlib import Path

from insikt.collectors.base import OK, WARN, CRIT, OFF, Section, Collector

# Self-contained fixture path (not strictly needed here, but per the harness
# contract — the base module is framework-agnostic and reads nothing from disk).
FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"


def test_fixture_dir_exists():
    assert FIX.is_dir()


def test_status_constants_are_distinct_strings():
    levels = {OK, WARN, CRIT, OFF}
    assert levels == {"ok", "warn", "crit", "off"}
    assert len(levels) == 4  # no accidental aliasing


def test_section_to_dict_round_trips_every_field():
    reasons = ["reason-a", "reason-b"]
    data = {"count": 3, "nested": {"k": "v"}}
    sec = Section(
        key="pi",
        title="Raspberry Pi",
        available=True,
        status=WARN,
        summary="cpu warm",
        data=data,
        partial=True,
        reasons=reasons,
    )

    d = sec.to_dict()

    # Every declared field is present and value-equal.
    assert d == {
        "key": "pi",
        "title": "Raspberry Pi",
        "available": True,
        "status": WARN,
        "summary": "cpu warm",
        "data": data,
        "partial": True,
        "reasons": reasons,
    }
    # Exactly these keys — nothing extra, nothing missing.
    assert set(d.keys()) == {
        "key", "title", "available", "status",
        "summary", "data", "partial", "reasons",
    }


def test_section_to_dict_reasons_is_a_fresh_list_copy():
    reasons = ["only"]
    sec = Section(key="k", title="t", available=True, reasons=reasons)

    d = sec.to_dict()

    # Equal in value...
    assert d["reasons"] == reasons
    # ...but a distinct list object: mutating the dict must not touch the
    # Section's list, and mutating the Section's list must not touch the dict.
    assert d["reasons"] is not sec.reasons
    assert d["reasons"] is not reasons

    d["reasons"].append("mutated")
    assert sec.reasons == ["only"]

    sec.reasons.append("also-mutated")
    # The previously emitted dict is unaffected by later Section mutation.
    assert d["reasons"] == ["only", "mutated"]


def test_section_defaults():
    sec = Section(key="k", title="t", available=False)
    assert sec.status == OK
    assert sec.summary == ""
    assert sec.data == {}
    assert sec.partial is False
    assert sec.reasons == []
    # default_factory gives independent containers per instance
    other = Section(key="k2", title="t2", available=False)
    sec.data["x"] = 1
    sec.reasons.append("y")
    assert other.data == {}
    assert other.reasons == []


# --- Collector.safe_collect() ------------------------------------------------


class _RaisingCollector(Collector):
    key = "boom"
    title = "Boom Source"

    def available(self) -> bool:
        return True

    def collect(self) -> Section:
        raise ValueError("kaboom-detail")


class _GoodCollector(Collector):
    key = "good"
    title = "Good Source"

    def __init__(self, section: Section, profile=None):
        super().__init__(profile)
        self._section = section

    def available(self) -> bool:
        return True

    def collect(self) -> Section:
        return self._section


def test_safe_collect_never_raises_and_degrades_to_crit_partial():
    sec = _RaisingCollector().safe_collect()

    assert isinstance(sec, Section)
    assert sec.available is False
    assert sec.status == CRIT
    assert sec.partial is True
    # Identity is preserved from the collector's class attributes.
    assert sec.key == "boom"
    assert sec.title == "Boom Source"
    # The reason names the exception *type*.
    assert len(sec.reasons) == 1
    assert "ValueError" in sec.reasons[0]
    # And carries the message too (helpful for the audit trail).
    assert "kaboom-detail" in sec.reasons[0]


def test_safe_collect_reason_names_the_actual_exception_type():
    class _KeyErrCollector(_RaisingCollector):
        def collect(self) -> Section:
            raise KeyError("missing")

    sec = _KeyErrCollector().safe_collect()
    assert "KeyError" in sec.reasons[0]
    assert "ValueError" not in sec.reasons[0]


def test_safe_collect_passes_normal_section_through_unchanged():
    good = Section(
        key="good",
        title="Good Source",
        available=True,
        status=OK,
        summary="all healthy",
        data={"nodes": 7},
        partial=False,
        reasons=[],
    )
    out = _GoodCollector(good).safe_collect()

    # Same object, untouched — no wrapping on the happy path.
    assert out is good
    assert out.to_dict() == good.to_dict()
    assert out.status == OK
    assert out.partial is False
    assert out.available is True


def test_collector_init_scopes_conf_to_its_key():
    profile = {"good": {"path": "/x"}, "other": {"path": "/y"}}
    good = _GoodCollector(Section(key="good", title="t", available=True), profile=profile)
    assert good.profile is profile
    assert good.conf == {"path": "/x"}

    # No profile / non-dict profile must not raise and yields empty conf.
    bare = _GoodCollector(Section(key="good", title="t", available=True))
    assert bare.profile == {}
    assert bare.conf == {}


def test_collector_is_abstract():
    # Cannot instantiate the ABC directly (abstract methods unimplemented).
    import pytest

    with pytest.raises(TypeError):
        Collector()  # type: ignore[abstract]
