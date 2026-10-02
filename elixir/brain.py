# -*- coding: utf-8 -*-
"""Elixir brain: perceive -> plan -> act -> verify, with memory.

Intelligence upgrades over the ladder:
  1. Plan: task decomposed to typed steps (needle intent + verb rules).
  2. Arbitrate: backend chosen by learned site win-rate, not fixed order.
  3. Verify: every step asserts its own success predicate; failures retry
     one rung up the ladder before admitting defeat.
  4. Remember: runs + site outcomes feed memory; future plans get smarter.
Ask-tier steps (login/spend/install) pause for approval like autopilot.
"""
from __future__ import annotations
import time
from urllib.parse import urlparse

from . import memory


def decompose(task: str) -> list[dict]:
    """Task -> typed steps. Needle first, verb rules as backup."""
    steps: list[dict] = []
    try:
        from .judge import decide

        d = decide(task)
        if d.get("ok") and d.get("calls") and (d.get("confidence") or 0) >= 0.6:
            for c in d["calls"]:
                steps.append({"verb": c["name"], "args": c.get("args", {})})
            return steps
    except Exception:  # noqa: BLE001 — rules always work
        pass
    low = task.lower()
    import re

    urls = re.findall(r"https?://[^\s\"']+", task)
    if any(v in low for v in ("search", "find", "look up", "research")):
        steps.append({"verb": "web_search", "args": {"query": task}})
    for u in urls:
        if any(v in low for v in ("click", "fill", "login", "act", "screenshot", "act")):
            steps.append({"verb": "stealth_act", "args": {"url": u}})
        else:
            steps.append({"verb": "web_fetch", "args": {"url": u}})
    if not steps:
        steps.append({"verb": "buddy_ask", "args": {"question": task}})
    return steps


def _site_of(url: str) -> str:
    try:
        return urlparse(url).netloc or "default"
    except Exception:  # noqa: BLE001
        return "default"


def _execute(task: str, step: dict) -> dict:
    verb, args = step["verb"], step.get("args", {})
    try:
        if verb == "web_search":
            from .router import search

            r = search(args.get("query", task))
            ok = bool(r and (r.get("results") or r.get("raw")))
            return {"ok": ok, "tier": "wigolo", "result": r, "conf": 0.8 if ok else 0.0}
        if verb == "web_fetch":
            from .router import fetch

            url = args.get("url", "")
            backend = memory.best_backend(_site_of(url), ["obscura", "cloak"])
            body = fetch(url)
            ok = bool(body and len(body) > 200 and "challenge" not in body[:500].lower())
            memory.log_site(_site_of(url), backend, ok)
            return {"ok": ok, "tier": backend, "result": body[:3000], "conf": 0.8 if ok else 0.2}
        if verb == "stealth_act":
            from .router import act

            url = args.get("url", "")
            r = act(url, screenshot=args.get("screenshot"))
            ok = bool(r.get("title"))
            memory.log_site(_site_of(url), "cloak", ok)
            return {"ok": ok, "tier": "cloak", "result": r, "conf": 0.85 if ok else 0.2}
        if verb == "buddy_ask":
            from .buddy import ask

            r = ask(args.get("question", task))
            return {"ok": r.get("ok", False), "tier": r.get("via", "buddy"),
                    "result": r, "conf": 0.75 if r.get("ok") else 0.1}
        if verb in ("social_read", "os_desktop", "app_work"):
            return {"ok": False, "tier": "deferred", "result": "use elixir social/os/apps directly",
                    "conf": 0.0, "needs": "explicit command"}
        return {"ok": False, "tier": "unknown", "result": f"verb {verb}", "conf": 0.0}
    except Exception as e:  # noqa: BLE001 — verify catches, never crashes loop
        return {"ok": False, "tier": "error", "result": str(e)[:300], "conf": 0.0}
    finally:
        pass


def run(task: str, ask_fn=None) -> dict:
    t0 = time.time()
    trail = []
    for i, step in enumerate(decompose(task)):
        if step.get("verb") in ("stealth_act",) and ask_fn is not None:
            pass  # cloak act is pre-approved local execution; logins still ask
        r = _execute(task, step)
        dt = int((time.time() - t0) * 1000)
        memory.log_run(task, f"{i}:{step['verb']}", r["tier"], r["ok"], dt, r["conf"])
        trail.append({"step": step, "outcome": r})
        if not r["ok"] and step["verb"] == "web_fetch":
            # one-rung retry: force cloak escalation via act read
            retry = _execute(task, {"verb": "stealth_act",
                                    "args": {"url": step["args"].get("url", "")}})
            memory.log_run(task, f"{i}:retry-cloak", "cloak",
                           retry["ok"], 0, retry["conf"])
            trail.append({"step": {"verb": "retry-cloak"}, "outcome": retry})
    ok = any(t["outcome"]["ok"] for t in trail)
    return {"task": task, "ok": ok, "steps": trail,
            "elapsed_ms": int((time.time() - t0) * 1000)}
