# -*- coding: utf-8 -*-
"""Elixir router: wigolo -> obscura -> cloak(humanize) -> cua-driver. Read + act."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from urllib.parse import urlparse

from .config import PINS

_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal",
                  "metadata.googlesource.com"}


def npx_argv(package: str, *args: str) -> list[str] | None:
    """Resolve npx to its real path so shell=True is never needed.

    Windows ships `npx.CMD`, and CreateProcess cannot launch a .cmd
    directly — that is the usual reason people reach for shell=True.
    Resolving the absolute path lets us stay on shell=False, so a query
    containing `&`, `|`, `>` or `%` reaches wigolo as one literal argv
    element instead of being re-parsed by cmd.exe as a command separator.
    """
    exe = shutil.which("npx")
    if not exe:
        return None
    return [exe, "-y", package, *args]


def search_argv(query: str, max_results: int = 5) -> list[str] | None:
    """Build the wigolo argv as a plain list. Kept separate so the
    injection guarantee is directly unit-testable."""
    return npx_argv(f"wigolo@{PINS['wigolo']}", "search", query,
                    "--json", "--max-results", str(max_results))


def validate_url(url: str) -> str | None:
    """http/https only, never cloud-metadata endpoints.

    Returns an error string when the URL must be refused, else None.
    Loopback/private hosts stay reachable on purpose — this is a
    single-user local tool and fetching your own services is a feature.
    """
    try:
        p = urlparse(url)
    except ValueError as e:
        return f"malformed url: {e}"
    if p.scheme not in ("http", "https"):
        return f"refusing scheme '{p.scheme or '(none)'}': http/https only"
    host = (p.hostname or "").lower()
    if host in _BLOCKED_HOSTS:
        return "refusing cloud metadata endpoint"
    return None


def search(query: str, max_results: int = 5) -> dict:
    """Discovery via wigolo (local-first, $0). Falls back to error dict."""
    cmd = search_argv(query, max_results)
    if not cmd:
        return {"error": "npx not installed (install Node.js to enable search)"}
    try:
        # shell=False: the query is never handed to cmd.exe.
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                return {"raw": r.stdout[:4000]}
        return {"error": (r.stderr or r.stdout)[:1000]}
    except FileNotFoundError:
        return {"error": "wigolo not installed"}
    except subprocess.TimeoutExpired:
        return {"error": "wigolo search timed out after 120s"}


def fetch(url: str, dump: str = "markdown") -> str:
    """Fast path via obscura; escalate to cloak on challenge."""
    bad = validate_url(url)
    if bad:
        return f"[elixir] {bad}"

    exe = os.path.expanduser("~/.obscura/obscura.exe")
    if not os.path.exists(exe):
        exe = shutil.which("obscura") or "obscura"
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


def _plain_fetch(url: str) -> str:
    """Last-resort read-only fetch for boxes without optional browser tiers."""
    from urllib.request import Request, urlopen

    bad = validate_url(url)
    if bad:
        return f"[elixir] {bad}"
    req = Request(url, headers={"User-Agent": "elixir/0.1 (+read-only fallback)"})
    with urlopen(req, timeout=20) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def fetch_and_save(url: str, out_dir: str | os.PathLike | None = None) -> dict:
    """Fetch + persist markdown artifact. Returns path, not just text.

    Artifacts default to the HTTP-served artifacts directory so the
    Studio `/file` route can serve them without exposing DATA_DIR.
    """
    from urllib.parse import urlparse

    from .config import ARTIFACTS_DIR

    if out_dir is None:
        out_dir = ARTIFACTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    body = fetch(url)
    name = (urlparse(url).netloc or "page").replace(":", "_")
    path = os.path.abspath(os.path.join(str(out_dir), f"{name}.md"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {url}\n\n{body}")
    return {"path": path, "chars": len(body)}


def act_pdf(url: str, out_path: str) -> dict:
    """Full-page PDF artifact via stealth browser (print-to-PDF, real file)."""
    bad = validate_url(url)
    if bad:
        return {"ok": False, "url": url, "error": bad}
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError:
        return {"ok": False, "url": url,
                "error": "cloakbrowser unavailable; PDF capture skipped"}

    from .harness import PROFILES, acquire_seat, release_seat, seed_for
    from urllib.parse import urlparse

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    site = urlparse(url).netloc.replace(":", "_") or "default"
    acquire_seat()
    try:
        ctx = launch_persistent_context(
            str(PROFILES / site), humanize=True,
            args=[f"--fingerprint={seed_for(site)}"])
        try:
            p = ctx.new_page()
            p.goto(url, wait_until="load", timeout=45000)
            p.wait_for_timeout(2000)
            p.pdf(path=out_path)
            return {"ok": True, "path": out_path, "title": p.title()}
        finally:
            ctx.close()
    except Exception as e:  # noqa: BLE001 — report, never crash the run
        return {"ok": False, "url": url, "error": str(e)[:300]}
    finally:
        release_seat()


def _cloak_fetch(url: str) -> str:
    bad = validate_url(url)
    if bad:
        return f"[elixir] {bad}"
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError:
        return _plain_fetch(url)

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
    bad = validate_url(url)
    if bad:
        return {"ok": False, "url": url, "error": bad}
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError:
        return {"ok": False, "url": url,
                "error": "cloakbrowser unavailable; install it for humanized act/fill/screenshot"}
    from urllib.parse import urlparse

    from .harness import PROFILES, acquire_seat, release_seat, rotate_seed, seed_for

    site = urlparse(url).netloc.replace(":", "_") or "default"
    if screenshot:
        os.makedirs(os.path.dirname(os.path.abspath(screenshot)) or ".", exist_ok=True)
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
            frames = []
            if screenshot and screenshot.endswith("_3.png"):
                import time as _t

                base = screenshot[:-6]  # ui_<rid> from ui_<rid>_3.png
                for k in (1, 2):
                    p.wait_for_timeout(1200)
                    fp = f"{base}_{k}.png"
                    p.screenshot(path=fp)
                    frames.append(fp)
                _t.sleep(0)
            if fill:
                for sel, val in fill.items():
                    p.locator(sel).fill(val)
                    p.wait_for_timeout(800)
            if screenshot:
                p.screenshot(path=screenshot, full_page=True)
                frames.append(screenshot)
            result = {"url": p.url, "title": p.title(), "screenshot": screenshot,
                      "frames": frames}
            # bot-wall signal -> rotate fingerprint next run, stay honest
            if "challenge" in p.title().lower() or "captcha" in p.title().lower():
                result["rotated_seed"] = rotate_seed(site)
            return result
        finally:
            ctx.close()
    finally:
        release_seat()
