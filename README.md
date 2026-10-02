# Elixir — human-equal web entity
Standalone router: `wigolo -> obscura -> cloak -> cua-driver`, read + act.

Demo video kept local-only by choice (`take_full.mp4`, not shipped).

## Install
```powershell
git clone https://github.com/demolished-lab/elixir.git
cd elixir
pip install -e .                    # elixir cli
npx -y wigolo --version              # search/memory (already 0.2.1 on this box)
~/.obscura/obscura.exe --version     # fast render (already 0.2.2)
pip install cloakbrowser             # stealth (already 0.5.11 + 152-pro)
# optional OS hands (installed 0.32.0, daemon on named pipe):
cua-driver serve --socket "\\.\pipe\cua-driver"  # one daemon per boot, then:
python -m elixir doctor              # all four tiers ok
```

## Use
```powershell
python -m elixir doctor              # probe every tier for real
python -m elixir search "LLM framework compare" --json
python -m elixir fetch https://example.com --dump markdown
python -m elixir act https://browserscan.net/bot-detection --screenshot scan.png
python -m elixir studio              # local web UI at http://127.0.0.1:8765/
```

Routing: wigolo search -> obscura fetch -> cloak `launch_persistent_context(humanize=True)` on `blocked_by_challenge/403/Turnstile`.
Profiles: `./profiles/<site>/` fixed `--fingerprint=seed` + storage_state, one human per site.
Artifacts (`.md` / `.pdf` / screenshots) land in `<ELIXIR_DATA_DIR>/artifacts/`
— that is the only directory Studio will ever serve.

## Security model (Studio)

| Control | Behaviour |
| --- | --- |
| Bind | `127.0.0.1` only, never `0.0.0.0` |
| Auth | random token per process, required on **every** route except `/` |
| CORS | no `Access-Control-Allow-Origin`, ever — a foreign page cannot read the token |
| CSRF | `Origin` must be loopback, `Host` must be loopback, `Content-Type` must be `application/json` |
| Body | capped at 64 KB, `task` capped at 2000 chars, malformed JSON → 400 |
| File reads | `os.path.commonpath()` containment inside `artifacts/`, `.env`/`.lock`/`.jsonl` refused |
| Memory | finished runs pruned after 15 min, hard cap of 50 |
| Subprocess | `shell=False` everywhere; `npx` resolved to its absolute path so `&`/`|` reach wigolo as literal argv |
| URLs | `http`/`https` only; cloud metadata endpoints refused |
| Spend | `spend.allowed()` checked *inside* `_bynara_text`/`_bynara_vision`, not left to callers |
| Output | feed HTML is escaped; untrusted tool evidence is wrapped as tagged data for the synthesiser |

## Ops (production)
```powershell
elixir doctor        # human report, 8 tiers
elixir health        # machine JSON: {"healthy": bool, "tiers": {...}} — point monitoring here
elixir versions      # pinned vs installed upstream drift
elixir spend         # metered cloud-eyes vs monthly cap (default 50000 IDR)
elixir autopilot     # self-heal safe tiers, ask approval for login/spend/install
elixir studio        # local web UI, token printed at startup
python -m pytest -q  # 56 gates: injection, CSRF, traversal, spend cap, seat lock, scrub
```
CI (`.github/workflows/ci.yml`) runs `pyflakes` + the suite on
ubuntu/windows × Python 3.10/3.13, and builds the wheel.
Policy: `elixir/autopilot.py` — auto = retries/escalation/rotation/daemons;
ask = logins, spend, installs, updates, irreversible. An approval with a
`run` key executes immediately (a declined or inert approval is theatre).
Secrets via env/`.env` (`ELIXIR_BYNARA_KEY_FILE`), never code;
logs scrub keys (`elixir/log.py`).
