---
name: connect
description: Stage 0 of stimulir client onboarding -- get from zero to a working, authenticated, cost-visible connection to stimulir in minutes (install the CLI, authenticate, select a workspace, send one real inference call, see its cost). Use when a user has no stimulir CLI set up yet, asks to "connect to stimulir" / "onboard to stimulir" / "get stimulir working", or any other stimulir skill's preflight reports the CLI missing or unauthenticated.
---

# Connect

Stage 0, and only Stage 0: get from a machine with nothing on it to a
working, authenticated, cost-visible connection to stimulir. This mirrors
stimulir's own marketing bar -- "self-onboard in minutes... send a real task,
see the result and the cost" -- and this skill's job is to make that literal
sequence happen, not to build anything on top of it.

Every other stimulir-integrated skill in this collection assumes `connect`
has already run: CLI installed, authenticated, workspace selected. Don't
re-derive that setup inside another skill's preflight -- point back here
instead.

## Placement rationale

This is the front door, not a feature. It deliberately does three things and
stops:

1. **Verify** the environment (read-only, safe to run any number of times).
2. **Bootstrap** up to the first gate that needs a human -- login is
   interactive by design (device-flow browser approval), so this skill
   reports the exact command to run and stops, it never runs it itself.
3. **Prove the loop** with one real inference call and one real usage query,
   once auth + workspace are in place.

What it explicitly does NOT do: create API keys automatically, pick a
workspace on the user's behalf when more than one exists, wire the key into
any adopter's source code (that is `migrate-inference`'s job, a different
skill), or manage ongoing usage/billing dashboards. Stage 0 ends the moment
the user can see one real response and its real cost.

## Capability tiers

| Capability | Status |
|---|---|
| Check install/auth/workspace state | Self-contained, fully read-only, safe to re-run anytime |
| Bootstrap up to the first human-required gate | Read-only checks only; stops and prints the exact command for login/workspace selection rather than running it |
| Create an inference API key | Real, billable, irreversible-ish action (revocable, not un-creatable) -- the agent's explicit, confirmed step, never automatic |
| Send one real inference call + read real usage | Real hosted call against the stimulir gateway -- needs an authenticated session and a selected workspace |

## Preflight

```bash
python3 --version   # 3.10+
which stimulir       # may legitimately be empty on a fresh machine -- that's the case this skill exists for
```

Do not assume the CLI is installed or authenticated just because this skill
is present -- that is precisely the state `check_environment.py` exists to
discover. Run it first, every time, before deciding what to do next.

## The workflow

```
1. helpers/check_environment.py   ->  read-only snapshot: CLI installed?
                                       version? authenticated? which
                                       workspace (if any) is selected?
2. helpers/bootstrap.py           ->  same checks, plus ONE next-action
                                       decision: install, login, or select
                                       a workspace. Stops at the first gate
                                       that needs a human and prints the
                                       exact command -- never runs it.
3. (human/agent runs the printed command -- `stimulir login`,
    `stimulir workspace use <id>`, etc. -- then re-run step 2 to confirm)
4. stimulir keys create --name <name> --env dev   -- the agent runs this
   itself, directly, ONLY after explicit user confirmation (see
   "Anti-patterns"). The plaintext key is shown exactly once; print it to
   the user once, do not log it or write it to a file yourself.
5. helpers/smoke_test.py          ->  one real `stimulir infer chat` call
                                       + one real `stimulir usage` query,
                                       proving "send a real task, see the
                                       cost" end to end.
```

Steps 1-2 can run any number of times with zero side effects -- treat them
as the default way to check "are we ready yet" after every human action in
step 3. Step 4 is the one genuinely irreversible-feeling action in this
skill (a real credential, real spend potential) -- see "Anti-patterns"
before running it.

### 1-2. Check + bootstrap

```bash
python3 helpers/check_environment.py
python3 helpers/bootstrap.py
```

