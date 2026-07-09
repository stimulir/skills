# Install — connect

First-time setup runbook. ~5 minutes, most of it the interactive login step.

## 0. Prereqs

```bash
python3 --version   # 3.10+
uv --version         # install: https://docs.astral.sh/uv/getting-started/installation/
```

This skill's helpers are Python standard library only (`subprocess`,
`json`, `pathlib`) -- there is no `pyproject.toml` dependency to install to
run them. `uv` is only needed to install the `stimulir` CLI itself.

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
```

For Codex:
```bash
ln -s ~/Developer/stimulir-skills/skills/connect ~/.codex/skills/connect
```

For Claude Code:
```bash
ln -s ~/Developer/stimulir-skills/skills/connect ~/.claude/skills/connect
```

### `npx skills add`

```bash
npx skills add stimulir/skills
```

## 2. Install the stimulir CLI

```bash
uv tool install stimulir
stimulir --version
```

If you already have it installed, keep it current:
```bash
uv tool upgrade stimulir
```

You can also run it without installing, via `uvx`:
```bash
uvx stimulir --help
```
(`uvx` works for one-off invocations but does not persist a login session
the way `uv tool install`'s wrapper does across separate `uvx` calls in the
same way a normal installed binary does -- prefer `uv tool install` for
anything beyond a single `--help` check.)

## 3. Authenticate

```bash
stimulir login
```

This opens a browser device-approval page with a code pre-filled -- confirm
it and you're in. No password is typed. The session is cached in
`~/.stimulir/` (a `stim_cli_` token, valid 30 days, refreshed on use).

For headless/CI/remote environments where a browser can't open locally:
```bash
stimulir login --headless   # prints the approval link instead of opening it
# or, with a pre-issued token from Settings -> CLI Tokens in the console:
stimulir login --token <stim_cli_...>
```

To end a session:
```bash
stimulir logout             # clears local credentials only
stimulir logout --remote    # also revokes the token server-side first
```

## 4. Select a workspace

```bash
stimulir workspace list --json
stimulir workspace use <id>
```

The selection is written to `~/.stimulir/config.json` (`{"workspace_id":
"..."}`) -- this is what every helper in this skill reads to confirm a
workspace is active. If your account belongs to only one workspace, you
still need to run `workspace use` explicitly once; nothing in this skill
auto-selects it for you.

## 5. Verify

```bash
cd ~/Developer/stimulir-skills/skills/connect
python3 helpers/check_environment.py
```

Expect `"ready": true` and an empty `"missing": []` list once steps 2-4 are
done. If anything is still missing, run:

```bash
python3 helpers/bootstrap.py
```

and follow `next_step.reason` / `next_step.next_command`.

## 6. Create an inference key and prove the loop

```bash
# real, billable action -- run directly, not via a helper (see SKILL.md)
stimulir keys create --name connect-smoke-test --env dev

# pick a model id confirmed for your workspace
stimulir models --json

# real inference call + real usage query
python3 helpers/smoke_test.py --model <model-id>
```

If `smoke_test.py` fails with an `unknown_model` error, the id you picked
from `stimulir models --json` isn't routable through `infer chat` on this
workspace -- try a different id from the same list, or one already present
in a `stimulir usage --group-by model --json` response.

## 7. Notes

- No network access beyond the stimulir API host is required for anything
  in this skill -- there's no separate `STIMULIR_API_URL`/`STIMULIR_API_KEY`
  pair to configure here the way some other skills in this repo need; the
  CLI itself owns all of that via `~/.stimulir/`.
- This skill never reads `~/.stimulir/credentials.json` (the cached session
  token) -- only the non-secret `workspace_id` field in
  `~/.stimulir/config.json`, and only via CLI subprocess calls otherwise.
- Corporate/offline environments that cannot reach the stimulir API can
  still run `helpers/check_environment.py`'s CLI-presence check; the auth
  and inference checks will correctly report as failed/unreachable rather
  than hanging indefinitely (each subprocess call has a timeout).
