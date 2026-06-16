"""Host / Raspberry Pi metrics collector — the live heartbeat of the dashboard.

Pure stdlib + an optional ``vcgencmd`` (Raspberry Pi) for temperature and the
throttle bits. Reads ``/proc`` and ``/sys`` so it works on any Linux; on a Pi it
additionally reports SoC temperature and under-voltage/throttle history. On a
non-Linux host it degrades to whatever is readable.

Fast refresh (a few seconds): CPU% is computed from the delta between successive
``/proc/stat`` reads, so the collector instance is reused across ticks by the
server; a one-off ``scan`` samples a short interval itself.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import CRIT, OK, WARN, Collector, Section

# vcgencmd get_throttled bit meanings.
_THROTTLE_BITS = {
    0: "under-voltage now",
    1: "ARM frequency capped now",
    2: "currently throttled",
    3: "soft temperature limit now",
    16: "under-voltage has occurred",
    17: "ARM frequency capping has occurred",
    18: "throttling has occurred",
    19: "soft temperature limit has occurred",
}


def _read(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _vcgencmd(arg: str) -> Optional[str]:
    try:
        out = subprocess.run(["vcgencmd", arg], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _cpu_times() -> Optional[tuple[int, int]]:
    line = _read("/proc/stat")
    if not line:
        return None
    parts = line.splitlines()[0].split()
    if parts[0] != "cpu":
        return None
    vals = [int(x) for x in parts[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
    total = sum(vals)
    return total, idle


class SystemCollector(Collector):
    key = "system"
    title = "Host"
    interval = 3.0

    def __init__(self, profile: Optional[dict] = None):
        super().__init__(profile)
        self._prev: Optional[tuple[int, int]] = None
        opts = self.conf or {}
        self.temp_warn = float(opts.get("temp_warn", 70))
        self.temp_crit = float(opts.get("temp_crit", 80))

    def available(self) -> bool:
        return Path("/proc/stat").exists()

    # --- pieces -----------------------------------------------------------
    def _temp_c(self) -> Optional[float]:
        v = _vcgencmd("measure_temp")  # "temp=42.8'C"
        if v:
            m = re.search(r"([\d.]+)", v)
            if m:
                return float(m.group(1))
        raw = _read("/sys/class/thermal/thermal_zone0/temp")
        if raw and raw.lstrip("-").isdigit():
            return round(int(raw) / 1000.0, 1)
        return None

    def _cpu_percent(self) -> Optional[float]:
        cur = _cpu_times()
        if cur is None:
            return None
        if self._prev is None:
            self._prev = cur
            time.sleep(0.25)
            cur = _cpu_times()
            if cur is None:
                return None
        dt = cur[0] - self._prev[0]
        di = cur[1] - self._prev[1]
        self._prev = cur
        if dt <= 0:
            return None
        return round(100.0 * (dt - di) / dt, 1)

    def _mem(self) -> Optional[dict]:
        info = _read("/proc/meminfo")
        if not info:
            return None
        kv = {}
        for ln in info.splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                kv[k.strip()] = v.strip()
        total = int(kv.get("MemTotal", "0 kB").split()[0]) * 1024
        avail = int(kv.get("MemAvailable", "0 kB").split()[0]) * 1024
        if not total:
            return None
        used = total - avail
        return {"total": total, "used": used, "percent": round(100.0 * used / total, 1)}

    def _disk(self) -> Optional[dict]:
        try:
            st = os.statvfs("/")
        except OSError:
            return None
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        if not total:
            return None
        return {"total": total, "used": used, "percent": round(100.0 * used / total, 1)}

    def _throttle(self) -> Optional[dict]:
        v = _vcgencmd("get_throttled")  # "throttled=0x50000"
        if not v or "=" not in v:
            return None
        raw = v.split("=", 1)[1].strip()
        try:
            bits = int(raw, 16)
        except ValueError:
            return None
        flags = [label for bit, label in _THROTTLE_BITS.items() if bits & (1 << bit)]
        return {
            "raw": raw,
            "now": bool(bits & 0b1111),
            "ever": bool(bits & (0b1111 << 16)),
            "flags": flags,
        }

    # --- collect ----------------------------------------------------------
    def collect(self) -> Section:
        model = (_read("/proc/device-tree/model") or "").replace("\x00", "").strip()
        is_pi = "raspberry pi" in model.lower()
        temp = self._temp_c()
        cpu = self._cpu_percent()
        mem = self._mem()
        disk = self._disk()
        throttle = self._throttle()
        load = None
        la = _read("/proc/loadavg")
        if la:
            load = [float(x) for x in la.split()[:3]]
        uptime = None
        up = _read("/proc/uptime")
        if up:
            uptime = int(float(up.split()[0]))

        data = {
            "model": model or "unknown host",
            "is_pi": is_pi,
            "cores": os.cpu_count(),
            "temp_c": temp,
            "cpu_percent": cpu,
            "load": load,
            "mem": mem,
            "disk": disk,
            "uptime_s": uptime,
            "throttle": throttle,
        }

        status, notes = OK, []
        if temp is not None:
            if temp >= self.temp_crit:
                status, n = CRIT, f"temp {temp}°C"
                notes.append(n)
            elif temp >= self.temp_warn:
                status, n = WARN, f"temp {temp}°C"
                notes.append(n)
        if mem and mem["percent"] >= 90:
            status = CRIT if status != CRIT else status
            notes.append(f"mem {mem['percent']}%")
        elif mem and mem["percent"] >= 85 and status == OK:
            status = WARN
        if disk and disk["percent"] >= 90:
            status = WARN if status == OK else status
            notes.append(f"disk {disk['percent']}%")
        if throttle and throttle["now"]:
            status = CRIT
            notes.append("throttled now")
        elif throttle and throttle["ever"] and status == OK:
            status = WARN
            notes.append("under-voltage/throttle in history")

        bits = []
        if temp is not None:
            bits.append(f"{temp}°C")
        if cpu is not None:
            bits.append(f"CPU {cpu:.0f}%")
        if mem:
            bits.append(f"mem {mem['percent']:.0f}%")
        if uptime:
            bits.append(f"up {_fmt_uptime(uptime)}")
        summary = "  ·  ".join(bits) or "host metrics"

        return Section(key=self.key, title=self.title, available=True, status=status,
                       summary=summary + (f"  ·  ⚠ {'; '.join(notes)}" if notes and status != OK else ""),
                       data=data)


def _fmt_uptime(s: int) -> str:
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"
