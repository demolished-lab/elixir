# -*- coding: utf-8 -*-
"""Elixir config: env-first, secrets never in code.

Env vars (all optional, sane defaults):
  ELIXIR_DATA_DIR        profiles/state/screenshots root (default: package root)
                         HTTP-served artifacts live in <DATA_DIR>/artifacts only
  ELIXIR_BYNARA_KEY_FILE path to file holding the cloud-eye API key (required
                         for cloud fallback; unset = cloud tiers disabled)
  ELIXIR_OLLAMA_URL      default http://localhost:11434
  ELIXIR_TEXT_MODEL      default qwen3:4b-instruct-2507-q4_K_M
  ELIXIR_VISION_MODEL    default qwen2.5vl:3b
  ELIXIR_CLOUD_VISION    default agnes-2.5-flash
  ELIXIR_MAX_TOKENS      default 150 (applies to local *and* cloud generation)
  ELIXIR_OLLAMA_KEEP_ALIVE  how long a local model stays resident after a call,
                         default 15m. A cold reload costs minutes on a CPU-only
                         box, so resident == fast.
  ELIXIR_SEAT_TIMEOUT    default 120
  ELIXIR_SPEND_CAP_IDR   monthly cloud-eye cap, default 50000 (~pennies)
  ELIXIR_LOG_LEVEL       default INFO
A local `.env` (KEY=VALUE lines) in the data dir is loaded if present.
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    for base in (Path.cwd(), ROOT):
        f = base / ".env"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_dotenv()

DATA_DIR = Path(os.getenv("ELIXIR_DATA_DIR", str(ROOT)))
PROFILES_DIR = DATA_DIR / "profiles"
STATE_FILE = DATA_DIR / ".elixir_state.json"
SEAT_LOCK = DATA_DIR / ".cloak_seat.lock"
SPEND_LOG = DATA_DIR / ".elixir_spend.jsonl"

# The only directory the Studio HTTP server is allowed to read from.
# Kept separate from DATA_DIR so `.env`, state files and profile cookies
# can never be served by `/file` or `/shot`.
ARTIFACTS_DIR = DATA_DIR / "artifacts"

# Names never served over HTTP even if they sit inside ARTIFACTS_DIR.
DENIED_SUFFIXES = (".env", ".lock", ".db", ".jsonl", ".key", ".pem")

# No default on purpose: the key lives outside the repo, path comes from env.
BYNARA_KEY_FILE = os.getenv("ELIXIR_BYNARA_KEY_FILE", "")
OLLAMA_URL = os.getenv("ELIXIR_OLLAMA_URL", "http://localhost:11434")
TEXT_MODEL = os.getenv("ELIXIR_TEXT_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
VISION_MODEL = os.getenv("ELIXIR_VISION_MODEL", "qwen2.5vl:3b")
CLOUD_VISION_MODEL = os.getenv("ELIXIR_CLOUD_VISION", "agnes-2.5-flash")
MAX_TOKENS = int(os.getenv("ELIXIR_MAX_TOKENS", "150"))
OLLAMA_KEEP_ALIVE = os.getenv("ELIXIR_OLLAMA_KEEP_ALIVE", "15m")
SEAT_TIMEOUT = int(os.getenv("ELIXIR_SEAT_TIMEOUT", "120"))
SPEND_CAP_IDR = float(os.getenv("ELIXIR_SPEND_CAP_IDR", "50000"))
LOG_LEVEL = os.getenv("ELIXIR_LOG_LEVEL", "INFO")

# Pinned upstream versions — update deliberately, not by surprise.
PINS = {
    "wigolo": "0.2.1",
    "obscura": "0.2.2",
    "cloakbrowser": "0.5.11",
    "cua-driver": "0.32.0",
    "agent-reach": "1.5.0",
    "cli-anything-hub": "0.4.1",
    "cactus-needle": "3.0.6",
}
