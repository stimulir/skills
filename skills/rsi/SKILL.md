---
name: rsi
description: Diagnose and measurably improve an application's AI behavior from Stimulir traces using a durable server-side hill climb. Use when the user says RSI; asks to diagnose production failures; wants to improve a prompt from observed traffic; wants to hill-climb quality, latency, or cost; or asks to start, continue, steer, inspect, or review an RSI run.
metadata:
  category: operator
---

# RSI

Turn a short improvement request into one action against Stimulir's durable
RSI controller. The controller owns immutable-cohort selection, baseline and
candidate measurement, diagnosis, candidate proposals, lineage memory,
comparability, rejection gates and the iteration cap. Do not reproduce eval
construction, proposal generation or lineage mechanics.

## Resolve the target safely

Work from the adopter repository. Read its Stimulir environment and project
configuration without printing secrets. Prefer the adopter application's
`STIMULIR_API_KEY`, API base and project over any saved human CLI login. Locate
the nearest relevant dotenv file (for example `backend/.env`) and pass it with
`--env-file`; do not source it or place its values in command arguments.

- A workspace-pinned application key does not require a separate workspace
  export or `stimulir login`; the server derives its workspace from the key.
- Refuse an API-base, workspace or project mismatch.
- Never silently fall back between production and staging.
- When the user says production, require the production API base.
- If app context is missing or unauthorized, report the exact mismatch and
  stop. Do not repair it by switching an ambient human login.

Do not invoke `connect` or any other skill from this skill.

## Choose exactly one action

Map the user's request to one command:

| Intent | Command |
|---|---|
| Start a diagnosis or hill climb | `stimulir lab rsi run --env-file <adopter-env>` |
| Read compact progress | `stimulir lab rsi status <rsi-run-id> --env-file <adopter-env>` |
| Inspect lineage and diagnoses | `stimulir lab rsi overview <rsi-run-id> --env-file <adopter-env>` |
| Continue a ready run | `stimulir lab rsi continue <rsi-run-id> --env-file <adopter-env>` |

Use `--help` to confirm the installed CLI's exact arguments. Do not guess an
unsupported flag or bypass the CLI with direct REST calls.

The server owns proposer mechanics. Never ask the user to invent a rationale,
create a prompt file, export a workspace, or repeat the CLI sequence manually.
Only pass `--instruction` when the user supplied a real constraint.

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
