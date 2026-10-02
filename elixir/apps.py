# -*- coding: utf-8 -*-
"""Elixir app tier via CLI-Anything Hub: every desktop app agent-native.

Web tiers read the internet; this tier produces artifacts (docs, 3D, GIS,
notes, diagrams) through per-app CLI harnesses. Delegates to `cli-hub`.
"""
from __future__ import annotations
import os
import subprocess

ENV = {**os.environ, "PYTHONUTF8": "1"}


def _run(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["cli-hub"] + args, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=ENV,
        )
        return r.returncode == 0, (r.stdout or r.stderr)[:3000]
    except FileNotFoundError:
        return False, "cli-hub not installed (pip install cli-anything-hub)"
    except subprocess.TimeoutExpired:
        return False, "cli-hub timeout"


def search(text: str) -> str:
    ok, out = _run(["search", text])
    return out


def info(name: str) -> str:
    ok, out = _run(["info", name])
    return out


def install(name: str) -> str:
    ok, out = _run(["install", name], timeout=300)
    return out


def launch(name: str, args: list[str]) -> str:
    ok, out = _run(["launch", name] + args, timeout=300)
    return out
