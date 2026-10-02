# -*- coding: utf-8 -*-
"""Elixir router: wigolo -> obscura -> cloak(humanize) -> cua-driver. Read + act."""
from __future__ import annotations
import json
import os
import subprocess


def search(query: str, max_results: int = 5) -> dict:
    """Discovery via wigolo (local-first, $0). Falls back to error dict."""
    cmd = ["npx", "-y", "wigolo", "search", query, "--json", "--max-results", str(max_results)]
    try:
        import os

        use_shell = os.name == "nt"
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace", shell=use_shell,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                return {"raw": r.stdout[:4000]}
        return {"error": (r.stderr or r.stdout)[:1000]}
    except FileNotFoundError:
        return {"error": "wigolo not installed"}


def fetch(url: str, dump: str = "markdown") -> str:
    """Fast path via obscura; escalate to cloak on challenge."""
    import os

    exe = os.path.expanduser("~/.obscura/obscura.exe")
    if not os.path.exists(exe):
        exe = "obscura"
    try:
        r = subprocess.run(
            [exe, "fetch", url, "--dump", dump, "--timeout", "20"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        body = r.stdout.strip()
        if r.returncode == 0 and body and "challenge" not in body[:2000].lower():
            return body
        return _cloak_fetch(url)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _cloak_fetch(url)


def _cloak_fetch(url: str) -> str:
    from cloakbrowser import launch_persistent_context

    from .harness import PROFILES, acquire_seat, release_seat, seed_for

    acquire_seat()
    try:
        ctx = launch_persistent_context(
            str(PROFILES / "default"), humanize=True,
            args=[f"--fingerprint={seed_for('default')}"],
        )
        try:
            p = ctx.new_page()
            p.goto(url, wait_until="load", timeout=45000)
            p.wait_for_timeout(2500)
            text = p.evaluate("() => document.body ? document.body.innerText.slice(0,20000) : ''")
            return str(text)
        finally:
            ctx.close()
    finally:
        release_seat()


def act(url: str, screenshot: str | None = None, fill: dict | None = None) -> dict:
    """Human act: goto + optional fill + click + screenshot via cloak humanize."""
    from cloakbrowser import launch_persistent_context
    from urllib.parse import urlparse

    from .harness import PROFILES, acquire_seat, release_seat, rotate_seed, seed_for

    site = urlparse(url).netloc.replace(":", "_") or "default"
    acquire_seat()
    try:
        ctx = launch_persistent_context(
            str(PROFILES / site), humanize=True,
            args=[f"--fingerprint={seed_for(site)}"],
        )
        try:
            p = ctx.new_page()
            p.goto(url, wait_until="load", timeout=45000)
            p.wait_for_timeout(2000)
            if fill:
                for sel, val in fill.items():
                    p.locator(sel).fill(val)
                    p.wait_for_timeout(800)
            if screenshot:
                p.screenshot(path=screenshot, full_page=True)
            result = {"url": p.url, "title": p.title(), "screenshot": screenshot}
            # bot-wall signal -> rotate fingerprint next run, stay honest
            if "challenge" in p.title().lower() or "captcha" in p.title().lower():
                result["rotated_seed"] = rotate_seed(site)
            return result
        finally:
            ctx.close()
    finally:
        release_seat()
