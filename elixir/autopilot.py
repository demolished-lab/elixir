# -*- coding: utf-8 -*-
"""Elixir autopilot: overcome every failure mode itself, ask approval only.

Policy:
  AUTO (no ask): retries, tier escalation, seed rotation, cache reuse,
    E: mount, daemon start, free updates, screenshot evidence.
  ASK (your approval): credentials/logins, any spend (metered models, proxy,
    Pro seats), installs, account actions, anything irreversible.
"""
from __future__ import annotations

ASK_TIERS = {"login", "spend", "install", "account", "irreversible"}


def diagnose() -> list[dict]:
    """Run all probes, return fix plans for non-ok tiers."""
    from .probes import doctor_all

    plans = []
    for pr in doctor_all():
        if pr.status == "ok":
            continue
        plans.append(plan_for(pr.name, pr.status, pr.message))
    return plans


def plan_for(tier: str, status: str, message: str) -> dict:
    if tier == "cua" and status in ("warn", "off"):
        return {"tier": tier, "fix": "start cua-driver daemon",
                "mode": "auto", "run": "daemon_cua"}
    if tier == "cloak" and status != "ok":
        # policy: installs/updates touch installed code -> always ask
        return {"tier": tier, "fix": "cloakbrowser update (free, changes installed code)",
                "mode": "ask", "kind": "install", "run": "update_cloak",
                "ask_text": "Update cloakbrowser (free, modifies installed code)? [y/N]"}
    if tier == "agent-reach":
        return {"tier": tier, "fix": "login-walled platforms need your cookies",
                "mode": "ask", "kind": "login",
                "ask_text": "Paste Cookie-Editor export or confirm headed login? (small account)"}
    if tier == "judge" and status == "off":
        return {"tier": tier, "fix": "pip install cactus-needle",
                "mode": "ask", "kind": "install", "run": "install_judge",
                "ask_text": "Install cactus-needle (~100KB wheel)? [y/N]"}
    if tier == "apps" and status == "off":
        return {"tier": tier, "fix": "pip install cli-anything-hub",
                "mode": "ask", "kind": "install", "run": "install_apps",
                "ask_text": "Install cli-anything-hub? [y/N]"}
    if tier in ("wigolo", "obscura") and status == "off":
        return {"tier": tier, "fix": f"reinstall {tier}",
                "mode": "ask", "kind": "install",
                "ask_text": f"Reinstall {tier}? [y/N]"}
    return {"tier": tier, "fix": f"manual: {message[:120]}",
            "mode": "ask", "kind": "irreversible",
            "ask_text": f"Tier {tier} needs attention: {message[:120]}. Proceed manually? [y/N]"}


# install/update actions the user may approve. Key = plan["run"].
_INSTALLS = {"install_judge": "cactus-needle", "install_apps": "cli-anything-hub"}


def run_auto(key: str) -> dict:
    import subprocess

    if key == "daemon_cua":
        try:
            subprocess.Popen(
                ["cua-driver", "serve", "--socket", r"\\.\pipe\cua-driver"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"ok": True, "did": "cua daemon started"}
        except FileNotFoundError:
            return {"ok": False, "error": "cua-driver missing"}
    if key == "update_cloak":
        try:
            r = subprocess.run(
                ["python", "-m", "cloakbrowser", "update"],
                capture_output=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
            return {"ok": r.returncode == 0, "did": "cloak update attempted"}
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"ok": False, "error": str(e)[:160]}
    if key in _INSTALLS:
        pkg = _INSTALLS[key]
        try:
            r = subprocess.run(
                ["python", "-m", "pip", "install", "--no-input", pkg],
                capture_output=True, timeout=600,
                encoding="utf-8", errors="replace",
            )
            ok = r.returncode == 0
            return {"ok": ok, "did": f"pip install {pkg}",
                    **({} if ok else {"error": (r.stderr or r.stdout)[-400:]})}
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"ok": False, "error": str(e)[:160]}
    return {"ok": False, "error": f"unknown auto fix {key}"}


def autopilot(ask_fn=None) -> dict:
    """Diagnose -> auto-fix safe items -> ask approval for the rest -> verify."""
    if ask_fn is None:
        def ask_fn(text: str) -> bool:
            try:
                return input(f"APPROVE: {text} ").strip().lower().startswith("y")
            except (EOFError, KeyboardInterrupt):
                return False

    log: list[dict] = []
    for plan in diagnose():
        if plan["mode"] == "auto":
            log.append({**plan, **run_auto(plan["run"])})
            continue
        if not ask_fn(plan.get("ask_text", f"Approve {plan['fix']}?")):
            log.append({**plan, "approved": False, "note": "skipped by you"})
            continue
        # an approval must actually do the thing, or it is theatre
        if plan.get("run"):
            log.append({**plan, "approved": True, **run_auto(plan["run"])})
        else:
            log.append({**plan, "approved": True,
                        "note": f"approved — run manually: {plan['fix']}"})
    from .probes import doctor_all

    verify = {pr.name: pr.status for pr in doctor_all()}
    return {"actions": log, "verify": verify}
