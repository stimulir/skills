---
name: rsi
description: Diagnose and measurably improve an application's AI behavior from Stimulir traces using a durable server-side hill climb. Use when the user says RSI; asks to diagnose production failures; wants to improve a prompt from observed traffic; wants to hill-climb quality, latency, or cost; or asks to start, continue, steer, inspect, or review an RSI run.
metadata:
  category: operator
---

# RSI

Turn a short improvement request into a guided workflow against Stimulir's
durable RSI controller. Starting from production traces, the controller owns
trace selection, privacy and eligibility processing, immutable snapshot creation or
reuse, Lab handoff, baseline and candidate measurement, diagnosis, proposals,
lineage memory, comparability, rejection gates and the iteration cap. Do not
reproduce any of those mechanics in the coding agent.

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

## Inspect, resolve and preview

For a new diagnosis, first run the broad read-only inspection:

```bash
stimulir lab rsi inspect --env-file <adopter-env>
```

Use its searchable tag, prompt and model distributions, named folders,
available evaluators and workspace-accessible model candidates to resolve the
request. Do not dump long inventories into the conversation. If inspection
returns typed ambiguities, ask only the unresolved questions that affect the
run; do not re-ask facts the user already supplied or that inspection proved.

The minimum questions, when genuinely unresolved, are:

1. Which workflow/tag or prompt is in scope?
2. Which date window, named cohort, or count should be used?
3. Should RSI test the prompt only, models only, or both?

Imported open-source benchmark records are reference evidence, not observed
model inference. When inspect reports `cohort_kind=open_source_benchmark`, show
the workspace-accessible execution-baseline options it returns and ask for one
only if the user did not already specify it. Pass that exact choice as
`--baseline-model PROVIDER:MODEL` to both preview and run. Never call the
dataset publisher/reference label an inference model. For
`cohort_kind=production_inference`, never pass a baseline override: the server
must reconstruct the incumbent from trace evidence.

Then run the read-only preview with the resolved selectors:

```bash
stimulir lab rsi preview --env-file <adopter-env> <resolved-options>
```

Preview must precede a new run. Summarize total, matched, privacy-eligible and
selected counts; sampling policy; inferred incumbent provider/model and prompt
key/version; evaluator; candidate models; estimated cost and duration; and all
typed ambiguities. Never start when `runnable` is false, even if the user asks
to proceed; return the typed blockers and resolve or re-preview instead. A
preview spends no RSI inference budget and never promotes.

The preview returns `normalized_source`, `cohort_fingerprint`, and
`preview_token`. Treat all three as one integrity-bound handoff. For `run`,
reuse the normalized source exactly: translate its resolved `from`, `to`,
filters, count and sampling fields back to the matching CLI options instead of
re-resolving a relative window, and pass both `--cohort-fingerprint` and
`--preview-token` exactly as returned. Do not edit, synthesize, or reuse either
value across projects, and never print or log the full preview token. If any of the three fields is absent,
report that the CLI/server must be upgraded and do not start.

SDK callers must pass the complete preview handoff:

```python
preview = client.rsi.preview(<resolved selectors>)
if not preview["runnable"]:
    raise RuntimeError(preview.get("blockers") or "RSI preview is not runnable")

started = client.rsi.run(
    normalized_source=preview["normalized_source"],
    cohort_fingerprint=preview["cohort_fingerprint"],
    preview_token=preview["preview_token"],
    prompt_ref="auto",
    max_iterations=1,
)
```

## Choose the action

Map the user's request to one command:

| Intent | Command |
|---|---|
| Inspect available project inputs | `stimulir lab rsi inspect --env-file <adopter-env>` |
| Preview a resolved run without spend | `stimulir lab rsi preview --env-file <adopter-env>` |
| Start a diagnosis or hill climb | `stimulir lab rsi run --env-file <adopter-env>` |
| Read compact progress | `stimulir lab rsi status <rsi-run-id> --env-file <adopter-env>` |
| Inspect lineage and diagnoses | `stimulir lab rsi overview <rsi-run-id> --env-file <adopter-env>` |
| Read the terminal outcome | `stimulir lab rsi results <rsi-run-id> --env-file <adopter-env>` |
| Add an operator constraint when input is required | `stimulir lab rsi continue <rsi-run-id> --env-file <adopter-env>` |

