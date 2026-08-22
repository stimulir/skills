---
name: connect
description: Prepare a local machine to use the Stimulir CLI through read-only install, authentication, and workspace checks. Use when onboarding to Stimulir, repairing CLI authentication or workspace selection, or when another Stimulir skill reports that its connection preflight failed. This skill never creates credentials, handles secrets, authorizes spend, or makes billable inference calls.
metadata:
  category: operator
---

# Connect

Establish a ready CLI context without touching credentials or spend. Stop when
the CLI is installed, authentication is valid, and the intended workspace is
selected.

## Security contract

- Run only read-only checks from this skill.
- Never create, display, copy, persist, or return an API key or session token.
- Never make an inference call or authorize spend.
- Never read `~/.stimulir/credentials.json`.
- Treat login and workspace selection as visible human-controlled actions.
- Route credential setup to the Console. Route an explicitly requested test
  inference to the relevant inference workflow, outside this skill.

## Workflow

1. Inspect the environment:

   ```bash
   python3 helpers/check_environment.py
   ```

2. Obtain the next safe action:

   ```bash
   python3 helpers/bootstrap.py
   ```

3. If installation is missing, show the reported install command and obtain
   confirmation before installing software.
4. If authentication is missing, ask the human to complete `stimulir login`.
   Never accept or repeat a token in chat.
5. If workspace selection is missing, show the available workspaces and ask
   the human which one to select. Do not infer the choice.
6. Re-run both helpers. Finish only when `ready` is `true`.

The helpers may be re-run safely. They call only `stimulir --version` and
`stimulir workspace list --json`, and read only the non-secret `workspace_id`
from `~/.stimulir/config.json`.

## Human-controlled commands

These commands may be presented as the next step, but must not be hidden in a
helper or run without the human's direction:

```bash
uv tool install stimulir
uv tool upgrade stimulir
stimulir login
stimulir workspace list --json
stimulir workspace use <id>
```

For headless environments, direct the human to the Console's CLI-token flow.
Do not ask them to paste a token into the conversation and do not construct a
command containing a token.

## Output

`check_environment.py` returns the CLI, authentication, workspace, `ready`,
and `missing` fields. `bootstrap.py` returns the same checks plus exactly one
`next_step` and a top-level `ready` boolean. An unmet gate is a normal result,
so both helpers exit successfully when they can report it.

Return:

- CLI path and version;
- authentication status without token material;
- selected workspace ID and available workspace names;
- the single next human action, or confirmation that the connection is ready.

## Boundaries

- Do not run credential creation commands from this skill.
- Do not call inference or usage/spend commands from this skill.
- Do not install a provider credential; use `byok-register` for its
  human-controlled Console handoff and read-only verification.
- Do not reimplement CLI authentication or make direct REST requests.
