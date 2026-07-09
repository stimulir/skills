# Install — byok-register

No new auth surface here -- this skill uses the `stimulir` CLI's existing
session. If `connect` has already run in this environment (CLI installed,
`stimulir login` completed, workspace selected), skip straight to step 3.
~2 minutes otherwise.

## 0. Prereqs

```bash
which stimulir && stimulir --version   # v0.1.0 or later
python3 --version                      # >=3.10
```

This skill's helpers use only the Python standard library (`argparse`,
`json`, `os`, `shutil`, `subprocess`, `sys`) -- there is nothing to `uv sync`
or `pip install` for `byok-register` itself. `pyproject.toml` exists for
convention/consistency with sibling skills and declares zero runtime
dependencies.

## 1. Skill install

### Local clone + symlink

For Claude Code:
```bash
ln -s /path/to/workspace/skills/skills/byok-register ~/.claude/skills/byok-register
```

For Codex:
```bash
ln -s /path/to/workspace/skills/skills/byok-register ~/.codex/skills/byok-register
```

## 2. Auth (already handled by `connect` -- verify, don't redo)

```bash
stimulir whoami
```

If this fails, this skill is not usable yet -- go run `connect` /
`stimulir login` first. Do not attempt to work around a missing or
unauthenticated CLI session from inside `byok-register`'s helpers; they all
assume an authenticated CLI with a selected workspace and will fail loudly
(not silently) if that assumption doesn't hold.

## 3. Verify

```bash
cd /path/to/workspace/skills/skills/byok-register

# read-only: lists whatever BYOK credentials already exist in the active workspace
python3 helpers/list_byok.py

# dry run: prints the plan, registers nothing, never touches a real key
export SMOKE_TEST_KEY=not-a-real-key
python3 helpers/register_byok.py --provider openai --label smoke-test --key-env SMOKE_TEST_KEY
unset SMOKE_TEST_KEY

# if the dry run's "would_run" list looks right and key_present is true, the wiring is correct
```

Do not run `register_byok.py --confirm` as part of a smoke test -- it is a
real, workspace-visible registration against a live provider account. Save
`--confirm` for an actual credential the adopter wants connected.

If you already have a BYOK credential registered (from a prior session or
another tool), you can safely verify it read-only:

```bash
python3 helpers/verify_byok.py <credential_id from list_byok.py output>
```

## 4. Notes

- All three helpers shell out to the `stimulir` CLI -- none of them make a
  direct HTTP call. If `stimulir` is ever unreachable (network, session
  expiry), the failure surfaces as a normal CLI error captured in
  `stderr`/exit code, not a Python traceback.
- `register_byok.py` defaults to dry-run. There is no environment variable
  or config flag that changes this default -- `--confirm` must be passed
  explicitly on every real registration, every time.
- The provider enum (`openai`, `anthropic`, `google_gemini`, `mistral`,
  `aws_bedrock`, `azure_openai`, `together_ai`, `nebius`) is read from the
  installed CLI's own `--help` output at the time this skill was built.
  If a future CLI version adds or renames a provider, `register_byok.py`'s
  `PROVIDERS` list needs a one-line update to match -- it is not derived
  dynamically from the CLI.