`bootstrap.py` imports `check_environment.py`'s functions directly (no
subprocess-of-a-subprocess) and adds exactly one more read: the
`workspace_id` persisted at `~/.stimulir/config.json` by a prior `stimulir
workspace use`. This is the CLI's actual mechanism for remembering the
active workspace -- confirmed directly against the file; `stimulir
workspace list --json` itself does NOT mark which one is active (only the
human-readable table view does, with a `●` column that has no JSON
counterpart). Only that one non-secret field is read; this skill never
opens `~/.stimulir/credentials.json` (the cached session token).

`bootstrap.py`'s output always has a `next_step` object:

```json
{
  "stage": "login",
  "done": false,
  "next_command": "stimulir login",
  "reason": "Not authenticated (or the cached 30-day session expired). ..."
}
```

Read `next_step.reason` to the user, tell them (or, with explicit
confirmation, run) `next_step.next_command`, then re-run `bootstrap.py` to
confirm the gate cleared before moving to the next stage. When
`next_step.stage == "workspace"` and `next_step.done == true`,
`ready_for_key_and_smoke_test` is `true` and it's safe to move to step 4.

### 3. Interactive gates (the human's turn)

Two stages in this workflow are inherently interactive and this skill will
never automate them:

- **`stimulir login`** -- opens a browser device-approval page. The 30-day
  cached token then lives in `~/.stimulir/`. For headless/CI environments,
  `stimulir login --token <token>` accepts a pre-issued `stim_cli_` token
  instead (Settings -> CLI Tokens in the console) -- but the token itself
  still has to come from a human pasting it, this skill does not generate
  or fetch one on the caller's behalf.
- **`stimulir workspace use <id>`** -- when `bootstrap.py` reports more than
  one workspace and none selected, it lists every candidate id/name in
  `checks.auth.workspaces`. Ask the user which one before running `use`
  yourself -- don't guess based on list order or name-matching heuristics.

### 4. Create an inference key (agent action, confirm first)

```bash
stimulir keys create --name <descriptive-name> --env dev
```

Run this directly (it is not wrapped in a helper -- see "Anti-patterns" for
why). `--env dev` is the sane default for a Stage-0 connection; ask before
using `--env staging` or `--env prod`. Consider `--credit-limit-pence <n>`
for a hard spend cap on the new key -- worth surfacing to the user
explicitly for a first-time connection, since it bounds the blast radius of
whatever consumes the key next. **Never pass `--save`**: that flag writes
the plaintext key to `~/.stimulir/credentials` for `stimulir infer` to reuse
automatically, which is a second, separate place a secret would live beyond
"shown once to the user." Print the key to the user once, then let it fall
out of scope -- do not log it, write it to a file, or echo it into a
subsequent command's shell history.

### 5. Prove the loop: one real task, one real cost

```bash
python3 helpers/smoke_test.py --model <model-id>
```

