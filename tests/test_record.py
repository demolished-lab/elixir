# -*- coding: utf-8 -*-
"""Trajectory evidence gates."""

from elixir import record


def test_record_roundtrip():
    r = record.start("unit-test")
    assert r["ok"] is True
    assert "dir" in r
    s = record.stop()
    assert isinstance(s, dict)
    st = record.state()
    assert isinstance(st, dict)
