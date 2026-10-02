# -*- coding: utf-8 -*-
"""Elixir OS hands via cua-driver: exact-human desktop control, AI speed.

Intelligence rule: deterministic grounding first (UIA tree / window bounds),
no model call for atomic moves. Model only grounds novel targets from a
screenshot; execution stays native-speed.
Speed rule: browser work stays in cloak/obscura (parallel); OS hands only
for what the browser cannot do (desktop apps, file dialogs, 2FA, DRM).
"""
from __future__ import annotations
import json
import subprocess


def _call(tool: str, args: dict | None = None) -> dict:
    cmd = ["cua-driver", "call", tool]
    if args:
        cmd += ["--args-json", json.dumps(args)]
    cmd += ["--json"]
    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return {"ok": False, "error": "cua-driver not installed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{tool} timeout"}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[:500]}
    try:
        return {"ok": True, "data": json.loads(r.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "raw": r.stdout[:2000]}


def screen() -> dict:
    return _call("get_screen_size")


def desktop(out: str = "desktop.png", max_dim: int = 0) -> dict:
    """Full screenshot to file — coordinate source for desktop actions."""
    return _call("get_desktop_state", {"screenshot_out_file": out,
                                       "max_image_dimension": max_dim})


def windows() -> dict:
    return _call("list_windows")


def window_tree(pid: int) -> dict:
    """UIA tree: structured elements + bounds for deterministic grounding."""
    return _call("get_window_state", {"pid": pid})


def click_desktop(x: int, y: int) -> dict:
    return _call("click", {"target": {"kind": "desktop", "display_id": "primary"},
                           "position": {"x": x, "y": y}})


def type_text(text: str) -> dict:
    return _call("type", {"text": text})


def hotkey(*keys: str) -> dict:
    return _call("hotkey", {"keys": list(keys)})


def launch_app(name: str) -> dict:
    """Hidden launch (SW_SHOWNOACTIVATE) — never steals focus."""
    return _call("launch_app", {"name": name})


def to_front(pid: int) -> dict:
    return _call("bring_to_front", {"pid": pid})
