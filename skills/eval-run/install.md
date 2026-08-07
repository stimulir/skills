# Install — eval-run

Assumes `connect` has already run: `stimulir` CLI installed, authenticated,
workspace selected. That setup is not repeated here. Around 2 minutes.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # >=3.10
```

Both helpers (`create_eval_run.py`, `check_eval_run.py`) use only the Python
standard library (`argparse`, `json`, `subprocess`, `shutil`, `sys`). There is
nothing to `pip install` or `uv sync` for this skill to run. `pyproject.toml`
declares the skill and its empty runtime dependency set, plus dev tooling
(`pytest`, `ruff`) if you are editing the helpers themselves:

```bash
# only needed if you are developing/testing this skill's helpers
uv sync
```

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
```

For Codex:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-run ~/.codex/skills/eval-run
```

For Claude Code:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-run ~/.claude/skills/eval-run
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
stimulir lab eval --help
```

If that fails with an auth error, re-run `connect` before using this skill.
There is no fallback auth path here, by design: see `SKILL.md`. The MCP
server exposes no lab tools, so shelling out to the CLI is the only path.

## 3. Console deep links

The CLI prints an openable console link every time it starts a run. That link
is `{console_base}/workspaces/lab/evaluate?run=<run-id>`, plus `&view=tree`
for the tree view. When the console origin cannot be resolved the CLI prints
the run id and names the variable instead of guessing a host:

```bash
export STIMULIR_CONSOLE_BASE=https://console.stimulir.com
# or set "console_base" in ~/.stimulir/config.json
```

Neither helper reconstructs the link. The CLI also derives it from the API
base as a fallback, and a second implementation would drift.

## 4. Verify

```bash
cd ~/Developer/stimulir-skills/skills/eval-run

# helpers import cleanly and show usage
python3 helpers/create_eval_run.py --help
python3 helpers/check_eval_run.py --help

# confirm the underlying CLI subcommands exist and are authenticated
stimulir lab eval runs --limit 1
stimulir lab eval create-run --help
stimulir lab eval get --help
stimulir lab eval tree --help
```

`stimulir lab eval runs --limit 1` is the only real smoke test that costs
nothing: it is a read against the selected workspace, so it proves auth and
scope in one call. There is no safe no-op for `create_eval_run.py` beyond
`--help`, because starting a run needs a real `--data-asset-id` (a reviewed,
snapshotted data asset) and a real `--prompt` ref. Do not fabricate
placeholder ids to exercise the happy path. Run it for real the first time
you have a genuine comparison to make.

## 5. Notes

- **Neither helper waits.** `check_eval_run.py` performs exactly one status
  read and returns; it has no interval or timeout arguments, and there is no
  `--wait` flag anywhere in `stimulir lab eval`. It replaced an earlier
  `poll_eval_run.py` that looped in the foreground. Do not reintroduce that,
  and do not wrap either helper in a shell loop.
- **`--execute` is the normal path.** `create-run` always sends
  `queue: true, execute: false` and issues the start as a separate call.
  Without `--execute` the run is created QUEUED with no executor spawned, and
  nothing polls for queued runs, so it never starts. `create_eval_run.py`
  therefore requires exactly one of `--execute` or `--leave-queued`.
- `--execute` starts real inference and judging across every case times every
  candidate. Treat it as a costed action.
- `stimulir lab eval delete` archives by default and archiving is one-way
  (there is no un-archive endpoint). `--hard` destroys rows and refuses on a
  run with descendants. Confirm with the user before either.
- If your `stimulir` binary is not on `PATH` under the name `stimulir`, pass
  `--stimulir-bin /path/to/stimulir` to either helper.
