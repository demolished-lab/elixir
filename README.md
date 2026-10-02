# Elixir — human-equal web entity
Standalone router: `wigolo -> obscura -> cloak -> cua-driver`, read + act.

Demo video kept local-only by choice (`take_full.mp4`, not shipped).

## Install
```powershell
cd C:\path\to\elixir
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
```

Routing: wigolo search -> obscura fetch -> cloak `launch_persistent_context(humanize=True)` on `blocked_by_challenge/403/Turnstile`.
Profiles: `./profiles/<site>/` fixed `--fingerprint=seed` + storage_state, one human per site.

## Ops (production)
```powershell
elixir doctor        # human report, 8 tiers
elixir health        # machine JSON: {"healthy": bool, "tiers": {...}} — point monitoring here
elixir versions      # pinned vs installed upstream drift
elixir spend         # metered cloud-eyes vs monthly cap (default 50000 IDR)
elixir autopilot     # self-heal safe tiers, ask approval for login/spend/install
python -m pytest tests/ -q   # 9 gates: credentials never auto, spend cap, seat lock, scrub
```
Policy: `elixir/autopilot.py` — auto = retries/escalation/rotation/daemons/updates;
ask = logins, spend, installs, irreversible. Secrets via env/`.env`
(`ELIXIR_BYNARA_KEY_FILE`), never code; logs scrub keys (`elixir/log.py`).
