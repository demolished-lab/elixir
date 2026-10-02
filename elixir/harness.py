# -*- coding: utf-8 -*-
"""Elixir harness: survive fingerprint decay + free 1-seat limit.

- Seat: free tier = 1 concurrent cloak session. Serialize via lock file + queue.
- Pool: N fingerprint seeds per site, sticky until detection, then rotate.
- Decay: periodic stealth self-test; auto `cloakbrowser update` on fail.
- Ladder: cloak -> obscura -> wigolo cache, honest status always.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import time

from .config import PROFILES_DIR, SEAT_LOCK as _SEAT, SEAT_TIMEOUT as _TIMEOUT, STATE_FILE

BASE = PROFILES_DIR.parent
PROFILES = PROFILES_DIR
STATE = STATE_FILE
SEAT_LOCK = _SEAT

SEAT_TIMEOUT = _TIMEOUT  # seconds to wait for free seat


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"seeds": {}, "scores": {}, "cloak_version": None}


def _save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def seed_for(site: str, pool: int = 5) -> str:
    """Sticky seed per site; rotate index on detection via `rotate_seed(site)`."""
    s = _load_state()
    idx = s["seeds"].get(site, 0) % pool
    digest = hashlib.sha256(f"elixir:{site}:{idx}".encode()).hexdigest()
    return str(10000 + int(digest[:6], 16) % 89999)


def rotate_seed(site: str) -> str:
    s = _load_state()
    s["seeds"][site] = s["seeds"].get(site, 0) + 1
    _save_state(s)
    return seed_for(site)


def acquire_seat(timeout: int = SEAT_TIMEOUT) -> None:
    """Block until the single cloak seat is free. File-lock, cross-process."""
    start = time.time()
    while True:
        try:
            fd = os.open(SEAT_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                age = time.time() - SEAT_LOCK.stat().st_mtime
                if age > 300:  # stale lock from crashed run
                    SEAT_LOCK.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise TimeoutError(f"cloak seat busy >{timeout}s (free = 1 session)")
            time.sleep(1.5)


def release_seat() -> None:
    try:
        SEAT_LOCK.unlink(missing_ok=True)
    except OSError:
        pass


def cloak_version() -> str:
    try:
        r = subprocess.run(
            ["python", "-m", "cloakbrowser", "info"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        for line in r.stdout.splitlines():
            if "Version:" in line:
                return line.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def stealth_score_quick() -> dict:
    """Lightweight decay signal: TLS/FP surface without full 30-site suite.

    Returns {"ok": bool, "signals": {...}}. Heavy suite stays manual:
    `examples/stealth_test.py` in cloak repo.
    """
    signals: dict = {}
    try:
        from cloakbrowser import launch

        acquire_seat(timeout=60)
        try:
            b = launch(humanize=True)
            p = b.new_page()
            p.goto("https://example.com", timeout=30000)
            ua = p.evaluate("() => navigator.userAgent")
            wd = p.evaluate("() => String(navigator.webdriver)")
            signals["ua_no_headless"] = "Headless" not in str(ua)
            signals["webdriver_false"] = wd in ("undefined", "false")
            b.close()
        finally:
            release_seat()
    except Exception as e:  # noqa: BLE001 — harness must report, not crash
        signals["launch_error"] = str(e)[:200]
    ok = signals.get("ua_no_headless") and signals.get("webdriver_false")
    return {"ok": bool(ok), "signals": signals}


def ensure_fresh() -> dict:
    """Check version + quick signals; auto-update binary on decay signal."""
    before = cloak_version()
    quick = stealth_score_quick()
    updated = False
    if not quick["ok"]:
        try:
            subprocess.run(
                ["python", "-m", "cloakbrowser", "update"],
                capture_output=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
            updated = True
        except (OSError, subprocess.TimeoutExpired):
            pass
    after = cloak_version()
    s = _load_state()
    s["cloak_version"] = after
    s["scores"][time.strftime("%Y-%m-%d")] = quick
    _save_state(s)
    return {"before": before, "after": after, "quick": quick, "updated": updated}
