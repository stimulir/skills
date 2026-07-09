# Install — capture-traces

Assumes `connect` has already run in this environment (the `stimulir` CLI
installed, authenticated, workspace selected) -- this runbook does not
re-cover that setup, only what's specific to this skill. ~5 minutes.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # 3.10+

# if the environment uses uv:
uv sync
```

All three helpers (`capture_trace.py`, `advance_stage.py`,
`snapshot_asset.py`) shell out to the `stimulir` CLI and use only the Python
standard library (`argparse`, `json`, `subprocess`, `sys`) -- there are no
third-party dependencies to install for this skill. `pyproject.toml` exists
for `uv sync` / packaging parity with the rest of this skill family, not
because anything here needs a package beyond the stdlib.

## 1. Skill install

### Local clone + symlink

```bash
git clone <this-skills-repo-url> ~/Developer/skills
```

For Codex:
```bash
ln -s ~/Developer/skills/skills/capture-traces ~/.codex/skills/capture-traces
```

For Claude Code:
```bash
ln -s ~/Developer/skills/skills/capture-traces ~/.claude/skills/capture-traces
```

### `npx skills add`

```bash
npx skills add <org>/<skills-repo>
```

## 2. Confirm the CLI is authenticated and the workspace is selected

This skill does no auth of its own -- it relies entirely on `connect`
having already set up `~/.stimulir/`:

```bash
stimulir data list --json
```

If this fails with an auth error ("not logged in", 401, etc.), go run
`connect` first. There is no local fallback and this skill does not attempt
to reimplement login.

## 3. Confirm migrate-inference is actually producing traces

`capture_trace.py` captures a trace by ID -- there is nothing to capture
until inference traffic is flowing through Stimulir and traces exist in
this workspace. If `migrate-inference` hasn't run yet (or isn't sending
real traffic through the gateway), `stimulir data from-trace` will fail
with "trace not found" for any ID you try. That's expected; go run
`migrate-inference` first.

## 4. Verify

```bash
cd ~/Developer/skills/skills/capture-traces

# sanity-check the CLI wrapper shape without needing a real trace:
python3 helpers/capture_trace.py --help
python3 helpers/advance_stage.py --help
python3 helpers/snapshot_asset.py --help

# once you have a real trace UUID from migrate-inference traffic:
python3 helpers/capture_trace.py <real-trace-uuid> --source agent --target eval

# snapshot dry-run is always safe to try -- it creates nothing without --confirm:
python3 helpers/snapshot_asset.py <asset-id-from-above> --label smoke-test
```

If `capture_trace.py` fails with a `stimulir` CLI error, re-run `stimulir
data list --json` directly to confirm auth/workspace selection is still
good before assuming this skill is broken.

## 5. Notes

- **Sequencing**: if this adopter has a privacy-layer skill, confirm it has
  actually run on the traffic before capturing traces from it. See
  `SKILL.md`'s "Placement rationale" for why this order matters -- captured
  traces can become training/eval data, so PII needs to be scrubbed at the
  source, not retroactively.
- `advance_stage.py` needs `stimulir data list --json` to look up an
  asset's current stage before allowing a transition -- if that call is
  slow or rate-limited in a given workspace, expect `advance_stage.py` to
  inherit that latency. `--skip-adjacency-check` bypasses the lookup
  entirely but also bypasses the one-stage-at-a-time safety check; only use
  it for a verified, deliberate override (see `SKILL.md`'s Anti-patterns).
- `snapshot_asset.py` defaults to dry-run. This is intentional, not a bug
  -- snapshots are immutable, so the default posture requires an explicit
  `--confirm` before anything is actually created.
