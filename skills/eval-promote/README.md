# eval-promote

Closes the loop. Reviews a completed eval run's **promotion proposals** and
applies exactly one, with the human authorising it. Applying moves a production
label onto the winning prompt version and pins the champion. Stage 3 of the
promote-with-evidence pipeline: after `eval-run` scores and `eval-iterate`
branches, this is the step that ships the winner.

## Why

- **Promotion is a live production change.** Applying a proposal moves the label
  so traffic serves the new version immediately, and pins the champion. The
  skill surfaces the exact move first and applies one proposal per invocation.
- **The human authorises, the agent proposes.** `stimulir lab eval promote` asks
  for confirmation before it changes anything, and this skill never passes
  `--yes` on the human's behalf. There is no `promote` helper, on purpose: a
  helper could not answer that prompt from a stream the human sees. The agent
  renders the move; the human runs the command and answers.
- **It reviews and promotes, nothing else.** Scoring is `eval-run`. Branching is
  `eval-iterate`. This skill does neither.

## Quick start

```bash
# 1. see what completed runs recommend. Read-only.
python3 helpers/review_proposal.py

# 2. render exactly ONE move and the command to apply it. Runs nothing.
python3 helpers/review_proposal.py <proposal-id>

# 3. the HUMAN runs the promote and answers its confirmation prompt.
stimulir lab eval promote <proposal-id> --reason "beat incumbent on the reviewed asset"

# 4. confirm the pin landed.
stimulir lab eval champions
```

See [`SKILL.md`](./SKILL.md) for the full playbook, including why there is no
promote helper and what a promotion sets in motion downstream. See
[`install.md`](./install.md) for setup.

## Architecture

```
review_proposal.py  → stimulir lab eval proposals --json   → the exact move + the promote command (NOT run)
(human)             → stimulir lab eval promote <id>        → label moves live, champion pinned
```

One read-only helper, no shared state, no server, no background process. The
helper wraps one CLI read and renders the move; it never runs `promote`. The
live change stays a bare CLI call the human makes after seeing the move.
