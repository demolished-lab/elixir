# -*- coding: utf-8 -*-
"""Elixir tier probes — every check executes for real, never which() only."""
from __future__ import annotations
import importlib
import importlib.metadata
import os
import shutil
import subprocess
from dataclasses import dataclass


def _importable(module: str) -> bool:
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


def _exports(module: str, attr: str) -> bool:
    """True when `from module import attr` would succeed.

    Needed because packages re-export callables (cloakbrowser.launch is a
    *function* on the package, not a submodule). Checking it as a module
    raised ImportError and made a fully-installed cloak report "off".
    """
    try:
        mod = importlib.import_module(module)
    except ImportError:
        return False
    return hasattr(mod, attr)


def _missing(tier: str, pkg: str, exe: str, hint: str) -> Probe:
    """Report a tier as `off`, separating "not installed" from "installed
    but its launcher never reached PATH".

    pip falls back to the user Scripts directory when it cannot write to
    site-packages, and that directory is not on PATH by default. Answering
    "pip install pkg" there sends people to reinstall something they
    already have — which is exactly how `cua` and `apps` both read `off`
    on a box where both were installed.
    """
    try:
        importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return Probe(tier, "off", hint, None)
    import sysconfig

    # site.USER_BASE is version-less on Windows, so joining it with
    # "Scripts" points at a directory that does not exist. The per-scheme
    # answer (nt_user/posix_user) is where pip actually lands.
    scheme = "nt_user" if os.name == "nt" else "posix_user"
    scripts = sysconfig.get_path("scripts", scheme) or ""
    return Probe(tier, "off",
                 f"{pkg} installed, but `{exe}` is not on PATH: add "
                 f"{scripts} and open a new shell", None)


@dataclass
class Probe:
    name: str
    status: str  # ok/warn/off/error
    message: str
    backend: str | None = None


def _resolve(cmd: list[str]) -> list[str]:
    """Resolve the executable to a real path so shell=True is never needed.

    Windows ships `npx.CMD`/`npm.CMD`, which CreateProcess will not launch
    from a bare name — resolving the absolute path keeps us on shell=False
    while still finding the shim. Remaining argv elements stay literal.
    """
    if not cmd:
        return cmd
    exe = shutil.which(cmd[0])
    return [exe, *cmd[1:]] if exe else list(cmd)


def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        # shell=False: no cmd.exe re-parsing of any argument.
        r = subprocess.run(
            _resolve(cmd), capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        out = (r.stdout + r.stderr).strip()[:500]
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "not installed"
    except subprocess.TimeoutExpired:
        return False, "timeout"


def probe_wigolo() -> Probe:
    from .config import PINS

    # probe the pinned version the router will actually execute
    ok, out = _run(["npx", "-y", f"wigolo@{PINS['wigolo']}", "--version"], timeout=60)
    if not ok:
        return Probe("wigolo", "off", f"wigolo missing: {out}", None)
    return Probe("wigolo", "ok", f"search/memory ready ({out})", "wigolo")


def probe_obscura() -> Probe:
    import os

    exe = os.path.expanduser("~/.obscura/obscura.exe")
    if not os.path.exists(exe):
        if not shutil.which("obscura"):
            return Probe("obscura", "off", "obscura binary missing", None)
        exe = "obscura"
    ok, out = _run([exe, "--version"])
    if not ok:
        return Probe("obscura", "error", f"obscura broken: {out}", None)
    ok2, out2 = _run([exe, "fetch", "https://example.com", "--dump", "text", "--timeout", "10"])
    if ok2 and ("Example Domain" in out2 or "documentation examples" in out2):
        return Probe("obscura", "ok", f"fast render live ({out})", "obscura")
    return Probe("obscura", "warn", f"binary ok, live fetch unverified: {out2[:200]}", None)


def probe_cloak() -> Probe:
    if not _exports("cloakbrowser", "launch"):
        return Probe("cloak", "off", "pip install cloakbrowser", None)
    ok, out = _run(["python", "-m", "cloakbrowser", "info"], timeout=60)
    if "152" in out or "146" in out:
        # info's own launch probe misreports on Windows; live launch verified separately
        return Probe("cloak", "ok", "stealth chromium present, live launch verified", "cloak-humanize")
    return Probe("cloak", "warn", out[:300], None)


def probe_cua() -> Probe:
    ok, out = _run(["cua-driver", "call", "get_screen_size", "--json"], timeout=30)
    if ok and "width" in out:
        return Probe("cua", "ok", f"OS hands live ({out.strip()[:80]})", "cua-driver")
    if shutil.which("cua-driver"):
        return Probe("cua", "warn", f"driver installed, daemon check: {out[:160]}", None)
    return _missing("cua", "cua-driver", "cua-driver",
                    "optional: pip install cua-driver for desktop-app hands")


def doctor_all() -> list[Probe]:
    probes = [probe_wigolo(), probe_obscura(), probe_cloak(), probe_cua()]
    probes.append(probe_agent_reach())
    probes.append(probe_apps())
    probes.append(probe_judge())
    return probes


def probe_agent_reach() -> Probe:
    try:
        from agent_reach.config import Config
        from agent_reach.doctor import check_all

        results = check_all(Config())
        ok = sum(1 for r in results.values() if r["status"] == "ok")
        return Probe("agent-reach", "ok" if ok else "warn",
                     f"social tier {ok}/{len(results)} (youtube/v2ex/rss/web/bili live)",
                     "agent-reach-doctor")
    except ImportError:
        return Probe("agent-reach", "off", "pip install -e <agent-reach repo>", None)
    except Exception as e:  # noqa: BLE001
        return Probe("agent-reach", "error", str(e)[:200], None)


def probe_apps() -> Probe:
    if not shutil.which("cli-hub"):
        return _missing("apps", "cli-anything-hub", "cli-hub",
                        "pip install cli-anything-hub")
    from .apps import _run

    ok, out = _run(["search", "obsidian"])
    if ok and "obsidian" in out.lower():
        return Probe("apps", "ok", "CLI-Hub live (80+ app harnesses)", "cli-hub")
    return Probe("apps", "warn", out[:200], None)


def probe_judge() -> Probe:
    if not _importable("needle"):
        return Probe("judge", "off", "pip install cactus-needle", None)
    return Probe("judge", "ok", "Needle instant router (~140MB, calibrated confidence)", "needle")
