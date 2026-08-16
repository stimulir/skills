# Install — eval-iterate

Assumes `connect` has already run (`stimulir` CLI installed, authenticated,
workspace selected). That setup is not repeated here. About 2 minutes.

## 0. Prereqs

```bash
stimulir --version
python3 --version   # >=3.10
```

All four helper files (`_common.py`, `read_tree.py`, `derive_candidate.py`,
`ack_steer.py`) use only the standard library: `argparse`, `hashlib`, `json`,
`os`, `pathlib`, `shutil`, `subprocess`, `sys`. There is nothing to
`pip install` or `uv sync` for this skill to run. `pyproject.toml` exists to
declare the skill and its empty runtime dependency set, plus dev tooling if
you are editing the helpers themselves:

```bash
# only needed if you are developing/testing this skill's helpers
uv sync
```

## 1. The CLI must be recent enough to have the lineage verbs

This skill wraps `tree`, `derive` and `ack-steer`, which shipped after the
original `create-run` / `get-run` surface. Check:

```bash
stimulir lab eval tree --help
stimulir lab eval derive --help
stimulir lab eval ack-steer --help
```

If any of the three is missing, the installed CLI predates the lineage work.
Upgrade it (`pip install -U stimulir`) before using this skill. There is no
fallback: the MCP server exposes 8 tools and none of them touch the lab, so
shelling out to the CLI is the only operator path to this surface.

## 2. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
```

For Codex:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-iterate ~/.codex/skills/eval-iterate
```

For Claude Code:
```bash
ln -s ~/Developer/stimulir-skills/skills/eval-iterate ~/.claude/skills/eval-iterate
```

### `npx skills add`

```bash
npx skills add stimulir/skills
```

## 3. Auth (already handled by `connect`)

This skill does no authentication of its own. It shells out to the `stimulir`
CLI, which reads its session from `~/.stimulir/`. Confirm it is live against
a real read:

```bash
stimulir lab eval runs --limit 5
```

If that errors on auth or workspace selection, re-run `connect` before using
this skill. There is no fallback auth path here, by design. See `SKILL.md`'s
placement rationale for why this skill does not reimplement
`Authorization: Bearer $STIMULIR_TOKEN` / `X-Business-Profile-Id`.

## 4. Console deep links (optional, one line)

The helpers print a link to the child run at
`{console_base}/workspaces/lab/evaluate?run=<id>&view=tree`, opening the RSI
workbench directly. The base is resolved from
`STIMULIR_CONSOLE_BASE`, then `console_base` in `~/.stimulir/config.json`:

```bash
export STIMULIR_CONSOLE_BASE=https://console.stimulir.com
```

If neither is set, the helpers emit `console_url: null` plus a hint naming
the variable. They deliberately do not reproduce the CLI's `api.` to
`console.` hostname derivation, because a second implementation of it here
would be a second place to drift, and a link that 404s on a run that exists
is worse than no link.

## 5. Verify

```bash
cd ~/Developer/stimulir-skills/skills/eval-iterate

# helpers import cleanly and show usage
python3 helpers/read_tree.py --help
python3 helpers/derive_candidate.py --help
python3 helpers/ack_steer.py --help

# the one real, safe smoke test: read a lineage. Read-only, spends nothing.
python3 helpers/read_tree.py <an-existing-run-id>
```

`read_tree.py` against a real run id is a genuine end-to-end check: it proves
the CLI is installed, authenticated, pointed at the right workspace, and new
enough to have `tree`. Use any eval run id from `stimulir lab eval runs`.

There is no safe smoke test for `derive_candidate.py`. A derive re-runs the
full case set for two arms and costs real inference plus judging, and it
mutates a durable lineage. Do not fabricate a run id to exercise the happy
path. Run it for real the first time you have an actual hypothesis to test.

## 6. Notes

- **No helper starts a server, a background process or a loop.** There is no
  `--wait`, no `--interval-seconds`, no `--timeout-seconds` and no
  `--max-iterations` anywhere in this skill. Each helper makes one or two
  CLI calls in the foreground and exits.
- **`derive_candidate.py` spends money.** Each branch re-runs the full case
  set for both the incumbent and the new arm. Read `projected_next_spend`
  from `read_tree.py` before invoking it.
- **The API owns the caps**, not this skill: depth 8, and 4 unfinished
  branches per tree. A refusal is the stopping signal, not an error to retry
  around.
- **Archive is one-way.** `stimulir lab eval delete` defaults to archiving,
  there is no un-archive endpoint, and a hard delete of a run with
  descendants 409s unless `--include-descendants` is passed. No helper here
  wraps it. Ask a human first.
- If your `stimulir` binary is not on `PATH` under the name `stimulir`, pass
  `--stimulir-bin /path/to/stimulir` to any helper.
