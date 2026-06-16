"""Tests for insikt/collectors/system.py SystemCollector.

The collector reads /proc, /sys and an optional `vcgencmd`. We never touch the
real host: we monkeypatch the module-level helpers `_read`, `_vcgencmd` and
`_cpu_times` to feed canned strings, and `os.statvfs` for disk numbers. Pure
parsing + status-escalation logic is then asserted deterministically.
"""

from __future__ import annotations

import os
from collections import namedtuple
from pathlib import Path

import pytest

from insikt.collectors import system as sysmod
from insikt.collectors.base import CRIT, OK, WARN

# Self-contained fixture path (kept for parity with the suite convention; the
# system collector itself reads /proc, not the fixture tree).
FIX = Path(__file__).resolve().parent / "fixtures" / "hermes_home"

PROFILE = {"system": {"temp_warn": 70, "temp_crit": 80}}

# A realistic /proc/meminfo: 8 GiB total, ~2 GiB available -> ~75% used.
MEMINFO = (
    "MemTotal:        8192000 kB\n"
    "MemFree:         1024000 kB\n"
    "MemAvailable:    2048000 kB\n"
    "Buffers:          100000 kB\n"
    "Cached:           500000 kB\n"
)

_Statvfs = namedtuple("statvfs_result", "f_bsize f_frsize f_blocks f_bfree f_bavail")


def _statvfs_pct(percent_used: float):
    """Return a fake os.statvfs result giving roughly `percent_used` used."""
    frsize = 4096
    blocks = 1_000_000
    # used = total - free(bavail); want bavail = (1-p)*blocks
    bavail = int(blocks * (1.0 - percent_used / 100.0))

    def _fake(_path):
        return _Statvfs(
            f_bsize=frsize, f_frsize=frsize, f_blocks=blocks,
            f_bfree=bavail, f_bavail=bavail,
        )

    return _fake


def _make_reader(mapping: dict, default=None):
    """Build a fake `_read` that dispatches on path substring."""

    def _fake_read(path: str):
        for needle, value in mapping.items():
            if needle in path:
                return value
        return default

    return _fake_read


def _make_vcgencmd(mapping: dict, default=None):
    def _fake_vc(arg: str):
        return mapping.get(arg, default)

    return _fake_vc


def _patch_all(
    monkeypatch,
    *,
    reads=None,
    vc=None,
    cpu_times=None,
    statvfs=None,
):
    """Patch every external touchpoint the collector uses, with safe defaults
    (everything reads as absent unless overridden)."""
    monkeypatch.setattr(sysmod, "_read", _make_reader(reads or {}))
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd(vc or {}))
    # cpu_times default None -> _cpu_percent returns None without sleeping.
    monkeypatch.setattr(sysmod, "_cpu_times", cpu_times or (lambda: None))
    if statvfs is not None:
        monkeypatch.setattr(os, "statvfs", statvfs)
    else:
        monkeypatch.setattr(os, "statvfs", lambda _p: (_ for _ in ()).throw(OSError("no disk")))


# --------------------------------------------------------------------------
# (1) _throttle() bit parsing
# --------------------------------------------------------------------------

def test_throttle_history_set_now_clear(monkeypatch):
    """0x50000 = bits 16 and 18 -> events happened in the past, not active now."""
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd({"get_throttled": "throttled=0x50000"}))
    t = sysmod.SystemCollector(PROFILE)._throttle()
    assert t is not None
    assert t["ever"] is True
    assert t["now"] is False
    assert t["raw"] == "0x50000"
    assert t["flags"]  # non-empty
    # bit16 = under-voltage occurred, bit18 = throttling occurred
    assert "under-voltage has occurred" in t["flags"]
    assert "throttling has occurred" in t["flags"]


def test_throttle_all_clear(monkeypatch):
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd({"get_throttled": "throttled=0x0"}))
    t = sysmod.SystemCollector(PROFILE)._throttle()
    assert t is not None
    assert t["ever"] is False
    assert t["now"] is False
    assert t["flags"] == []


def test_throttle_now_active(monkeypatch):
    """0x1 = bit0 (under-voltage now) -> now True."""
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd({"get_throttled": "throttled=0x1"}))
    t = sysmod.SystemCollector(PROFILE)._throttle()
    assert t["now"] is True
    assert "under-voltage now" in t["flags"]


def test_throttle_absent_or_garbage(monkeypatch):
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd({}))  # returns None
    assert sysmod.SystemCollector(PROFILE)._throttle() is None
    monkeypatch.setattr(sysmod, "_vcgencmd", _make_vcgencmd({"get_throttled": "throttled=0xZZ"}))
    assert sysmod.SystemCollector(PROFILE)._throttle() is None  # bad hex -> None, no raise


# --------------------------------------------------------------------------
# (2) collect() status escalation
# --------------------------------------------------------------------------

