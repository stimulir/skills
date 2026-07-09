---
name: eval-run
description: Compare a prompt or model change against a curated dataset before promoting it to production, using stimulir's lab eval runs (create-run, execute, poll to completion, summarize pass/fail/score). Use when the user wants to evaluate/benchmark a new prompt version, model, or config change against a known dataset, gate a promotion/deploy on eval results, or check the status/score of an eval run that's already in flight.
---

# Eval Run

This skill creates and monitors a **lab eval run**: stimulir's mechanism for
comparing a prompt or model change against a curated, versioned dataset
(a "data asset") before that change ships to production. It is Stage 3 of
the promote-with-evidence pipeline -- capture real traffic, curate it into a
reviewed data asset, *then* run a change against that asset here, and only
promote if the run's results hold up.

## Placement rationale

This skill assumes `connect` has already run (stimulir CLI installed,
authenticated, workspace selected) -- that setup is not re-documented here.

Eval-run creation and polling are ordinary authenticated API actions with no
local hardware dependency, so this skill shells out to the `stimulir` CLI
(which already owns login/session caching in `~/.stimulir/`) rather than
reimplementing `Authorization: Bearer` / `X-Business-Profile-Id` auth in
Python. Nothing here starts a server or a background process --
`poll_eval_run.py` runs to completion (or timeout) in the foreground and
exits.

## Preflight

```bash
stimulir --version
stimulir lab eval create-run --help
python3 --version
```

Confirm the `stimulir` CLI is installed and authenticated (`connect` has
already run) before doing anything else. If `stimulir lab eval create-run
--help` fails with an auth error, stop and fix authentication first --
don't try to work around it by calling REST directly.

## The dependency this skill will NOT paper over

**An eval run is only as trustworthy as the data asset it runs against.**
This skill does not create, curate, or review data assets -- that is
upstream work (capture real traffic, then curate/snapshot it into a
reviewed data asset, e.g. via a `capture-traces`-style skill). Before
calling `create_eval_run.py`:

1. Confirm the `--data-asset-id` you're about to pass refers to a data
   asset that has actually been **reviewed and snapshotted** -- not a raw,
   unreviewed trace dump. If you (or the user) are not sure whether the
   data asset has been through that review step, say so and ask, or go
   curate it first. Do not guess.
2. Confirm the `--prompt <key>:<version>` you're comparing is the exact
   version under test -- an eval run against the wrong prompt version
   produces a result that looks authoritative but answers the wrong
   question.

Running an eval against an unreviewed/unsnapshotted data asset is the
single most common way this skill produces misleading results: a
low-quality or unrepresentative dataset yields a pass/fail signal that
doesn't actually predict production behavior. See Anti-patterns below.

## The workflow

### 1. Create the run

```bash
python helpers/create_eval_run.py \
  --name "summarize-ticket-v4-vs-v3" \
  --data-asset-id <data-asset-id> \
  --prompt summarize-ticket:4
```

This creates the run but leaves it queued (does not start execution) unless
`--execute` is passed:

```bash
python helpers/create_eval_run.py \
  --name "summarize-ticket-v4-vs-v3" \
  --data-asset-id <data-asset-id> \
  --prompt summarize-ticket:4 \
  --execute
```

`--execute` is opt-in on purpose: it kicks off real evaluation work
(inference calls against every row in the data asset) immediately, which
costs time and money. Only pass it once you've confirmed the data asset and
prompt reference above -- creating the run without `--execute` lets you
inspect what was queued before committing to a full pass.

Prints the CLI's `--json` response, which includes the run ID needed for
step 2.

### 2. Poll to completion

```bash
python helpers/poll_eval_run.py --run-id <run-id-from-step-1>
```

Polls `stimulir lab eval get-run --run-id <id> --json` on an interval
(`--interval-seconds`, default 10s) until the run reaches a terminal status
(`completed`, `succeeded`, `failed`, `errored`, `cancelled`), or until
`--timeout-seconds` (default 1800 = 30 minutes) elapses. This is read-only
GET polling against a run the agent already explicitly created in step 1 --
safe to run unattended, since nothing here is irreversible or billed beyond
the run itself.

Prints a JSON summary:

```json
{
  "run_id": "run_abc123",
  "status": "completed",
  "passed": 42,
  "failed": 3,
  "total": 45,
  "score": 0.933,
  "polls": 6,
  "elapsed_seconds": 58.2,
  "raw": { "...": "full CLI get-run payload, nothing dropped" }
}
```

