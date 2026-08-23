---
name: usage-audit
description: Report bounded, read-only Stimulir usage and billing totals. Use for cost, spend, metering, or reconciliation questions. Defaults to typed aggregates; raw event access is an explicit bounded file export that is never loaded into agent context.
metadata:
  category: operator
---

# Usage Audit

Use typed aggregates by default.

## Reconcile

```bash
stimulir billing reconcile --json
```

Report period, requests, token totals, GBP cost, meter-event count, unmetered-event count, and status. Do not call raw billing or usage endpoints.

For grouped operational usage, use `stimulir usage --window <7d|30d|month> --group-by <provider|model|day>` and report aggregates only.

## Explicit forensic export

Export events only when the user specifically requests event-level reconciliation and names a destination:

```bash
stimulir billing export-events --output <path> --limit <1-500>
```

The CLI writes a bounded allow-listed projection to the file. Do not open, paste, summarize, or feed that file into agent context unless the user separately requests analysis and confirms the scope. Report only the file path and exported count.

## Boundaries

- Read-only; never change limits, plans, keys, routing, or billing state.
- Never use direct REST fallbacks.
- Never expose request bodies, prompts, customer content, credentials, or raw server errors.
