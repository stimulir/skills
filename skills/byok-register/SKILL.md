---
name: byok-register
description: Guide a human through registering an existing provider credential in the Stimulir Console, then inspect and verify the resulting credential without accessing its secret. Use when an adopter wants to connect OpenAI, Anthropic, Gemini, Mistral, Bedrock, Azure OpenAI, Together AI, or Nebius as BYOK. Secret entry is always human-only in the Console; this skill never reads, receives, transmits, logs, or stores raw provider keys.
metadata:
  category: operator
---

# BYOK Register

Help the human register their provider credential through the Stimulir Console,
then verify the resulting non-secret credential record from the CLI.

## Security contract

- Never ask for a raw provider key in chat.
- Never read a provider key from an environment variable, file, clipboard, or
  command argument.
- Never pass a provider key to a helper, subprocess, CLI, or HTTP request.
- Never display, log, transform, or persist secret material.
- Never remove or rotate a credential from this skill.
- Secret entry occurs only in the human-controlled Stimulir Console form.

## Preflight

```bash
which stimulir && stimulir --version
stimulir whoami
```

If authentication or workspace selection is missing, stop and route to
`connect`. Do not repair authentication inside this skill.

## Workflow

1. Ask which provider the human intends to connect and which workspace/project
   should own the credential. Do not ask for the key value.
2. Inspect existing non-secret credential records:

   ```bash
   python3 helpers/list_byok.py
   ```

3. If an equivalent active credential already exists, ask whether the human
   wants only to verify it. Do not create a duplicate automatically.
4. Otherwise, direct the human to the Stimulir Console BYOK settings for the
   selected workspace. Ask them to enter the provider key in that Console form
   and tell you only when registration finishes. Do not request screenshots
   containing the secret.
5. Re-run the list helper and identify the new credential by its non-secret ID,
   provider, and label.
6. Verify it:

   ```bash
   python3 helpers/verify_byok.py <credential_id>
   ```

7. Return the credential ID, provider, label, status, and verification result.

Supported provider identifiers are `openai`, `anthropic`, `google_gemini`,
`mistral`, `aws_bedrock`, `azure_openai`, `together_ai`, and `nebius`.

## Helper authority

`list_byok.py` and `verify_byok.py` invoke only non-secret CLI operations. They
may observe credential metadata and verification status, but they never receive
the stored provider secret. Treat returned error messages as potentially
sensitive operational metadata and do not copy them outside the user's task.

## Return

- selected workspace/project;
- provider and non-secret label;
- credential ID;
- stored status and live verification result;
- any typed verification blocker, without secret values.

## Boundaries

- Do not suggest environment-variable indirection as a way for agent code to
  handle the key; that still gives installed code access to the secret.
- Do not use a CLI secret prompt from this skill. The Console is the only
  supported secret-entry surface for this workflow.
- Do not call the BYOK REST endpoint directly.
- Do not add registration, removal, or rotation helpers.
