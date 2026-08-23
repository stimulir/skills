---
name: connect
description: Prepare a machine to use the Stimulir CLI through read-only install, authentication, and workspace-selection checks. Use for onboarding or repairing CLI readiness. Never creates credentials, handles secrets, runs inference, or authorizes spend.
metadata:
  category: operator
---

# Connect

Establish CLI readiness through visible, human-controlled steps.

## Safety contract

- Run only `stimulir --version` and `stimulir workspace list --json` as checks.
- Never print raw command output, errors, workspace names, tokens, or credentials.
- Never read `~/.stimulir/credentials.json`.
- Never create keys, call inference, inspect usage, or authorize spend.
- Treat login and workspace selection as human-controlled actions.

## Workflow

1. Run `stimulir --version`. Report only whether the CLI exists and its version.
2. Run `stimulir workspace list --json` and parse it locally. Report only:
   - whether authentication succeeded;
   - workspace count;
   - workspace IDs.
   Do not reproduce workspace names, raw output, or error bodies.
3. If installation is missing, offer `uv tool install stimulir` or `pipx install stimulir` and obtain confirmation before installing.
4. If authentication is missing, ask the human to run `stimulir login`. Never accept a token in chat.
5. If no workspace is selected, ask which workspace ID to use, then run `stimulir workspace use <id>` only after the human chooses it.
6. Re-run the two read-only checks once and report readiness.

If output is malformed, report the stable blocker `unexpected_cli_response`; do not expose or interpret the raw response.

## Boundaries

- Route provider credentials to `byok-register`.
- Route inference tests to the relevant inference workflow.
- Do not call REST directly or reimplement authentication.
