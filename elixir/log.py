# -*- coding: utf-8 -*-
"""Structured JSON-lines logging (stdlib only). Secrets are never logged."""
from __future__ import annotations
import json
import logging
import sys

from .config import LOG_LEVEL

_SECRET_HINTS = ("api_key", "x-api-key", "token", "secret", "sk-nry")


def scrub(obj):
    if isinstance(obj, dict):
        return {k: ("***" if any(h in k.lower() for h in _SECRET_HINTS) else scrub(v))
                for k, v in obj.items()}
    if isinstance(obj, str):
        for h in ("sk-nry-", "cb_"):
            if h in obj:
                return "***key***"
        return obj
    return obj


class JsonHandler(logging.Handler):
    def emit(self, record):
        try:
            payload = {"level": record.levelname, "msg": record.getMessage(),
                       "mod": record.module}
            if record.args and isinstance(record.args, dict):
                payload.update(scrub(record.args))
            sys.stderr.write(json.dumps(payload) + "\n")
        except Exception:  # noqa: BLE001 — logging must never crash
            pass


def get_logger(name: str = "elixir") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        log.addHandler(JsonHandler())
        log.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return log
