---
name: usage-audit
description: Get cost-per-task visibility into stimulir spend -- aggregated usage summaries, raw usage events for reconciliation, and account-level billing snapshots. Use whenever the user asks what something cost, wants a spend breakdown by model/task/agent, needs to audit or reconcile billing, or wants this running alongside another skill/pipeline to track its cost as it runs. Entirely read-only.
---

# Usage Audit

Cost-per-task visibility into stimulir spend, matching stimulir's own "see
what every task costs" value prop. Wraps three read-only surfaces: an
aggregated usage summary, the raw usage-event ledger, and an account-level
billing snapshot. No side effects anywhere in this skill -- it never
creates, modifies, or deletes anything in the account it reports on.

## Placement rationale

This skill is ONGOING, not sequential. It does not sit at a fixed stage in
some other skill's pipeline -- it runs *alongside* whatever else is
happening (another skill's multi-step workflow, a long agent session, a
scheduled job) to answer "what has this cost so far" at any point, and
again at the end to close out the picture. Invoke it:

- Before a costly run, to check current billing-account headroom
  (`billing_snapshot.py`).
- Periodically during a long-running or multi-stage task, to watch spend
  accumulate (`usage_summary.py` with a short `--window`).
- After a run, to get a final per-model/per-task cost breakdown and
  reconcile it against the raw event ledger (`usage_summary.py` +
  `usage_events.py`).

This skill assumes `connect` has already run -- the `stimulir` CLI is
installed, authenticated, and pointed at the right workspace. That setup is
not re-documented here; see `install.md` for the one-time bootstrap this
skill itself needs (Python deps only) if `connect` hasn't been run yet.

## Read-only, always

Every helper in this skill is a GET-shaped read against stimulir's own
usage/billing surfaces. Nothing here creates a resource, spends money,
mutates billing state, or writes back to the account. There is no
`--confirm` flag anywhere in this skill because there is no irreversible or
costly action to gate -- reporting on spend is inherently safe to run as
often as needed.

## Preflight

```bash
which stimulir && stimulir --version
python3 -c "import httpx; print('httpx ok')"
```

`usage_summary.py` and `billing_snapshot.py` require the `stimulir` CLI on
`PATH` and already authenticated (`~/.stimulir/` session cache from
`connect`) -- they refuse to run and fail loudly if the binary is missing.
`usage_events.py` prefers the CLI too, but falls back to a direct REST call
(`STIMULIR_API_KEY` + `STIMULIR_API_URL`) if the installed CLI version has
no `usage events` subcommand -- see "CLI reference" below.

## The pipeline

This isn't a linear pipeline with an end state -- it's three independent,
composable read calls. Use whichever answers the question being asked;
combine them for a real audit.

```
usage_summary.py    →  aggregated spend for one window, grouped by
                        model / task / agent / day (server-computed)
usage_events.py     →  raw per-event ledger for the same window
                        (itemized, for re-summing and reconciliation)
billing_snapshot.py →  current account state: balance, plan, spend-to-date,
                        active limits/alerts (not windowed -- "right now")
```

A real audit is: pull the summary for the window in question, pull the raw
events for the same window, independently re-sum the events by the same
grouping key, and diff the two totals. If they don't match (or don't match
within a documented rounding/timing tolerance the CLI itself states), say so
explicitly rather than reporting only the summary number.

## CLI reference

```bash
# aggregated summary, default window 30d, grouped by model
python helpers/usage_summary.py --window 30d --group-by model

# other useful group-by dimensions (whatever stimulir usage supports)
python helpers/usage_summary.py --window 7d --group-by task
python helpers/usage_summary.py --window 24h --group-by agent

# raw usage events for the same window, for reconciliation
python helpers/usage_events.py --window 30d
python helpers/usage_events.py --window 30d --group-by model --limit 500
python helpers/usage_events.py --window 30d --cursor "<next_cursor from previous call>"

# account-level billing snapshot (not windowed)
python helpers/billing_snapshot.py

# write any of the above straight to a file for later diffing
python helpers/usage_summary.py --window 30d --group-by model --out /tmp/summary.json
python helpers/usage_events.py --window 30d --out /tmp/events.json
```

All three helpers print JSON to stdout (or to `--out` if given) and exit
non-zero with a clear message on failure -- missing `stimulir` binary,
missing/invalid auth, a non-200 REST response, or unparsable output. None
of them retry silently or swallow an error into an empty result.

### Underlying surfaces

| Helper | Wraps | REST equivalent |
|---|---|---|
| `usage_summary.py` | `stimulir usage --window --group-by --json` | `GET /api/v1/usage/summary?window=&group_by=` |
| `usage_events.py` | `stimulir usage events --json` (CLI-first, REST fallback) | `GET /api/v1/usage/events` |
| `billing_snapshot.py` | `stimulir billing snapshot --json` | `GET /api/v1/billing/hybrie/snapshot` |

## Output contract

Every helper re-emits the underlying CLI/REST payload's JSON verbatim --
this skill does not reshape, rename, or drop fields. Treat the shape as
whatever the installed `stimulir` CLI version returns; do not hardcode
assumptions about specific field names beyond what's needed to sum costs
and group keys, since the CLI's exact schema is authoritative, not this
skill's docs. `usage_events.py`'s payload may include a pagination cursor
(commonly `next_cursor` or similar) -- if the first page looks truncated
relative to the summary's totals, page through with `--cursor` rather than
reporting a partial reconciliation as final.

## Anti-patterns (do NOT do)

- **Treating a single `usage_summary.py` window as authoritative without
  cross-checking `usage_events.py`.** A summary is a server-computed
  aggregate; it can lag, double-count across overlapping windows, or bucket
  differently than expected. A real audit always cross-checks the raw event
  ledger for the same window before reporting a number as final.
- Reporting only the first page of `usage_events.py` as the full ledger
  when the response carries a pagination cursor. Page through fully before
  reconciling totals, or say explicitly that the reconciliation is partial.
- Confusing `billing_snapshot.py` (account state right now) with
  `usage_summary.py` (spend over a window). They answer different
  questions and are not interchangeable -- don't report a billing balance
  as if it were a windowed cost breakdown or vice versa.
- Calling any helper without the `stimulir` CLI authenticated first (i.e.
  before `connect` has run). These helpers do not perform their own login
  flow and will fail loudly rather than prompting for credentials.
- Adding write/mutation capability to this skill. It exists specifically as
  the read-only cost-visibility layer that runs alongside everything else
  -- any action with side effects belongs in a different, explicitly
  side-effecting skill, not bolted onto this one.
