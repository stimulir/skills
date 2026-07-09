# Install — usage-audit

No hardware, no server, no write access needed -- this skill is entirely
read-only. ~5 minutes, less if `connect` has already run.

## 0. Prereqs

This skill assumes `connect` has already run: the `stimulir` CLI installed,
authenticated, and pointed at the right workspace. If that hasn't happened
yet, do it first (see the top-level `connect` setup for this environment) --
it is not re-documented here.

```bash
which stimulir
stimulir --version
```

If `stimulir` isn't found on `PATH`, install it per your environment's
standard stimulir CLI install path, then run `connect` before continuing.

Python 3.10+ with `uv` recommended:
```bash
brew install uv
```

## 1. Skill install

Each skill in this repo owns its own Python environment. The correct
bootstrap point is the `usage-audit` directory itself, not the repo root.

### Local clone + symlink

```bash
git clone <this-repo-url> ~/Developer/skills
cd ~/Developer/skills/skills/usage-audit
uv sync  # installs httpx
```

For Codex:
```bash
ln -s ~/Developer/skills/skills/usage-audit ~/.codex/skills/usage-audit
```

For Claude Code:
```bash
ln -s ~/Developer/skills/skills/usage-audit ~/.claude/skills/usage-audit
```

### `npx skills add`

If you install the skill files through a skill installer, run the same
dependency bootstrap from the installed skill directory afterwards:

```bash
npx skills add <org>/<repo>

cd ~/.claude/skills/usage-audit   # or ~/.codex/skills/usage-audit
uv sync
```

## 2. Auth

This skill deliberately does NOT implement its own login flow. It relies on
`stimulir` CLI auth already being set up by `connect`:

```bash
stimulir usage --window 1d --group-by model --json
# should print a JSON payload, not an auth error
```

If that fails with an authentication error, re-run `connect` -- this skill
has no local fallback and will refuse to proceed without it.

### REST fallback (only used by `usage_events.py`)

`usage_summary.py` and `billing_snapshot.py` require the CLI, full stop.
`usage_events.py` prefers the CLI too (`stimulir usage events --json`), but
falls back to a direct REST call if the installed CLI version has no
`usage events` subcommand. That fallback needs:

```bash
export STIMULIR_API_URL=https://api.stimulir.com   # default, override for self-hosted/staging
export STIMULIR_API_KEY=hyb_...                     # only needed if the CLI fallback triggers
```

If your `stimulir` CLI already supports `usage events`, you can skip this
entirely -- the REST path is never touched.

## 3. Verify

```bash
cd ~/Developer/skills/skills/usage-audit

# CLI reachable and authenticated
python3 helpers/billing_snapshot.py
# prints a JSON billing snapshot on success

# usage summary for a short window
python3 helpers/usage_summary.py --window 1d --group-by model

# raw events for the same window, for reconciliation
python3 helpers/usage_events.py --window 1d
```

If any command fails with `'stimulir' CLI not found on PATH`, go back to
step 0. If it fails with an authentication error, go back to step 2 and
re-run `connect`.

## 4. Notes

- This skill never writes to the account it reports on -- there is no
  `--confirm` flag anywhere because there is no irreversible action to gate.
- Corporate/offline environments that cannot reach `STIMULIR_API_URL`
  directly can still use `usage_summary.py` and `billing_snapshot.py` fully
  (CLI-only) as long as the CLI itself can reach stimulir's API. Only
  `usage_events.py`'s REST fallback needs direct outbound HTTPS access, and
  only when the CLI lacks a `usage events` subcommand.
- Treat a single `usage_summary.py` call as a snapshot, not an audit. Pair
  it with `usage_events.py` for the same window before reporting a spend
  number as final -- see `SKILL.md`.
