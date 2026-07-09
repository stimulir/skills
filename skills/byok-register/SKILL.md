---
name: byok-register
description: Register an adopter's OWN existing provider API key (OpenAI, Anthropic, Gemini, Mistral, Bedrock, Azure OpenAI, Together AI, Nebius) with Stimulir as a bring-your-own-key credential, then verify it -- so the adopter keeps their existing provider contract/pricing while still getting Stimulir's gateway benefits (metering, fusion, privacy). Use when the user wants to connect a provider key they already have, as the alternate Stage 1 path to provisioning a new hyb_* managed key. Add + verify only -- this skill does not remove or rotate credentials.
---

# BYOK Register

Stage 1 has two paths onto Stimulir: provision a new managed `hyb_*` key, or
bring an existing provider key you already pay for. This skill is the
second path. The adopter keeps their own contract, rate limits, and pricing
with the upstream provider (OpenAI, Anthropic, Gemini, Mistral, Bedrock,
Azure OpenAI, Together AI, Nebius) -- Stimulir stores the credential
encrypted and routes through it, so the adopter still gets gateway-level
metering, fusion (multi-model panels), and privacy de-identification on top
of a key they were already using.

This skill is **add + verify only**. Removing or rotating a BYOK credential
is a separate, destructive operation (`stimulir byok remove`) and is
explicitly out of scope here -- do not wire it in.

## Placement rationale

This skill assumes `connect` has already run: the `stimulir` CLI is
installed, the user is authenticated (`stimulir login`), and a workspace is
selected. This skill does not re-document that setup -- see install.md for
the one-time dependency check, not the auth flow itself.

All three helpers are thin wrappers around the real `stimulir byok` CLI
subcommands (`add`, `list`, `verify`) -- there is no direct REST
implementation here. The CLI already owns session handling
(`~/.stimulir/`), retry behavior, and the credential encryption path; this
skill does not reimplement any of that.

## Preflight

```bash
which stimulir && stimulir --version
stimulir whoami
```

If `stimulir` is not on `PATH`, or `whoami` fails, stop and point the user
at `connect` / `stimulir login` -- do not attempt to work around a missing
or unauthenticated CLI from inside this skill.

## The workflow

### 1. Confirm the provider and gather the key safely

Ask the adopter which upstream provider they want to bring, and have them
export their EXISTING provider API key into an environment variable of
their choosing in their own shell -- e.g.:

```bash
export MY_OPENAI_KEY=sk-...
```

This skill never asks for, receives, or handles the raw key value directly.
It only ever receives the NAME of the environment variable
(`--key-env MY_OPENAI_KEY`), and reads the value from `os.environ` inside
the helper process, at the moment it is needed.

### 2. Dry run first

```bash
python helpers/register_byok.py --provider openai --label "acme-prod-openai" --key-env MY_OPENAI_KEY
```

Without `--confirm`, this only prints the exact `stimulir` command that
would run, plus `key_present: true/false` (never the key itself), and does
nothing else. Registering a credential is a real, workspace-visible side
effect -- always show the adopter the dry-run plan before running
`--confirm`.

### 3. Register for real

```bash
python helpers/register_byok.py --provider openai --label "acme-prod-openai" --key-env MY_OPENAI_KEY --confirm
```

