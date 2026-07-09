# Install — eval-run

Assumes `connect` has already run (`stimulir` CLI installed, authenticated,
workspace selected) -- that setup is not repeated here. ~2 minutes.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # >=3.10
```

Both helpers (`create_eval_run.py`, `poll_eval_run.py`) use only the Python
standard library (`argparse`, `json`, `subprocess`, `shutil`, `time`, `sys`)
-- there is nothing to `pip install` or `uv sync` for this skill to run.
`pyproject.toml` exists to declare the skill and its (empty) runtime
dependency set, plus dev tooling (`pytest`, `ruff`) if you're editing the
helpers themselves:

```bash
# only needed if you're developing/testing this skill's helpers
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

This skill does not do its own authentication -- it shells out to the
`stimulir` CLI, which reads its session from `~/.stimulir/` (set up once by
`connect`). Confirm it's live:

```bash
stimulir lab eval create-run --help
```

If that fails with an auth error, re-run `connect` (or whatever your
environment's login flow is) before using this skill -- there is no
fallback auth path here, by design (see `SKILL.md`'s placement rationale
for why this skill deliberately does not reimplement
`Authorization: Bearer $STIMULIR_TOKEN` / `X-Business-Profile-Id:
$WORKSPACE_ID` itself).

## 3. Verify

```bash
cd ~/Developer/stimulir-skills/skills/eval-run

# helper scripts import cleanly and show usage
python3 helpers/create_eval_run.py --help
python3 helpers/poll_eval_run.py --help

# confirm the underlying CLI subcommands exist and are authenticated
stimulir lab eval create-run --help
stimulir lab eval get-run --help
```

There is no safe no-op smoke test for `create_eval_run.py` beyond `--help`
-- creating a run needs a real `--data-asset-id` (a reviewed, snapshotted
data asset) and a real `--prompt <key>:<version>` reference, both of which
are specific to your workspace. Don't fabricate placeholder IDs just to
exercise the happy path; run it for real against a data asset you've
actually reviewed, the first time you use this skill for a genuine
prompt/model comparison.

## 4. Notes

- Neither helper starts a server or a background process. `poll_eval_run.py`
  loops in the foreground with a bounded `--timeout-seconds` (default
  1800s / 30 min) and always exits -- it does not detach or daemonize.
- `create_eval_run.py --execute` starts real evaluation work (inference
  calls against every row in the data asset) -- treat it like any other
  costed action, not a free dry run. Omit `--execute` to create the run
  queued and inspect it before committing to a full pass.
- If your `stimulir` binary isn't on `PATH` under the name `stimulir`, pass
  `--stimulir-bin /path/to/stimulir` to either helper.
