# eval-run

Compares a prompt or model change against a curated, reviewed dataset
before it ships to production, by creating and polling a stimulir lab eval
run -- the Stage 3 gate that sits after real traffic has been captured and
curated into a snapshotted data asset, and before any promotion decision.

## Why

- Thin CLI wrapper, not a reimplementation: shells out to `stimulir lab
  eval create-run` / `get-run` rather than hand-rolling REST auth --
  `stimulir` already owns token/workspace headers via `~/.stimulir/`.
- Creation and execution are separated: `create_eval_run.py` queues a run
  by default; `--execute` (real, costed inference work) is opt-in and
  named explicitly.
- Polling is read-only and safe to run unattended: `poll_eval_run.py` only
  GETs an already-created run's status until it's terminal, then reports a
  pass/fail/score summary -- it never creates or mutates anything itself.
- Honest about its one hard dependency: an eval run is only as trustworthy
  as the data asset behind it. This skill does not curate or review data
  assets -- see [`SKILL.md`](./SKILL.md) for why an unreviewed/unsnapshotted
  data asset produces misleading results.

## Quick start

```bash
# 1. create a run (queued, not yet executing)
python helpers/create_eval_run.py \
  --name "summarize-ticket-v4-vs-v3" \
  --data-asset-id da_abc123 \
  --prompt summarize-ticket:4

# 2. once you've confirmed the data asset + prompt ref, execute it
python helpers/create_eval_run.py \
  --name "summarize-ticket-v4-vs-v3" \
  --data-asset-id da_abc123 \
  --prompt summarize-ticket:4 \
  --execute

# 3. poll to completion and get a pass/fail/score summary
python helpers/poll_eval_run.py --run-id run_from_step_2
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including the data-asset
review dependency and why `--execute` is opt-in) and
[`install.md`](./install.md) for setup.

## Architecture

```
create_eval_run.py   → stimulir lab eval create-run [--execute]  → run ID
poll_eval_run.py      → stimulir lab eval get-run (looped)        → pass/fail/score summary
```

Two independent scripts, no shared state, no server. Each helper wraps
exactly one CLI command and returns structured JSON -- neither one decides
what the result means; that's the calling agent's job.