Use `--help` to confirm the installed CLI's exact arguments. Do not guess an
unsupported flag or bypass the CLI with direct REST calls.

For preview and start, translate source scope into the matching command options:

| User language | RSI argument |
|---|---|
| today | `--source-window today` |
| last month, one month, last 30 days | `--source-window 30d` |
| last seven days | `--source-window 7d` |
| explicit date range | `--from <ISO-8601> --to <ISO-8601>` |
| most recent 50 eligible traces | `--count 50 --sampling newest` |
| deterministic sample of 100 | `--count 100 --sampling deterministic_random --sampling-seed <stable-name>` |
| named cohort or Lab folder | `--folder-name <name>` (or exact `--folder-id`) |
| trace tag `assessment`, tagged `assessment`, or tag `assessment` in a trace-scope request | `--trace-tag assessment` |
| traces from prompt key `x` | `--prompt-key x` |
| traces generated by model `x` | `--source-model x` |

Treat each requested trace tag as an exact source-trace filter. `--trace-tag`
filters the cohort; `--tag` only labels the RSI run and must not be substituted
for it. Preserve multiple explicitly requested trace tags as repeated
`--trace-tag` arguments. For example:

```bash
stimulir lab rsi preview --env-file <adopter-env> \
  --source-window 30d --trace-tag assessment --prompt auto \
  --max-iterations 1
```

When preview is runnable, use its normalized exact bounds and selectors with
`rsi run` once, binding the run to that exact preview:

```bash
stimulir lab rsi run --env-file <adopter-env> \
  <normalized exact source options> \
  --cohort-fingerprint <preview.cohort_fingerprint> \
  --preview-token <preview.preview_token> \
  --prompt auto --max-iterations 1
```

Do not run if the preview is non-runnable, stale, belongs to another project,
or its normalized source differs from the proposed run. Re-preview after any
selector, experiment-mode, candidate, evaluator, or source change.

Inspection, preview and start are controller actions, not manual data-pipeline
steps. The agent must not separately capture, clean, snapshot or register the
cohort in Lab. If the installed CLI lacks a required selector, report that an
upgrade is required; never silently broaden the cohort.

Use `--experiment-mode prompt_only` unless the user requests or approves model
exploration. For model exploration use `model_only` or `prompt_and_model` and
only candidates returned by inspection, explicitly supplied by the user, or
admitted by workspace policy. Pass an explicit candidate as repeated
`--candidate-model PROVIDER:MODEL`. Pass `--allow-managed-inference` only when
the workspace exposes it and the user allows it. `hybrie-small`,
`hybrie-mid`, and `hybrie-large` are not defaults and must never be invented.

The baseline is the provider, model, prompt key and prompt version reconstructed
from the selected production traces. Never pass or imply a fallback baseline.
Preserve `baseline_model_unresolved`, mixed-incumbent and prompt ambiguity
blockers instead of substituting a Stimulir-managed model.

For an imported benchmark only, preserve the pinned dataset source provenance
while using the explicitly selected `experiments.baseline_model` to execute the
production-labelled demo prompt. Preserve typed
`benchmark_execution_baseline_required`,
`benchmark_execution_baseline_unavailable`,
`benchmark_execution_baseline_override_not_allowed`, and mixed-cohort blockers
instead of guessing or widening the cohort.

The server owns proposer mechanics. Never ask the user to invent a rationale,
create a prompt file, export a workspace, or repeat the CLI sequence manually.
Only pass `--instruction` when the user supplied a real constraint.

## Defaults

Unless the user says otherwise:

- use diagnostic mode;
- let the controller infer the prompt target;
- honor the requested source window and exact trace filters;
- use deterministic, explicit count/sampling controls when the user supplied a count;
- keep model exploration off unless requested or approved;
- do not promote, relabel or edit application code;
- detach after the run command returns.