Sends `stimulir infer chat "<prompt>" --model <model-id> --json` (one real,
billable call), then `stimulir usage --window 30d --group-by model --json`
(a real read of the workspace's aggregated spend), and prints both as one
JSON report.

**`--model` has no default and is required.** The model catalog from
`stimulir models --json` is workspace-specific, and — confirmed directly
against a live workspace — not every id it lists is actually routable
through `infer chat` on that same workspace (a model can appear in the
catalog and still 404 with `unknown_model` when you try to run it). Run
`stimulir models --json` first, or read a model id straight out of an
existing `stimulir usage` response, and pass a confirmed-working id.

## CLI reference

```bash
# install / upgrade
uv tool install stimulir
uvx stimulir --help
uv tool upgrade stimulir

# auth
stimulir login                       # interactive device flow, 30-day cached token
stimulir login --token <stim_cli_>   # headless/CI, token from Settings -> CLI Tokens
stimulir logout --remote             # revoke server-side + clear local

# workspace
stimulir workspace list --json
stimulir workspace use <id>

# keys (plaintext shown once -- never pass --save from this skill)
stimulir keys create --name <name> --env dev [--credit-limit-pence <n>]

# smoke test
stimulir models --json
stimulir infer chat "<prompt>" --model <id> --json
stimulir infer chat "<prompt>" --model <id> --stream   # interactive human verification

# cost visibility
stimulir usage --window 30d --group-by model --json     # window: 7d|30d|month
```

## Output contract

`check_environment.py` and `bootstrap.py` print one JSON object to stdout,
always exit 0 (an unmet gate is a normal finding, not a crash):

```json
{
  "cli": {"installed": true, "path": "...", "version": "stimulir 0.1.0"},
  "auth": {"authenticated": true, "workspaces": [{"id": "...", "name": "..."}]},
  "workspace": {"active_workspace_id": "...", "config_path": "~/.stimulir/config.json"},
  "ready": true,
  "missing": []
}
```

`bootstrap.py` wraps that under `checks` and adds `next_step` +
`ready_for_key_and_smoke_test` (see step 1-2 above for the `next_step`
shape).

`smoke_test.py` prints one JSON object and exits non-zero with a clear
stderr message on any failure (missing CLI, not authenticated, bad model
id, non-JSON CLI output):

```json
{
  "ok": true,
  "inference": {"command": [...], "model": "...", "prompt": "...", "response": { "...": "full stimulir infer chat --json payload, including usage.{prompt,completion,total}_tokens" }},
  "usage": {"command": [...], "window": "30d", "usage": { "points": [...], "totals": {"cost_gbp": 0.0, "requests": 0}, "meta": {...} }}
}
```

## Anti-patterns (do NOT do)

- **Running `stimulir login` non-interactively from a helper.** Login is a
  device-flow browser approval by design -- there is no dry-run or
  auto-approve path this skill should invent. `bootstrap.py` only ever
  prints the command; the human (or the agent, with explicit confirmation)
  runs it themselves.
- **Guessing which workspace to select** when `bootstrap.py` reports more
  than one candidate. List them, ask the user, then run `stimulir workspace
  use <id>` -- don't pick the first one, the most recently created one, or
  one matching a name heuristic.
- **Wrapping `stimulir keys create` in a helper that runs by default.**
  Creating a key is a real, billable, mostly-irreversible action (revocable
  but not un-creatable, and it can accrue spend the moment it's used). This
  skill runs it as a direct, visible CLI command the agent types after the
  user has explicitly said yes -- not something a `--dry-run`-lacking script
  can quietly execute as part of a bigger pipeline.
- **Passing `--save` to `stimulir keys create`.** That flag persists the
  plaintext key to `~/.stimulir/credentials` for CLI reuse -- a second
  storage location beyond "shown once." This skill's job is to show the key
  once and stop, not to give it a second home.
- **Hardcoding a model id in `smoke_test.py` or a wrapper around it.** Model
  catalogs are workspace-specific and catalog membership does not guarantee
  `infer chat` routability (confirmed directly: `stimulir models --json` can
  list an id that then 404s with `unknown_model` from `infer chat` on the
  same workspace). Always resolve a model id live (`stimulir models --json`
  or an existing `usage` breakdown) rather than trusting a name from
  documentation or a past session.
- **Treating a non-zero exit from `check_environment.py` or `bootstrap.py`
  as a bug.** Both always exit 0 on a clean run -- "not authenticated" or
  "no CLI" are expected findings in their `missing` list, not helper
  failures. Only `smoke_test.py` uses a non-zero exit as a real failure
  signal, because it performs the actual billable/authenticated action.
- **Re-deriving this skill's checks inside another skill.** Every other
  stimulir-integrated skill should assume `connect` already ran and simply
  fail loudly if a real call 401s -- pointing back at this skill, not
  reimplementing install/auth/workspace probing locally.
- **Reading `~/.stimulir/credentials.json`.** This skill never needs the
  cached session token directly -- `stimulir workspace list --json`
  succeeding is sufficient proof of a live session, and the active
  workspace comes from the separate, non-secret `config.json`. There is no
  reason for any helper here to open the credentials file.
