# -*- coding: utf-8 -*-
"""Spend firewall: every metered call logged, monthly cap enforced."""
from __future__ import annotations
import json
import time

from .config import SPEND_CAP_IDR, SPEND_LOG


def month_key() -> str:
    return time.strftime("%Y-%m")


def spent_this_month() -> float:
    total = 0.0
    try:
        for line in SPEND_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("month") == month_key():
                total += float(e.get("cost_idr", 0))
    except OSError:
        pass
    return total


def record(model: str, in_tokens: int, out_tokens: int,
           in_per_1k: float, out_per_1k: float) -> dict:
    cost = in_tokens / 1000 * in_per_1k + out_tokens / 1000 * out_per_1k
    entry = {"month": month_key(), "ts": time.time(), "model": model,
             "in": in_tokens, "out": out_tokens, "cost_idr": round(cost, 4)}
    with open(SPEND_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def allowed(extra_idr: float = 5.0) -> bool:
    """True if projected spend stays under cap."""
    return spent_this_month() + extra_idr <= SPEND_CAP_IDR
