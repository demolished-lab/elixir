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
        return {"tier": tier, "fix": "cloakbrowser update (free)",
                "mode": "auto", "run": "update_cloak"}
    if tier == "agent-reach":
        return {"tier": tier, "fix": "login-walled platforms need your cookies",
                "mode": "ask", "kind": "login",
                "ask_text": "Paste Cookie-Editor export or confirm headed login? (small account)"}
    if tier == "judge" and status == "off":
        return {"tier": tier, "fix": "pip install cactus-needle",
                "mode": "ask", "kind": "install",
                "ask_text": "Install cactus-needle (~100KB wheel)? [y/N]"}
    if tier == "apps" and status == "off":
        return {"tier": tier, "fix": "pip install cli-anything-hub",
                "mode": "ask", "kind": "install",
                "ask_text": "Install cli-anything-hub? [y/N]"}
    if tier in ("wigolo", "obscura") and status == "off":
        return {"tier": tier, "fix": f"reinstall {tier}",
                "mode": "ask", "kind": "install",
                "ask_text": f"Reinstall {tier}? [y/N]"}
    return {"tier": tier, "fix": f"manual: {message[:120]}",
            "mode": "ask", "kind": "irreversible",
            "ask_text": f"Tier {tier} needs attention: {message[:120]}. Proceed manually? [y/N]"}


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
    if key == "mount_e":
        try:
            r = subprocess.run(
                ["schtasks", "/Run", "/TN", "VyuhaMountVHD"],
                capture_output=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            return {"ok": True, "did": "E: mount requested"}
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
            result = run_auto(plan["run"])
            log.append({**plan, **result})
        else:
            if ask_fn(plan.get("ask_text", f"Approve {plan['fix']}?")):
                log.append({**plan, "approved": True, "note": "run it now or say the word"})
            else:
                log.append({**plan, "approved": False, "note": "skipped by you"})
    from .probes import doctor_all

    verify = {pr.name: pr.status for pr in doctor_all()}
    return {"actions": log, "verify": verify}
