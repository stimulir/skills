# Install — eval-promote

Assumes `connect` has already run: `stimulir` CLI installed, authenticated,
workspace selected. That setup is not repeated here. Around 2 minutes.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # >=3.10
```

The one helper (`review_proposal.py`) uses only the Python standard library
(`argparse`, `json`, `subprocess`, `shutil`, `sys`). There is nothing to
`pip install` or `uv sync` for this skill to run. `pyproject.toml` declares the
skill and its empty runtime dependency set, plus dev tooling (`pytest`, `ruff`)
if you are editing the helper itself:

```bash
# only needed if you are developing/testing this skill's helper
uv sync
```

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
```

For Codex:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-promote ~/.codex/skills/eval-promote
```

For Claude Code:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-promote ~/.claude/skills/eval-promote
```

### `npx skills add`

```bash
npx skills add stimulir/skills
```

## 2. Auth (already handled by `connect`)

This skill does no authentication of its own. It shells out to the `stimulir`
CLI, which reads its session from `~/.stimulir/` (set up once by `connect`).
Confirm it is live:

```bash
stimulir lab eval proposals --help
```

If that fails with an auth error, re-run `connect` before using this skill.
There is no fallback auth path here, by design: see `SKILL.md`. The MCP server
exposes no lab tools, so shelling out to the CLI is the only path.

## 3. Verify

```bash
cd ~/Developer/stimulir-skills/skills/eval-promote

# helper imports cleanly and shows usage
python3 helpers/review_proposal.py --help

# confirm the underlying CLI subcommands exist and are authenticated
stimulir lab eval proposals --status proposed --json
stimulir lab eval promote --help
stimulir lab eval champions --json
```

`stimulir lab eval proposals --status proposed --json` is the real smoke test
and costs nothing: it is a read against the selected workspace, so it proves
auth and scope in one call. An empty list is a valid result. Do not run
`promote` to "test" it. It is a live production change and there is no dry-run
form of it.

## 4. Notes

- **This skill never confirms a promotion on the human's behalf.**
  `review_proposal.py` reads and renders; it has no path that runs
  `stimulir lab eval promote`. The promote is a bare CLI call the human runs so
  they see and answer its confirmation prompt. Do not pass `--yes` for them, and
  do not wrap the command in anything that answers the prompt.
- **One proposal per invocation.** `review_proposal.py <id>` renders exactly one
  move. Several open proposals are reviewed and promoted one at a time, each its
  own decision.
- `stimulir lab eval promote` is auditable and revertible, but every request
  served between the apply and a revert used the new version. Treat it as a live
  change.
- If your `stimulir` binary is not on `PATH` under the name `stimulir`, pass
  `--stimulir-bin /path/to/stimulir` to the helper.
