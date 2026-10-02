# -*- coding: utf-8 -*-
"""Elixir episodic memory: every run logged, every site learns.

SQLite at <data>/.elixir_memory.db:
  runs  — task, step, tier, ok, latency_ms, confidence, ts
  sites — site, backend, wins, total (success-rate driven arbitration)
"""
from __future__ import annotations
import sqlite3
import time

from .config import DATA_DIR

DB = DATA_DIR / ".elixir_memory.db"


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS runs
        (ts REAL, task TEXT, step TEXT, tier TEXT, ok INTEGER,
         latency_ms INTEGER, confidence REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS sites
        (site TEXT, backend TEXT, wins INTEGER, total INTEGER,
         PRIMARY KEY (site, backend))""")
    return con


def log_run(task: str, step: str, tier: str, ok: bool,
            latency_ms: int, confidence: float | None = None) -> None:
    con = _db()
    con.execute(
        "INSERT INTO runs (ts, task, step, tier, ok, latency_ms, confidence)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), task, step, tier, int(ok), latency_ms, confidence))
    con.commit()
    con.close()


def log_site(site: str, backend: str, ok: bool) -> None:
    con = _db()
    row = con.execute("SELECT wins, total FROM sites WHERE site=? AND backend=?",
                      (site, backend)).fetchone()
    wins, total = row or (0, 0)
    con.execute("REPLACE INTO sites VALUES (?,?,?,?)",
                (site, backend, wins + int(ok), total + 1))
    con.commit()
    con.close()


def best_backend(site: str, candidates: list[str]) -> str:
    """Learned preference: highest win-rate with >=2 samples, else first."""
    con = _db()
    scored = []
    for b in candidates:
        row = con.execute("SELECT wins, total FROM sites WHERE site=? AND backend=?",
                          (site, b)).fetchone()
        wins, total = row or (0, 0)
        rate = wins / total if total >= 2 else -1.0
        scored.append((rate, b))
    con.close()
    scored.sort(reverse=True)
    return scored[0][1]


def stats(site: str | None = None) -> dict:
    con = _db()
    if site:
        rows = con.execute("SELECT backend, wins, total FROM sites WHERE site=?",
                           (site,)).fetchall()
    else:
        rows = con.execute(
            "SELECT site||'/'||backend, wins, total FROM sites").fetchall()
    con.close()
    return {k: {"wins": w, "total": t, "rate": round(w / t, 3) if t else None}
            for k, w, t in rows}
