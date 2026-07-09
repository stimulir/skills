---
name: prompt-versioning
description: Manage prompts as versioned, labeled assets in the Stimulir workspace instead of hardcoded strings scattered through the adopter's codebase -- create a new prompt version, promote a version to an environment label (e.g. staging/prod), or resolve a prompt by key+label. Use when the user wants to edit, iterate on, roll back, or promote a prompt that currently lives as a string literal in their code, or asks to "version" / "label" / "deploy" a prompt change.
---

# Prompt Versioning

Prompts stop being string literals buried in the adopter's source and become
versioned, labeled assets in the Stimulir workspace: every edit is a new
immutable version, every environment (dev/staging/prod/...) points at a
version via a movable label, and promotion is one explicit CLI call, not a
code deploy.

## Placement rationale

This assumes `connect` has already run in this environment -- CLI installed,
authenticated, workspace selected (see `install.md` for the one-time check,
not re-documented here). Every helper in this skill shells out to the
`stimulir` CLI's `prompts` subcommands rather than reimplementing REST auth
in Python: the CLI already owns session caching in `~/.stimulir/`, and
duplicating that here would be a second, driftable source of truth for
credentials. This is the correct posture for this skill specifically --
compare to `migrate-inference`-style skills, which touch the ADOPTER's own
source and may need to speak the raw SDK/REST shape directly because the
adopter's code doesn't necessarily have the `stimulir` CLI available at
runtime.

**The split this skill delivers on:** the adopter's *runtime* code should
resolve prompts through the SDK -- `client.prompts.get(key,
label="prod")` -- instead of a hardcoded string. This skill's *helpers*
never touch that runtime code; they manage the versions and labels that
SDK call resolves against, from the CLI, ahead of time. If you're
migrating an adopter's hardcoded prompt string into this system, the
end state is: the string becomes the `--content` of a `create`d version
here, and the call site becomes `client.prompts.get(key, label=...)` in
their code -- a separate, explicit edit you make to their source after
the version exists, not something any helper here does for you.

## Capability tiers

| Capability | Status |
|---|---|
| List / inspect prompts and version history | Real CLI calls, read-only, no side effects |
| Create a new prompt version | Real CLI call. Additive -- a freshly created version affects nothing until a label is moved onto it |
| Update version metadata (name/notes/active) | Real CLI call. Content is immutable by design; there is no "edit content" mode -- create a new version instead |
| Move a label to a version (promote/rollback) | Real CLI call with REAL, IMMEDIATE production impact if the label is one live code resolves against. Gated behind `--confirm` in `label_prompt.py` -- see below |
| Evaluating a version before promoting it | **Not built here.** Hand off to the `eval-run` skill (`--prompt <key>:<label-or-version>`) against the non-prod-labeled version. This skill only versions and labels; it has no opinion on prompt quality |

## Preflight

```bash
stimulir prompts list --json
```

If this returns a JSON prompt list, the CLI is installed, authenticated,
and pointed at a workspace -- proceed. If it errors (auth, no workspace,
CLI not found), stop and resolve that first; this skill does not
re-implement `connect`'s setup, it only depends on it having already
succeeded.

## The version -> label -> promote workflow

This is the whole point of the skill -- do not skip straight to labeling
`prod`.

```
1. create_prompt_version.py create   ->  new immutable version, unlabeled
                                          (or labeled to a non-prod env,
                                          e.g. --label dev)
2. label_prompt.py <key> <v> staging  ->  promote to a non-prod label first
                                          (dry-run by default; --confirm to execute)
3. hand off to eval-run                  ->  eval-run's --prompt <key>:staging
                                          evaluates that version against a
                                          reviewed data asset
4. label_prompt.py <key> <v> prod     ->  only after step 3 passes, promote
                                          the SAME version to prod
                                          (again: --confirm required)
```

**Always label a new version to a non-prod environment first, evaluate it,
then promote the same version to prod.** Never `create` a version and label
it straight to `prod` in one motion -- even though `create --label prod` is
mechanically possible (the CLI surface allows it), this skill's workflow is
to keep `create`'s `--label` pointed at a non-prod environment (`dev`,
`staging`, whatever the adopter's convention is) and treat the prod label
move as a separate, later, `label_prompt.py --confirm` call made only after
an eval pass. If the user's prompt is genuinely a same-version rollback to
something already proven in prod before, that's a legitimate exception --
say so explicitly when you do it.

### 1. Create a version

```bash
python helpers/create_prompt_version.py create \
  --key <prompt_key> --content "<prompt body>" \
  --name "<display name>" --notes "<why this version>" \
  [--label dev]
```

Or read the body from a file: `--file <path>` instead of `--content`.
Always produces a brand-new version (v1 for a new key, vN+1 for an existing
one) -- there is no in-place content edit. If `--label` is omitted, the new
version is created unlabeled; nothing currently resolving any label is
affected either way.

### 2. Promote to a non-prod label, then evaluate

```bash
python helpers/label_prompt.py <key> <version> staging
# prints a dry-run by default -- re-run with --confirm to actually move the label
python helpers/label_prompt.py <key> <version> staging --confirm
```

Then hand off to the `eval-run` skill: its `create_eval_run.py --prompt`
flag accepts `KEY`, `KEY:VERSION`, or `KEY:LABEL` directly, so pass
`<key>:staging` (or `<key>:<version>` if you want to pin the exact version
number instead of trusting whatever the label currently resolves to) --
no extra resolution step needed in between. This skill does not run evals
itself -- it has no visibility into whether a prompt is *good*, only into
what version a label points at.

### 3. Promote to prod

```bash
python helpers/label_prompt.py <key> <version> prod --confirm
```

