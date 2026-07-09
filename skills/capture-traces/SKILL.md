---
name: capture-traces
description: Turn live inference traffic already flowing through Stimulir (from the migrate-inference stage) into curated data assets, and move those assets through the Raw → Cleaning → Clean View → Snapshot → Lab pipeline one stage at a time. Use when the user wants to capture a trace as a dataset, promote/clean/stage a data asset, snapshot a dataset version, or otherwise turn production inference traffic into eval/training data -- this is the literal mechanism behind "gets sharper as it runs." Sequence AFTER a privacy-layer skill has scrubbed PII from the same traffic; do not use on raw, unscrubbed traces.
---

# Capture Traces

This skill is Stage 2 of the Stimulir adoption path, and it is CORE, not
optional polish. `migrate-inference` gets an adopter's inference traffic
flowing through Stimulir; on its own, that's just a pass-through gateway --
same behavior, extra hop. **This skill is what turns that traffic into the
thing Stimulir actually sells**: curated, versioned, improving data assets
built from an adopter's own real production traces. Without this skill
running regularly, "gets sharper as it runs" is a slogan with nothing behind
it.

## Placement rationale

This assumes `connect` has already run: the `stimulir` CLI is installed,
authenticated, and pointed at the right workspace. This skill does not
re-document that setup -- see `install.md` for the one thing specific to
*this* skill (confirming trace capture actually works end to end).

This also assumes `migrate-inference` has already run and traffic is
flowing -- there is nothing to capture from `stimulir data from-trace` until
inference calls are actually landing in Stimulir with trace IDs attached.

**Sequencing dependency, stated explicitly because it is easy to get wrong:**
this skill should run AFTER a privacy-layer skill has had a chance to scrub
PII from the same traffic, not before, and not "later, during cleaning."
Captured traces can become future training/eval data -- once a raw trace
with a customer's email, phone number, or other PII is pulled into a data
asset via `from-trace`, that PII is now sitting in the data pipeline
(Raw stage, then potentially copied forward into Cleaning, Clean View,
Snapshot, Lab). Scrubbing after capture means scrubbing N copies across
pipeline stages instead of one at the source. If no privacy-layer skill is
installed or has not run yet, say so explicitly and pause -- do not proceed
to capture traces on the assumption that "Cleaning" will handle it; the
pipeline's "Cleaning" stage is about dataset quality/dedup/formatting, not
a substitute for PII redaction.

## Preflight

```bash
stimulir --version
stimulir data list --json
```

If `stimulir data list --json` fails with an auth error, `connect` has not
been completed in this environment -- stop and tell the user to run it
first. Do not attempt to reimplement login or session handling here; the
CLI already owns that via `~/.stimulir/`.

## The pipeline

Every data asset moves through exactly these five stages, in exactly this
order, one step at a time:

```
Raw  →  Cleaning  →  Clean View  →  Snapshot  →  Lab
```

