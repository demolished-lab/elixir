# -*- coding: utf-8 -*-
"""Elixir social tier via agent-reach: 16-platform health + routing.

agent-reach has no read/search commands by design — it is installer +
doctor + skill playbooks; execution is upstream tools. Elixir uses its
doctor as ground truth for social reachability and executes login-walled
platforms through cloak persistent profiles.
"""
from __future__ import annotations


def status() -> dict:
    from agent_reach.config import Config
    from agent_reach.doctor import check_all

    try:
        results = check_all(Config())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300]}
    out = {}
    for name, r in results.items():
        out[name] = {
            "status": r["status"],
            "message": r["message"][:200],
            "backend": r.get("active_backend"),
        }
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    return {"ok": True, "score": f"{ok}/{len(results)}", "channels": out}


def route(platform: str) -> dict:
    """How elixir serves one social platform today."""
    s = status()
    if not s.get("ok"):
        return s
    ch = s["channels"].get(platform)
    if not ch:
        return {"ok": False, "error": f"unknown platform {platform}"}
    if ch["status"] == "ok":
        return {"ok": True, "via": ch["backend"] or "agent-reach upstream",
                "note": ch["message"]}
    return {"ok": False, "platform": platform, "agent_reach": ch["message"][:200],
            "elixir_fallback": f"cloak persistent profile ./profiles/{platform} + humanize",
            "unlock": f"agent-reach configure {platform}-cookies (Cookie-Editor export, small account)"}
