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
    import needle

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
