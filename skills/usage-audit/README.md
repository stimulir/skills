# usage-audit

Read-only cost-per-task visibility into stimulir spend for Codex / Claude
Code / future Stimulir code-runtime -- an aggregated usage summary, the raw
usage-event ledger for reconciliation, and an account-level billing
snapshot, all wrapping the real `stimulir` CLI/REST surface. Runs alongside
every other stage rather than sitting at a fixed point in a pipeline --
matches stimulir's own "see what every task costs" value prop.

## Why

- Ongoing, not sequential: check spend before a costly run, watch it
  accumulate mid-run, and close out with a reconciled total after --
  the same three helpers answer all three moments.
- CLI-first: shells out to `stimulir usage`/`stimulir billing snapshot`
  rather than reimplementing REST auth, so it reuses the session cache
  `connect` already set up in `~/.stimulir/`.
- Entirely read-only: no helper here creates, mutates, or spends anything.
  Every call is a GET-shaped report.
- Audit-honest: a single summary window is never treated as the final
  answer -- `usage_events.py` exists specifically so the raw ledger can be
  independently re-summed and cross-checked against the summary.

## Quick start

```bash
# 1. aggregated spend for the last 30 days, grouped by model
python helpers/usage_summary.py --window 30d --group-by model

# 2. raw usage events for the same window, for reconciliation
python helpers/usage_events.py --window 30d

# 3. current billing-account state (balance, plan, spend-to-date)
python helpers/billing_snapshot.py
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including how to
reconcile a summary against raw events for a real audit) and
[`install.md`](./install.md) for setup.

## Surfaces wrapped

| Helper | Wraps | REST equivalent |
|---|---|---|
| `usage_summary.py` | `stimulir usage --window --group-by --json` | `GET /api/v1/usage/summary?window=&group_by=` |
| `usage_events.py` | `stimulir usage events --json` (CLI-first, REST fallback) | `GET /api/v1/usage/events` |
| `billing_snapshot.py` | `stimulir billing snapshot --json` | `GET /api/v1/billing/hybrie/snapshot` |
