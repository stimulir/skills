# connect

Stage 0 of stimulir client onboarding for Codex / Claude Code -- get from a
machine with nothing installed to a working, authenticated, cost-visible
connection to stimulir in minutes. Wraps the real `stimulir` CLI
(install → `stimulir login` → `stimulir workspace use` → `stimulir keys
create` → `stimulir infer chat` → `stimulir usage`) with read-only
verification helpers that never run the interactive or billable steps
themselves -- they check state, report the exact next command, and stop.

## Why

- Every other stimulir-integrated skill assumes this one already ran --
  `connect` is the one place install/auth/workspace bootstrapping lives.
- Read-only by default: `check_environment.py` and `bootstrap.py` can be run
  any number of times with zero side effects, and always exit 0 (an unmet
  gate is a normal finding, not a crash).
- Interactive/billable steps (`stimulir login`, `stimulir keys create`) are
  never silently automated -- this skill prints the exact command and stops,
  the agent runs it directly only with explicit user confirmation.
- Proves the actual value prop end to end: one real inference call, one real
  usage query, in the same JSON report -- "send a real task, see the result
  and the cost."

## Quick start

```bash
# 1. read-only environment check
python3 helpers/check_environment.py

# 2. same checks + one next-action decision (install / login / workspace)
python3 helpers/bootstrap.py
# -> follow next_step.reason, run next_step.next_command yourself if it
#    requires human interaction (login, workspace selection), then re-run
#    this to confirm the gate cleared

# 3. create an inference key directly (only after explicit user confirmation)
stimulir keys create --name my-first-key --env dev

# 4. prove the loop: one real inference call + one real usage query
python3 helpers/smoke_test.py --model <model-id-confirmed-for-this-workspace>
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including exactly which
steps this skill will and will not automate) and [`install.md`](./install.md)
for first-time setup.
