---
name: rsi
description: Diagnose and measurably improve an application's AI behavior from Stimulir traces using a durable server-side hill climb. Use when the user says RSI; asks to diagnose production failures; wants to improve a prompt from observed traffic; wants to hill-climb quality, latency, or cost; or asks to start, continue, steer, inspect, or review an RSI run.
metadata:
  category: operator
---

# RSI

Turn a short improvement request into one action against Stimulir's durable
RSI controller. The controller owns immutable-cohort selection, baseline and
candidate measurement, lineage memory, comparability, rejection gates and the
iteration cap. In this explicit-proposer release, the coding agent diagnoses a
completed measurement and supplies one rationale plus one complete candidate
prompt when resuming. Do not reproduce eval construction or lineage mechanics.

## Resolve the target safely

Work from the adopter repository. Read its Stimulir environment and project
configuration without printing secrets. Resolve the requested API base,
workspace and project, then compare them with the active CLI context before
spending anything.

- Refuse an API-base, workspace or project mismatch.
- Never silently fall back between production and staging.
- When the user says production, require the production API base.
- If context is missing or unauthorized, report the exact mismatch and stop.

Assume `connect` has already installed and authenticated the CLI. Do not invoke
that or any other skill from this skill.

## Choose exactly one action

Map the user's request to one command:

| Intent | Command |
|---|---|
| Start a diagnosis or hill climb | `stimulir lab rsi run` |
| Read compact progress | `stimulir lab rsi status <rsi-run-id>` |
| Inspect lineage and diagnoses | `stimulir lab rsi overview <rsi-run-id>` |
| Continue a ready run | `stimulir lab rsi resume <rsi-run-id> --rationale "..." --prompt-file <file>` |

Use `--help` to confirm the installed CLI's exact arguments. Do not guess an
unsupported flag or bypass the CLI with direct REST calls.

## Defaults

Unless the user says otherwise:

- use diagnostic mode;
- let the controller infer the prompt target;
- honor an explicitly requested trace cohort such as `today`;
- do not promote, relabel or edit application code;
- detach after the one command returns.

Starting or resuming can spend inference and judging budget. Report any spend
or blocker returned by the controller. Status and overview are read-only.

## Boundaries

- Execute one RSI command per invocation, then return.
- Never poll, wait in a loop or recursively resume.
- Never invoke `capture-traces`, `privacy-layer`, `eval-run`, `eval-iterate`,
  `eval-promote`, `prompt-versioning` or another skill.
- Never manually recreate the controller's eval or derive stages. If `run`
  reports that no immutable cohort exists, report that prerequisite; this
  release does not curate raw traces inside RSI.
- Never promote a candidate. Promotion is a separate, explicitly authorized
  human-gated action outside this skill.
- Never change the adopter's prompt or source code.

## Return

Report the RSI run id and state, resolved environment and project, trace cohort
and snapshot, target prompt, current diagnosis or champion when available,
spend when returned, blockers or required intervention, and the console link.
Do not claim improvement until comparable completed evidence supports it.
