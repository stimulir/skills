# eval-run

Measures **one change, once**. Starts a durable stimulir Lab eval run against
a curated, reviewed data asset, then reads back what it scored. Stage 3 of
the promote-with-evidence pipeline: after real traffic has been captured and
snapshotted into a data asset, before any promotion decision.

## Why

- **It does not wait.** `create-run` detaches: it creates, starts, prints the
  run id, the status and a console deep link, and returns. There is no
  `--wait` flag in the CLI and no polling helper here, because a `--wait`
  flag is a poll loop with a friendlier name and it burns the agent's context
  on a run the console is already tracking.
- **It measures, it does not iterate.** The skill performs run-scoped
  mutations (create, execute, archive) and unlimited reads (get, runs, tree,
  steers). It never performs a lineage mutation (derive, steer-write, ack).
  Branching is an iteration decision that needs a budget, a champion pointer
  and a stopping rule, and all three live in the console.
- **It refuses the judgment call.** Neither helper decides whether a score is
  good enough. Promotion is `prompt-versioning`'s surface; this skill
  produces the evidence and hands it over.
- **Honest about its one hard dependency.** An eval run is only as
  trustworthy as the data asset behind it, and this skill does not curate or
  review data assets. See [`SKILL.md`](./SKILL.md).

## Quick start

```bash
# 1. start the run. Detaches immediately, prints a console link.
python helpers/create_eval_run.py \
  --name "summarize-ticket-v4-vs-v3" \
  --data-asset-id da_abc123 \
  --prompt summarize-ticket:4 \
  --execute

# 2. later, read the status ONCE. No loop, no timeout argument.
python helpers/check_eval_run.py --run-id <run-id>

# 3. read the promotion evidence: best arm per bucket, with blockers.
stimulir lab eval tree <run-id>
```

`--execute` is the normal path, not an opt-in extra. Without it the run is
created QUEUED with no executor and nothing polls for queued runs, so it
never starts. The helper refuses to guess: pass `--execute`, or
`--leave-queued` to say you will start it later with
`stimulir lab eval execute-run <id>`.

See [`SKILL.md`](./SKILL.md) for the full playbook, including the scope rule,
how to read a score without misreporting it, and why steers are displayed but
never acted on. See [`install.md`](./install.md) for setup.

## Architecture

```
create_evaluator.py → stimulir lab eval evaluator-create        → evaluator id (invariant gate)
create_eval_run.py  → stimulir lab eval create-run --execute    → run id + status + console link
check_eval_run.py   → stimulir lab eval get <id> --json         → one flat status read
```

Three independent scripts, no shared state, no server, no background process.
Each wraps exactly one CLI invocation. `create_evaluator.py` mints an invariant
evaluator that `create_eval_run.py --evaluator-id` attaches, so a violating
prompt candidate is skipped before any judge spend and barred from
re-derivation.

`create_eval_run.py` adds one guard the CLI lacks: it will not create a run
unless the caller says explicitly whether it should start. It passes the CLI's
human output through rather than `--json`, because the console deep link is
printed on the human path only.

`check_eval_run.py` replaces the former `poll_eval_run.py`, which looped in
the foreground until the run was terminal. The replacement takes no
`--interval-seconds` and no `--timeout-seconds`; the absence of those
arguments is what keeps the wait out of the agent's context.

Everything else is a raw CLI call documented in `SKILL.md`: `tree`, `steers`,
`runs`, `execute-run`, `delete`.