| Stage | What it means | When to move an asset here |
|---|---|---|
| **Raw** | Exactly what `from-trace` captured -- unmodified trace payload turned into an asset. Starting point, never a destination you move back to. | Automatic: this is where `capture_trace.py` lands every new asset. |
| **Cleaning** | Actively being deduplicated, reformatted, filtered, or otherwise transformed. A working-state stage, not a resting one. | After Raw, once there's an actual cleaning operation to perform (dedup, reformat, filter malformed rows/turns) -- not just because "some time passed." |
| **Clean View** | A stable, reviewed view of the cleaned data -- the first stage where the asset is trustworthy enough to look at, use, or start relying on. | After cleaning work is genuinely done and the result has been reviewed (by the agent's own inspection, or by a human) -- not immediately after Cleaning starts. |
| **Snapshot** | An immutable, versioned freeze of the Clean View data. This is the point a Lab run or eval should actually point at, so results are reproducible against a fixed version. | Right before the data is going to be used for something that needs to be reproducible later (a Lab experiment, an eval baseline) -- see `snapshot_asset.py`'s dry-run-by-default posture below. |
| **Lab** | The asset is in active use for experimentation -- fine-tuning runs, eval suites, offline analysis. | After a Snapshot exists. Never promote straight from Clean View to Lab; Lab work should always point at a frozen Snapshot, not a still-mutable Clean View. |

**One stage at a time, no exceptions in normal operation.** `advance_stage.py`
enforces this mechanically: it checks the asset's current stage and refuses
to jump (Raw straight to Clean View, Cleaning straight to Snapshot, etc.).
This is not pedantry -- Cleaning and Clean View exist as separate,
observable stages specifically so there's a checkpoint between "we started
touching this data" and "this data is trustworthy," and skipping that
checkpoint defeats the purpose of having it.

## Workflow

### 1. Capture a trace into a Raw asset

```bash
python helpers/capture_trace.py <trace-uuid> --source agent --target eval
```

`--source` is what generated the trace -- the live CLI accepts exactly
`agent` or `usage`, nothing else (`capture_trace.py` enforces this via
`choices=`). `--target` is optional and tags the intended downstream use
(e.g. `eval`, `sft`, `preference`) -- it's metadata for humans and
downstream filtering (`stimulir data list --target ...`), not a hard
constraint at capture time. `<trace-uuid>` must be an actual trace UUID
from the workspace (from `stimulir lab eval ...` output or the traces
panel) -- migrate-inference traffic that hasn't landed yet has no trace to
capture. This produces a new Raw-stage asset and prints its JSON record
(including its `id`) to stdout.

**Before running this**, confirm the privacy-layer skill (if present in
this adopter's setup) has already run on the traffic this trace came from.
If it hasn't, stop and say so -- see "Placement rationale" above.

### 2. Advance the asset through the pipeline, one stage at a time

```bash
python helpers/advance_stage.py <asset-id> --to cleaning
# ... cleaning work happens, reviewed ...
python helpers/advance_stage.py <asset-id> --to clean_view
```

Each call moves the asset exactly one step forward. The helper looks up the
asset's current stage via `stimulir data list --json` and refuses to run if
`--to` isn't the immediate next stage -- this is a mechanical adjacency
check, not a judgment call about whether the data is actually ready. The
agent (or a human reviewer) is responsible for deciding *when* an asset is
ready to move; this helper only prevents *skipping steps* once that
decision is made. (`--to` is this helper's own flag name; underneath it
calls the real CLI's positional form, `stimulir data stage <id> <stage>`.)

### 3. Snapshot before anything reproducible depends on this data

```bash
# dry run (default) -- shows what would happen, creates nothing
python helpers/snapshot_asset.py <asset-id> --label "eval-baseline-2026-07"

# actually create the immutable snapshot
python helpers/snapshot_asset.py <asset-id> --label "eval-baseline-2026-07" --confirm
```

Snapshotting is irreversible -- it freezes a version of the data
permanently. `snapshot_asset.py` defaults to dry-run and only calls
`stimulir data snapshot` with `--confirm` explicitly passed. Run the dry
run first, confirm the asset id is what's intended, then re-run with
`--confirm`. Note: the real `stimulir data snapshot` command has no
`--label` flag -- `--label` here is a local-only annotation this helper
echoes back in its own JSON output (`_local_label`) for the agent's
bookkeeping; it is never sent to the CLI.

### 4. Promote to Lab once a Snapshot exists

```bash
python helpers/advance_stage.py <asset-id> --to lab
```

Only after a Snapshot has actually been created (step 3, with `--confirm`)
-- `advance_stage.py`'s adjacency check will refuse `--to lab` if the
asset's current stage isn't `snapshot`.

## CLI reference

```bash
# capture (--source is required, one of: agent, usage; --target/--name optional)
python helpers/capture_trace.py <trace-uuid> --source agent [--target eval] [--name "..."]

# advance one stage (raw -> cleaning -> clean_view -> snapshot -> lab)
python helpers/advance_stage.py <asset-id> --to <stage> [--skip-adjacency-check]

# snapshot (dry-run unless --confirm; --label is local-only, not sent to the CLI)
python helpers/snapshot_asset.py <asset-id> [--label <text>] [--confirm]
```

Direct CLI equivalents these helpers wrap (verified against the live
`stimulir` CLI v0.1.0 `--help` output -- useful for spot-checking without
Python, or for operations these helpers don't cover, like `data create`,
`data upload`, `data unstage`, or `data bulk-stage`):

```bash
stimulir data from-trace <trace-uuid> --source agent --target eval --json
stimulir data list --json
stimulir data upload ./dataset.jsonl --stage raw --target eval --json
stimulir data stage <asset-id> <stage> --json   # positional stage, NOT --to
stimulir data snapshot <asset-id> --json        # no --label flag on the real CLI
```

## Output contract

All three helpers print the parsed JSON response from the underlying
`stimulir data ...` command to stdout (via `--json`), indented for
readability. `snapshot_asset.py` in dry-run mode (no `--confirm`) instead
prints `{"dry_run": true, "would_run": "...", ...}` and performs no CLI
call. Errors from the underlying CLI go to stderr and the helper exits
non-zero -- these are not swallowed or retried silently.

## Anti-patterns (do NOT do)

- **Capturing traces before a privacy-layer skill has scrubbed the source
  traffic.** Captured traces can become future training/eval data. If PII
  scrubbing happens after capture (or not at all), raw PII is now sitting
  in a data asset pipeline, potentially copied across multiple stages.
  Scrub at the source, before capture -- not after.
- **Skipping pipeline stages.** Don't call `stimulir data stage <id> --to
  snapshot` directly, and don't pass `--skip-adjacency-check` to
  `advance_stage.py` out of impatience. The Cleaning → Clean View
  distinction exists specifically to create a checkpoint before data is
  trusted; skipping it defeats the purpose of the pipeline.
- **Treating `snapshot_asset.py`'s dry-run output as if a snapshot was
  created.** It wasn't -- nothing happens without `--confirm`. Don't tell a
  user "snapshotted" based on the dry-run JSON alone.
- **Promoting an asset to Lab without a Snapshot existing first.** Lab work
  (fine-tuning, eval runs) should point at an immutable version, not a
  still-mutable Clean View -- otherwise results aren't reproducible against
  a fixed dataset.
- **Reimplementing REST auth or hitting `/api/v1/workspace/data-assets`
  directly in Python.** The `stimulir` CLI already owns session/credential
  handling via `~/.stimulir/`; shell out to it with `--json`, don't
  duplicate that logic here.
- **Deciding on the caller's behalf that data "is probably clean enough" to
  skip from Raw straight to Snapshot.** That's an editorial judgment call
  these helpers deliberately do not make -- `advance_stage.py` enforces the
  mechanical one-step-at-a-time rule, but whether an asset is actually
  *ready* to advance is for the agent (or a human) to decide before calling
  it, informed by looking at the data, not by convenience.
- **Calling `capture_trace.py` on a trace ID from before `migrate-inference`
  was live**, or on traffic that never actually flowed through Stimulir.
  There's nothing to capture from a trace ID that doesn't exist in the
  workspace, and the helper will fail loudly rather than fabricate a
  result -- that's correct behavior, don't route around it.