Only after the eval hand-off in step 2 comes back acceptable. This is the
exact same helper and the exact same `--confirm` gate as step 2 -- the
skill does not treat "prod" as a magic string requiring different code, the
discipline of evaluating first is a workflow the agent follows, not a
branch this helper hardcodes.

### Resolve / inspect at any point

```bash
python helpers/get_prompt.py <key> --label prod
python helpers/get_prompt.py <key> --version 3
stimulir prompts versions <key> --json
stimulir prompts list --json
```

`get_prompt.py` is read-only and safe to call as often as useful -- to
confirm what a label currently resolves to before and after a promotion, to
diff two versions' content, or to hand a version's content to an eval
harness.

### Rolling back

A rollback is not a special operation -- it's `label_prompt.py` pointed at
an older version number:

```bash
python helpers/label_prompt.py <key> <older_version> prod --confirm
```

## CLI reference

Helpers cover `create`, `update`, and `label`, `get`. `list`, `versions`,
and `archive` have no dedicated helper -- call the CLI directly, they're
already single, read-only-or-simple commands with a stable `--json` shape:

```bash
stimulir prompts list --json
stimulir prompts versions <key> --json
stimulir prompts archive <key> <version> --json   # marks a version inactive; irreversible via this CLI surface, confirm with the user first
```

```bash
# create a new version (new key or existing key)
python helpers/create_prompt_version.py create --key <key> \
  [--content "<text>" | --file <path>] \
  [--name <name>] [--type <type>] [--label <label>] [--notes <notes>]

# update metadata on an existing version (content is immutable)
python helpers/create_prompt_version.py update --key <key> --version <n> \
  [--name <name>] [--notes <notes>] [--active | --inactive]

# move a label to a version -- dry-run unless --confirm is passed
python helpers/label_prompt.py <key> <version> <label> [--confirm]

# resolve a prompt by key + label or key + version
python helpers/get_prompt.py <key> [--label <label> | --version <n>]
```

## Output contract

All three helpers print one JSON object to stdout on success (the CLI's own
`--json` payload, pretty-printed) and exit non-zero with a plain-text
`SystemExit` message to stderr on failure -- they don't swallow or reshape
CLI errors. `label_prompt.py` without `--confirm` prints a
`{"dry_run": true, "would_run": "...", "note": "..."}` object and exits 0
without calling the CLI at all.

A real version object (from `create`, `update`, or `get`) looks like:

```json
{
  "id": "0fa013e3-...",
  "key": "agent_chat_browser_research",
  "name": "Agent Chat Browser Research Prompt",
  "content": "Conduct web research for the following:\n...",
  "prompt_type": "task",
  "variables": {"research_query": "What to research"},
  "version": 1,
  "label": "production",
  "active": true,
  "archived": false,
  "change_notes": "...",
  "created_at": "2026-01-22T14:35:22.089049",
  "updated_at": "2026-01-22T14:35:22.089054"
}
```

`label` is a single string (or `null`) -- the label currently pointing at
*this* version, not a list of every label in the workspace. Two different
versions of the same key can each carry a different label at the same time
(e.g. v2 labeled `staging`, v5 labeled `prod`).

## Anti-patterns (do NOT do)

- **Calling `label_prompt.py` with `--confirm` straight after `create`,
  targeting `prod`, with no non-prod label and no eval step in between.**
  This is the single most important rule in this skill. A version must be
  labeled to a non-prod environment and evaluated (via `eval-run` or
  equivalent) before the same version is promoted to `prod`. The
  `--confirm` gate is mechanical, not editorial -- it stops an accidental
  execution, it does not stop a rushed one. The eval discipline is on the
  agent, every time.
- **Treating `label_prompt.py`'s dry-run output as a no-op you can ignore.**
  The dry-run is the safety check -- read `would_run` and confirm it's
  labeling the key/version/label you actually intend before adding
  `--confirm`. Don't reflexively append `--confirm` to every invocation.
- **Re-implementing REST auth or hitting `/api/v1/workspace/prompts`
  directly with raw `httpx`/`requests` calls.** The `stimulir` CLI already
  owns session caching in `~/.stimulir/`; shelling out to it is the
  correct posture for this skill. (The one exception in this family of
  skills is `migrate-inference`, which edits the adopter's own source and
  needs to speak the SDK/REST shape directly -- that is a different skill
  with a different job, not a reason to duplicate its approach here.)
- **Trying to "edit" a version's content via `update`.** `update` only
  touches metadata (name/notes/active). Content is immutable once a
  version exists by design -- there is no flag that changes it. Create a
  new version instead, every time content needs to change.
- **Calling `create_prompt_version.py create` with an empty prompt body.**
  The helper refuses this outright (fails loudly) rather than silently
  creating a version with no content -- neither `--content` nor `--file`
  being given is treated as a mistake, not a valid "empty" state.
- **Assuming a fresh, unlabeled version is "live" anywhere.** It is not --
  nothing resolves to it until a label is explicitly moved onto it via
  `label_prompt.py`. Don't tell a user a new version is "deployed" until
  the label move has actually been confirmed and executed.
- **Running `stimulir prompts archive` without checking with the user
  first.** It marks a version inactive and is not reversible through this
  CLI surface (no `unarchive` subcommand exists on this surface) -- treat
  it with the same care as any other irreversible action, even though it
  has no dedicated helper in this skill.
- **Building a helper that runs the eval-run skill itself, or that decides
  a version is "good enough" to promote.** That judgment belongs entirely
  to the agent orchestrating this skill plus whatever eval harness it
  hands off to -- no helper here inspects prompt quality, and none should.