def test_collect_temp_crit(monkeypatch):
    _patch_all(
        monkeypatch,
        vc={"measure_temp": "temp=85.0'C"},  # >= temp_crit (80)
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == CRIT
    assert sec.data["temp_c"] == 85.0
    assert "85.0" in sec.summary


def test_collect_temp_warn(monkeypatch):
    _patch_all(
        monkeypatch,
        vc={"measure_temp": "temp=72.5'C"},  # >= temp_warn (70), < crit
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == WARN
    assert sec.data["temp_c"] == 72.5


def test_collect_temp_ok(monkeypatch):
    _patch_all(
        monkeypatch,
        vc={"measure_temp": "temp=40.0'C"},  # below warn
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == OK
    assert sec.data["temp_c"] == 40.0


def test_collect_disk_full_at_least_warn(monkeypatch):
    _patch_all(
        monkeypatch,
        statvfs=_statvfs_pct(95.0),  # disk 95% -> >= 90
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status in (WARN, CRIT)
    assert sec.data["disk"]["percent"] >= 90
    assert "disk" in sec.summary


def test_collect_undervoltage_history_warns(monkeypatch):
    _patch_all(
        monkeypatch,
        vc={"get_throttled": "throttled=0x50000"},  # ever, not now
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == WARN
    assert sec.data["throttle"]["ever"] is True
    assert "history" in sec.summary


def test_collect_throttled_now_is_crit(monkeypatch):
    _patch_all(
        monkeypatch,
        vc={"get_throttled": "throttled=0x1"},  # active now
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == CRIT
    assert "throttled now" in sec.summary


# --------------------------------------------------------------------------
# (3) mem / disk parsing
# --------------------------------------------------------------------------

def test_mem_parsing(monkeypatch):
    _patch_all(
        monkeypatch,
        reads={"/proc/meminfo": MEMINFO},
    )
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    mem = sec.data["mem"]
    assert mem is not None
    # total = 8192000 kB * 1024
    assert mem["total"] == 8192000 * 1024
    # avail = 2048000 kB * 1024 ; used = total - avail
    assert mem["used"] == (8192000 - 2048000) * 1024
    # percent = used/total * 100 = 75.0
    assert mem["percent"] == 75.0
    # 75% is below both warn(85)/crit(90) thresholds -> OK
    assert sec.status == OK


def test_mem_high_warns(monkeypatch):
    # 8 GiB total, only ~0.4 GiB available -> ~95% used
    meminfo = (
        "MemTotal:        8192000 kB\n"
        "MemAvailable:     400000 kB\n"
    )
    _patch_all(monkeypatch, reads={"/proc/meminfo": meminfo})
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.data["mem"]["percent"] >= 90
    assert sec.status == CRIT  # >=90% mem is CRIT in the source
    assert "mem" in sec.summary


def test_disk_parsing(monkeypatch):
    _patch_all(monkeypatch, statvfs=_statvfs_pct(50.0))
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    disk = sec.data["disk"]
    assert disk is not None
    assert disk["total"] == 1_000_000 * 4096
    assert disk["percent"] == pytest.approx(50.0, abs=0.1)
    assert sec.status == OK  # 50% disk is fine


# --------------------------------------------------------------------------
# (4) collect() never raises when everything is absent
# --------------------------------------------------------------------------

def test_collect_all_absent(monkeypatch):
    # _read -> None for every path, _vcgencmd -> None, _cpu_times -> None,
    # os.statvfs raises OSError. The collector must degrade, not raise.
    _patch_all(monkeypatch)  # all defaults = absent
    c = sysmod.SystemCollector(PROFILE)
    sec = c.collect()
    assert sec.status == OK
    assert sec.summary == "host metrics"
    assert sec.available is True
    # nothing readable -> all numeric fields None
    assert sec.data["temp_c"] is None
    assert sec.data["mem"] is None
    assert sec.data["disk"] is None
    assert sec.data["throttle"] is None
    assert sec.data["cpu_percent"] is None
    assert sec.data["model"] == "unknown host"


def test_safe_collect_all_absent(monkeypatch):
    _patch_all(monkeypatch)
    c = sysmod.SystemCollector(PROFILE)
    sec = c.safe_collect()  # the never-raises wrapper used by scan/server
    assert sec.status == OK
    assert sec.available is True


# --------------------------------------------------------------------------
# (5) available() returns a bool
# --------------------------------------------------------------------------

def test_available_returns_bool():
    c = sysmod.SystemCollector(PROFILE)
    result = c.available()
    assert isinstance(result, bool)


def test_available_false_when_no_proc_stat(monkeypatch):
    # available() checks Path("/proc/stat").exists(); force it False.
    monkeypatch.setattr(sysmod.Path, "exists", lambda self: False)
    c = sysmod.SystemCollector(PROFILE)
    assert c.available() is False


# --------------------------------------------------------------------------
# extra: profile thresholds are actually read from the profile
# --------------------------------------------------------------------------

def test_profile_thresholds_applied():
    c = sysmod.SystemCollector(PROFILE)
    assert c.temp_warn == 70.0
    assert c.temp_crit == 80.0
    # with no profile, defaults still sane
    d = sysmod.SystemCollector(None)
    assert d.temp_warn == 70.0
    assert d.temp_crit == 80.0
