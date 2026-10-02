# -*- coding: utf-8 -*-
"""Elixir trajectory evidence: per-run before/after screenshots + action log,
optional full-session mp4. Programmable via cua-driver — no manual editor.

Recordly (human video editor, Electron GUI, no headless API) stays a manual
tool for polished demos; this module is the machine path: every `elixir run
--record` leaves turn folders + optional mp4 under runs/<task>/.
"""
from __future__ import annotations
import json
import subprocess
import time

from .config import DATA_DIR

RUNS_DIR = DATA_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)
_LOCAL_STATE: dict = {"recording": False, "backend": None}


def _call(tool: str, args: dict | None = None, timeout: int = 60) -> dict:
    cmd = ["cua-driver", "call", tool]
    if args:
        cmd += ["--args-json", json.dumps(args)]
    cmd += ["--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {"ok": False, "error": "cua-driver missing"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{tool} timeout"}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[:300]}
    try:
        return {"ok": True, "data": json.loads(r.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "raw": r.stdout[:500]}


def ensure_ffmpeg() -> dict:
    return _call("install_ffmpeg", {})


def start(label: str, video: bool = False) -> dict:
    global _LOCAL_STATE
    out = RUNS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{label}"
    out.mkdir(parents=True, exist_ok=True)
    r = _call("start_recording", {"output_dir": str(out),
                                  "record_video": video})
    if not r.get("ok"):
        metadata = {"label": label, "video": video, "backend": "local-metadata",
                    "started_at": time.time(), "note": r.get("error", "OS recorder unavailable")}
        (out / "run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        _LOCAL_STATE = {"recording": True, "backend": "local-metadata", "dir": str(out)}
        return {"ok": True, "dir": str(out), "detail": {"ok": True, "data": metadata}}
    _LOCAL_STATE = {"recording": True, "backend": "cua-driver", "dir": str(out)}
    return {"ok": True, "dir": str(out), "detail": r}


def stop() -> dict:
    r = _call("stop_recording", {})
    if not r.get("ok") and _LOCAL_STATE.get("backend") == "local-metadata":
        _LOCAL_STATE["recording"] = False
        return {"ok": True, "data": {"backend": "local-metadata", "dir": _LOCAL_STATE.get("dir")}}
    _LOCAL_STATE["recording"] = False
    return r


def state() -> dict:
    r = _call("get_recording_state", {})
    return r if r.get("ok") else {"ok": True, "data": _LOCAL_STATE.copy()}
