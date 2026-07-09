# Install — prompt-versioning

No local hardware, no extra Python dependencies, no separate API key --
this skill only needs the `stimulir` CLI already installed, authenticated,
and pointed at a workspace (i.e. `connect` has already run in this
environment). ~2 minutes if that's already true.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # 3.10+
```

No `pip install` / `uv sync` is strictly required -- both helpers and this
skill's `pyproject.toml` declare zero runtime dependencies (stdlib
`argparse`, `json`, `subprocess` only). If your environment uses `uv` for
consistency with sibling skills:

```bash
cd path/to/prompt-versioning
uv sync
```

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
```

For Codex:
```bash
ln -s ~/Developer/stimulir-skills/skills/prompt-versioning ~/.codex/skills/prompt-versioning
```

For Claude Code:
```bash
ln -s ~/Developer/stimulir-skills/skills/prompt-versioning ~/.claude/skills/prompt-versioning
```

### `npx skills add`

```bash
npx skills add stimulir/skills
```

## 2. Confirm `stimulir` is authenticated and a workspace is selected

This skill does not perform login or workspace selection itself -- that is
`connect`'s job, and every skill in this family assumes it already
succeeded. Confirm it did:

```bash
stimulir prompts list --json
```

- If this prints a JSON object with a `"prompts"` array (even an empty
  one), you're set -- proceed to verify below.
- If it errors with an auth failure or "no workspace selected", run
  whatever `connect` flow your environment uses before coming back to this
  skill. There is no fallback path here.

## 3. Verify

```bash
cd ~/Developer/stimulir-skills/skills/prompt-versioning

# byte-compile check
python3 -m py_compile helpers/*.py

# read-only smoke test against your real workspace
python3 helpers/get_prompt.py <any_existing_prompt_key> 2>&1 | head -5
# or, if you don't know a key yet:
stimulir prompts list --json | head -20

# dry-run smoke test -- prints the command, does NOT execute it
python3 helpers/label_prompt.py <any_existing_prompt_key> 1 staging
# expect: {"dry_run": true, "would_run": "stimulir prompts label ...", ...}
```

If you want to exercise the full write path, create a disposable test key,
promote it, then archive it when done:

```bash
python3 helpers/create_prompt_version.py create \
  --key _pv_install_smoke_test --content "smoke test {{x}}" --notes "install.md verification"
python3 helpers/label_prompt.py _pv_install_smoke_test 1 staging --confirm
python3 helpers/get_prompt.py _pv_install_smoke_test --label staging

# clean up -- archive is not reversible via this CLI surface, but this is a
# throwaway key created purely for this verification step
stimulir prompts archive _pv_install_smoke_test 1 --json
```

## 4. Notes

- No env vars, no API key file, no network config specific to this skill --
  everything rides on the `stimulir` CLI's own session in `~/.stimulir/`.
- `label_prompt.py` defaults to dry-run (prints the command, exits 0,
  executes nothing) unless `--confirm` is passed. This is deliberate: the
  helper never assumes a label move -- especially to `prod` -- is safe to
  execute without the caller explicitly saying so.
- If `stimulir` itself is missing, install it per Stimulir's own CLI setup
  docs -- that installation and its authentication flow are out of scope
  for this skill, which only depends on it already being done.