Internally this shells out to `stimulir byok add --provider openai --label
"acme-prod-openai" --json` and pipes the secret to the CLI's own
`--secret`-omitted interactive prompt over **stdin** -- confirmed directly
against the installed CLI (`stimulir byok add --help`: "Provider API key
(omit to be prompted without echo)"). The key is never placed in `argv`, so
it never appears in shell history, `ps`, or a process listing. Prints the
CLI's JSON response (a credential id, provider, label, status) on success.

Valid `--provider` values (from the installed CLI's own enum): `openai`,
`anthropic`, `google_gemini`, `mistral`, `aws_bedrock`, `azure_openai`,
`together_ai`, `nebius`. The common hyphenated aliases (`gemini`,
`bedrock`, `together-ai`, `azure`) are accepted and mapped automatically.

### 4. Verify

```bash
python helpers/verify_byok.py <credential_id>
```

Re-validates the stored credential against its upstream provider
(`stimulir byok verify <id> --json`) and reports a normalized
`{"id", "verified": true|false, "exit_code", "detail"}`. Exits non-zero
when verification fails, so this composes cleanly in a script or a CI
check. Always run this immediately after registering -- a credential that
registers successfully but fails verification usually means a typo'd key
or a provider-side restriction (region lock, insufficient quota), and the
adopter should know that before relying on it.

### 5. List (status check / idempotency check)

```bash
python helpers/list_byok.py
```

Passes `stimulir byok list --json` straight through. Use this BEFORE
registering to check whether a credential with the intended label/provider
already exists (the CLI does not itself prevent duplicate labels), and
anytime the adopter asks "what keys do I have connected."

## CLI reference

```bash
# dry run (default, no side effects)
python helpers/register_byok.py --provider <provider> --label <label> --key-env <ENV_VAR_NAME>

# actually register (irreversible-by-this-skill: undo requires `stimulir byok remove`, out of scope)
python helpers/register_byok.py --provider <provider> --label <label> --key-env <ENV_VAR_NAME> --confirm

# verify a registered credential
python helpers/verify_byok.py <credential_id>

# list all credentials in the active workspace
python helpers/list_byok.py
```

Real CLI surface these wrap (for reference, not reimplemented here):

```bash
stimulir byok add --provider openai --label <label>      # prompts for secret on stdin
stimulir byok list --json
stimulir byok verify <id> --json
```

REST equivalent (documented for completeness -- this skill does not call it
directly; the CLI is the supported surface):

```
POST/GET /api/v1/workspace/byok
POST     /api/v1/workspace/byok/{id}/verify
```

## Output contract

`register_byok.py` (dry run):

```json
{
  "dry_run": true,
  "would_run": ["stimulir", "byok", "add", "--provider", "openai", "--label", "acme-prod-openai", "--json"],
  "provider": "openai",
  "label": "acme-prod-openai",
  "key_env": "MY_OPENAI_KEY",
  "key_present": true,
  "note": "No credential was registered. ..."
}
```

`register_byok.py --confirm` (real run):

```json
{
  "dry_run": false,
  "provider": "openai",
  "label": "acme-prod-openai",
  "result": { "...": "whatever `stimulir byok add --json` returned, e.g. id/provider/label/status" }
}
```

`verify_byok.py`:

```json
{ "id": "45be2da3-...", "verified": true, "exit_code": 0, "detail": { "...": "CLI verify payload" } }
```

`list_byok.py`: the CLI's own `stimulir byok list --json` payload, passed
through unmodified (currently `{"credentials": [...], "by_provider": [...]}`
on the installed CLI version -- treat the exact shape as CLI-owned, not a
contract this skill defines).

## Anti-patterns (do NOT do)

- **Ever accepting a raw provider API key as a plain CLI argument.** Do not
  add a `--key` / `--secret` flag to `register_byok.py` that takes the key
  value directly. The only accepted input is `--key-env <VAR_NAME>` --
  indirection through an environment variable the caller names, read once
  in-process. A key value on argv lands in shell history and `ps` output;
  that is the exact failure mode this design exists to prevent.
- **Ever writing a raw key value to a log, stdout, stderr, or a file.**
  `register_byok.py` prints only `key_present: true/false`, never the
  value. If `stimulir byok add` ever changes to echo the secret back in its
  own output, do not print that field through unmodified -- redact it
  first. Today's CLI does not do this (confirmed against `--help` and a
  live dry run), but treat it as an invariant to keep checking, not a
  one-time fact.
- **Running `register_byok.py --confirm` without having shown the adopter
  the dry-run output first.** Registration is a real, irreversible-by-this-
  skill side effect (undoing it requires `stimulir byok remove`, which is
  out of scope). Always dry-run, let the agent/user see the plan, then
  confirm.
- **Building or calling a `remove`/rotate helper from this skill.** That is
  explicitly a different, destructive capability. If an adopter needs to
  remove a BYOK credential, tell them the CLI command
  (`stimulir byok remove <id>`) rather than adding a wrapper here.
- **Reimplementing REST auth in Python for this skill.** The `stimulir` CLI
  already owns login/session caching in `~/.stimulir/`; shell out to it
  with `--json`, don't hand-roll `POST /api/v1/workspace/byok` calls.
- **Assuming the `--provider` string the user says out loud matches the
  CLI's enum verbatim.** "Gemini" and "Bedrock" are common shorthand but
  the CLI's real values are `google_gemini` and `aws_bedrock`;
  `register_byok.py` maps the common aliases, but don't invent new
  provider strings that aren't in the CLI's own `--help` enum.
- **Treating a successful `register` as sufficient proof the key works.**
  Always follow with `verify_byok.py` -- a credential can be stored but
  still fail live validation against the upstream provider.
