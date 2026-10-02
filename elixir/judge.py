# -*- coding: utf-8 -*-
"""Elixir instant router via Needle: tiny on-device intent -> tool mapping.

Needle picks the tool + fills args in milliseconds (~140MB RAM), returns
calibrated confidence, and returns [] instead of guessing. Elixir uses it
to route natural-language requests to its own tiers without an LLM call.
Laya (System-1 calibrated choice/score/noul, 1.7GB ONNX/Node) stays optional
for decisions needing distributions rather than single picks.
"""
from __future__ import annotations

NEEDLE_TELEMETRY_ENV = "NEEDLE_TELEMETRY"


def decide(request: str) -> dict:
    import os

    os.environ.setdefault(NEEDLE_TELEMETRY_ENV, "0")
    try:
        import needle
    except ImportError:
        low = request.lower()
        import re

        urls = re.findall(r"https?://[^\s\"']+", request)
        if any(v in low for v in ("search", "find", "look up")):
            calls = [{"name": "web_search", "args": {"query": request}}]
        elif urls and any(v in low for v in ("click", "fill", "login", "act", "screenshot")):
            calls = [{"name": "stealth_act", "args": {"url": urls[0]}}]
        elif urls:
            calls = [{"name": "web_fetch", "args": {"url": urls[0]}}]
        else:
            calls = []
        return {"ok": True, "calls": calls, "confidence": 0.7 if calls else 0.0,
                "reasoning": "deterministic fallback; cactus-needle not installed"}

    @needle.tool
    def web_search(query: str):
        "Search the web for a query."
        return {"query": query}

    @needle.tool
    def web_fetch(url: str):
        "Fetch a page fast."
        return {"url": url}

    @needle.tool
    def stealth_act(url: str):
        "Act in stealth browser with human behavior."
        return {"url": url}

    @needle.tool
    def os_desktop(action: str):
        "Desktop OS action: screen, desktop, windows, click, type, hotkey."
        return {"action": action}

    @needle.tool
    def social_read(platform: str):
        "Read a social platform: youtube, bilibili, v2ex, rss, twitter, reddit, xiaohongshu."
        return {"platform": platform}

    @needle.tool
    def app_work(app: str):
        "Work in a desktop app: libreoffice, blender, obsidian, qgis."
        return {"app": app}

    @needle.tool
    def buddy_ask(question: str):
        "Ask the screen-seeing buddy a question."
        return {"question": question}

    agent = needle.Needle(
        tools=[web_search, web_fetch, stealth_act, os_desktop, social_read, app_work, buddy_ask]
    )
    out = agent.run(request)
    if isinstance(out, dict):
        calls = out.get("function_calls", [])
        return {
            "ok": True,
            "calls": [{"name": c.get("name"), "args": c.get("arguments")} for c in calls],
            "confidence": out.get("confidence"),
            "reasoning": str(out.get("reasoning", ""))[:200],
        }
    return {"ok": False, "raw": str(out)[:500]}