`passed` / `failed` / `total` / `score` are read straight off the CLI
response's `results` or `summary` field (whichever is present); if the CLI
schema doesn't expose those fields the summary still includes `status` and
the full `raw` payload so nothing is silently lost.

### 3. Interpret the result (agent's job, not the helper's)

`poll_eval_run.py` reports what happened -- it does not decide whether a
0.933 score is good enough to promote, whether a handful of failures are
acceptable, or whether the eval needs to be re-run against a larger data
asset. That judgment belongs to the agent (and ultimately the user):
compare the score/failures against whatever bar the team has set for this
prompt/model, and only recommend promotion if the run's results and the
underlying data asset both hold up to scrutiny.

## CLI reference

```bash
# create a run (queued by default; --execute starts it immediately)
python helpers/create_eval_run.py --name <name> --data-asset-id <id> \
  --prompt <key>:<version> [--execute] [--stimulir-bin <path>]

# poll an existing run to completion
python helpers/poll_eval_run.py --run-id <id> \
  [--interval-seconds 10] [--timeout-seconds 1800] [--stimulir-bin <path>]
```

Underlying CLI surface this skill wraps:

```bash
stimulir lab eval create-run --name <name> --data-asset-id <id> \
  --prompt <key>:<version> [--execute]
stimulir lab eval get-run --run-id <id> --json
```

REST equivalent (durable-run CRUD, for reference -- this skill does not
call REST directly):

```
POST   /api/v1/lab/evals/runs
POST   /api/v1/lab/evals/runs/{id}/execute
GET    /api/v1/lab/evals/runs/{id}
```
Auth: `Authorization: Bearer $STIMULIR_TOKEN`, `X-Business-Profile-Id: $WORKSPACE_ID`.

SDK equivalent, for reference: `client.lab_evals.create_run(name=..., data_asset_id=..., prompt_ref=..., model=...)`, `client.lab_evals.get_run(...)`.

## Output contract

- `create_eval_run.py` prints the CLI's `--json` create-run response
  unmodified (pretty-printed) to stdout. It always includes at least the
  new run's ID (`id` or `run_id`), which is the input to
  `poll_eval_run.py --run-id`.
- `poll_eval_run.py` prints one JSON object to stdout on success: the flat
  summary shown above, with `raw` holding the full final `get-run` payload.
  Non-terminal poll progress goes to stderr, not stdout, so stdout is
  always a single clean JSON document when the command exits 0.
- Both helpers exit non-zero with a `SystemExit` message (no partial JSON)
  on any failure -- missing CLI, auth failure, malformed `--prompt`, or
  poll timeout.

## Anti-patterns (do NOT do)

- **Creating an eval run against a data asset that hasn't been
  reviewed/snapshotted first.** This is the most common way this skill
  produces misleading results -- an unreviewed or unrepresentative dataset
  yields a pass/fail signal that looks authoritative but doesn't predict
  production behavior. Confirm the data asset came from a real curation/
  snapshot step (e.g. `capture-traces`) before passing its ID here.
- Passing `--execute` reflexively. It starts real, potentially costly
  evaluation work immediately -- treat it the same way you'd treat any
  other irreversible-cost action: confirm the data asset and prompt
  reference first, create the run without `--execute`, inspect what would
  run, then re-invoke with `--execute` (or use the CLI directly to execute
  the already-created run) once you're sure.
- Reimplementing REST auth in Python for this skill. `stimulir` already
  handles token/workspace headers -- shell out to it, don't hand-roll
  `Authorization` / `X-Business-Profile-Id` headers here.
- Treating `poll_eval_run.py`'s summary as a promotion decision. It reports
  status/score/pass-fail counts; deciding whether that's good enough to
  promote to production is the agent's (and user's) judgment call, not
  something baked into the helper.
- Polling forever. `poll_eval_run.py` has a `--timeout-seconds` default of
  30 minutes and exits non-zero on timeout rather than looping silently --
  don't wrap it in a shell `while true` that ignores that exit code.
- Assuming `passed`/`failed`/`score` field names are guaranteed present.
  The helper reads them defensively from `results`/`summary` and always
  includes the full `raw` payload precisely because the CLI's exact schema
  for those fields hasn't been pinned down here -- read `raw` if the flat
  fields come back `null`.
