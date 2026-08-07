# Install: scenario-simulate

One runtime dep, no external API key. ~1 minute, the lightest of the managed
skills, because inference is the gateway you are already on.

## 0. Prereqs

```bash
# if the environment uses uv:
uv sync
# otherwise:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27"
```

`httpx` plus the standard library is the whole footprint. No browser, no ML
framework, no simulation library. The loop is `asyncio` and the reasoning is
the gateway. That is what keeps it runnable in a bare sandbox and cheap to cold
start.

## 1. Gateway key (required)

```bash
export STIMULIR_API_KEY="hyb_..."
```

This is the workspace's ordinary inference key, not a skill-specific secret, so
a managed run needs no vault entry beyond what it already injects.

Optional overrides:

```bash
export STIMULIR_API_BASE="https://api.stimulir.com"   # default
export STIMULIR_PROJECT_ID="..."                       # sent as X-Project-Id when set
export STIMULIR_MODEL="stimulir/fusion"                # default
```

## 2. Smoke test, no network needed

```bash
cd helpers
python3 population.py --context ../examples/context.example.json --n 12 --seed 1 --out /tmp/pop.json
```

If that writes 12 personas, the skill is installed. Add `step.py` to make the
first live call.

## 3. Symlink into an agent's skills dir

```bash
ln -s "$PWD" ~/.claude/skills/scenario-simulate    # Claude Code
ln -s "$PWD" ~/.codex/skills/scenario-simulate     # Codex
```

## Notes

- No key ever goes on a command line. `STIMULIR_API_KEY` is read from the
  environment only, which is what makes the skill safe to run managed.
- Cost and wall-clock scale as personas × timesteps. Start at `--n 20` and one
  step.
- **Measured on staging** (`stimulir/fusion`): 40 personas at `--concurrency 8`
  took **190s, over the 180-second managed budget**. At the default
  `--concurrency 12` the same population fits. Concurrency is the cheapest lever
  because the calls are I/O-bound; if you raise `--n`, raise concurrency with it
  and time one step locally before running it managed.
- Two personas in that run failed with read timeouts and the batch completed
  regardless. That is the intended behaviour, not a fault. Check `failed` in the
  aggregate before trusting a distribution.
