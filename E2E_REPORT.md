# Elixir end-to-end verification

**Date:** 2026-10-02  
**Repository:** `demolished-lab/elixir`  
**Result:** **23 passed, 0 failed**

## What was verified

- Full `pytest` suite: all existing brain, edge-case, production-policy, memory, spend, seat-lock, judge, and recording tests pass.
- `doctor`: runs without crashing and reports each of the 8 tiers.
- `health`: returns machine-readable JSON and correctly reports the environment as unhealthy when optional tiers are absent.
- Real fetch: `https://example.com` returned the live Example Domain page.
- Brain run: `fetch https://example.com` completed successfully and recorded a verified `web_fetch` step.
- Social login-wall routing: `xiaohongshu` returns a safe cloak/profile fallback plus cookie-login unlock instructions.
- Unknown platform: `myspace2` returns a structured `unknown platform` error.
- Judge: natural-language fetch planning works through the deterministic fallback when Needle is not installed.
- Act edge case: returns a structured `cloakbrowser unavailable` result instead of crashing.
- Recording: `--record` produces inspectable local metadata when `cua-driver` is not installed.
- Syntax validation: `python3 -m compileall -q elixir` passes.

## Run it yourself

From the repository root:

```bash
python3 -m pytest tests/ -q
python3 -m elixir doctor
python3 -m elixir health
python3 -m elixir fetch https://example.com --dump markdown
python3 -m elixir run 'fetch https://example.com'
python3 -m elixir social xiaohongshu
python3 -m elixir social myspace2
python3 -m elixir decide 'fetch https://example.com'
python3 -m elixir act https://example.com
python3 -m elixir run 'fetch https://example.com' --record
```

## Visible evidence

The successful recorded run is at:

`runs/20261002-103439-task/run.json`

It records the local evidence backend and the reason it was selected:

```json
{
  "label": "task",
  "video": false,
  "backend": "local-metadata",
  "note": "cua-driver missing"
}
```

## Changes made

- Fixed a `doctor` CLI crash caused by an inner import shadowing the module-level `doctor_all` binding.
- Added a read-only `urllib` fetch fallback when Obscura and Cloak are unavailable.
- Added deterministic judge routing when optional `cactus-needle`/Needle is unavailable.
- Added structured degraded social status when `agent-reach` is unavailable.
- Added a structured non-crashing result for `act` when Cloak is unavailable.
- Added local metadata recording so `--record` remains visibly testable without OS hands.

## Environment limitation

The sandbox has Wigolo and network access, but not the optional Obscura binary, Cloakbrowser package, `cua-driver`, `agent-reach`, CLI-Hub, or Needle package. Elixir now runs the safe read-only and policy paths in this environment and labels unavailable tiers honestly. Installing those optional tools is still required to validate stealth browser actions, desktop control, social backends, and actual screenshots/video capture.