Starting or resuming can spend inference and judging budget. Report any spend
or blocker returned by the controller. Status and overview are read-only.

## Monitor only when requested

When the user says `wait until done`, `stay with it`, `babysit`, `keep
checking`, or otherwise explicitly asks for a terminal outcome, keep the agent
turn active and monitor automatically:

1. Start once, retain the returned RSI id, and use `status` at the server's
   `recommended_check_seconds` interval (30-60 seconds when absent).
2. Make each check quick and non-blocking. Never use `watch`, `tail -f`, a
   streaming shell command, or a blocking task-output call.
3. Heed `agent_guidance`, `recommended_check_seconds`, `terminal`, and typed
   blockers. Prioritize any new user message before the next check.
4. Do not call `continue` for normal iteration advancement. The durable server
   controller owns baseline -> diagnosis -> proposal -> comparison -> stopping.
5. Stop monitoring at `completed`, `needs_input`, `failed`, or `stopped`. On
   `completed`, call `results` once and report the evidence. On `needs_input`,
   return the exact blocker and ask only for the missing decision.

Monitoring is observational. If the agent process disconnects, the controller
must continue server-side and a later invocation can resume monitoring by id.

When the host supports subagents, terminal intent may be delegated to one
watcher subagent. Give it only the RSI id, adopter env-file path, resolved
project/environment, and this observational protocol. It may call `status`,
then `results` once at completion; it must not call `continue`, mutate the run,
promote, or reinterpret evidence. The parent agent remains responsible for
contextualizing the returned evidence against the user's application and
original request. If subagents are unavailable, the parent performs the same
bounded non-blocking checks. The workflow must never require subagent support.

## Boundaries

- Default starts execute one RSI command and detach. Explicit terminal-intent
  requests may perform the bounded non-blocking monitoring sequence above.
- Never recursively resume or use agent polling to drive normal iterations.
- Never invoke `capture-traces`, `privacy-layer`, `eval-run`, `eval-iterate`,
  `eval-promote`, `prompt-versioning` or another skill.
- Never manually create a data asset, Lab folder, snapshot, eval or derive
  stage. A missing immutable snapshot is not a user prerequisite: the RSI
  controller must create or reuse it from the requested traces. If the server
  still returns that legacy prerequisite, report an incompatible server
  deployment rather than asking the user to perform the workflow manually.
- Never start without a runnable preview and its unchanged normalized source,
  cohort fingerprint, and preview token. Never bypass a preview-integrity
  rejection with a fresh unreviewed run payload.
- Never promote a candidate. Promotion is a separate, explicitly authorized
  human-gated action outside this skill.
- Never change the adopter's prompt or source code.

## Return

Report the RSI run id and state, resolved environment and project, source
window and exact trace filters, matched trace count, eligible and excluded
counts, immutable snapshot id and whether it was created or reused, target
prompt, reconstructed incumbent provider/model/prompt version, experiment
mode and explicit model candidates, current diagnosis or champion when
available, cohort fingerprint, preview token, spend, and the console link.
Do not print the full preview token; report only that it was bound. Preserve any typed
blocker returned by the controller, especially
`no_matching_traces`, `all_traces_excluded`, `prompt_target_ambiguous`,
`baseline_model_unresolved`, `privacy_processing_failed`, and
`budget_exhausted`. If a field is not yet
available, say so rather than inventing it. Do not claim improvement until
comparable completed evidence supports it, and explicitly confirm that no
promotion occurred.

At terminal completion, the parent agent—not a watcher—must contextualize the
result: what production behavior failed; representative failing cases; whether
evidence attributes the failure to prompt, model, data, tool or evaluator;
which controlled prompt-only/model-only/combined experiments ran; quality,
cost and latency deltas against the exact production incumbent; rejected
candidates and reasons; and the next human review step. Do not attribute a
prompt gain to a simultaneous model change. If interrupted, return the stable
RSI id, state, console link and exact `status`/`results` commands so another
agent invocation can resume the handoff without restarting the run.
