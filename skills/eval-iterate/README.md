# eval-iterate

Advances an eval lineage by **one branch, once**. Reads the tree from any run
id, reads every hypothesis the lineage has already tried, derives one new
prompt candidate with a stated rationale, and hands back the child run id and
a console link. Then it stops.

The first skill in the `loop` category, and the category was empty until the
console could own the three things a loop needs: the budget, the champion
pointer and the stopping rule.

## Why

- **One iteration per invocation.** One tree read, at most one derive, at
  most one ack, then return. If more iterations are wanted, the caller
  invokes the skill again. That is the only mechanism, and there is no
  `--max-iterations` to pretend otherwise.
- **It does not decide when to stop.** Depth is capped at 8 and unfinished
  branches at 4, server-side. When the API refuses a derive, that refusal is
  the stop. The skill holds no counter, and `read_tree.py` reports headroom
  as advisory rather than gating on it.
- **It does not invoke another skill.** `prompt-versioning/SKILL.md:258-261`
  bans building a helper that runs another skill or that decides a version is
  good enough to promote. A loop that called the next skill would be exactly
  that. The label move stays in `prompt-versioning`, taken by whoever read
  the evidence.
- **It does not poll.** No `--wait`, no `--timeout-seconds`, no polling
  helper. The absence is the design: a `--wait` is a poll loop with a
  friendlier name and it puts the wait back in the agent's context.
- **The rationale is mandatory and checked.** A branch with no stated
  hypothesis is a rerun with extra steps. `derive_candidate.py` refuses thin
  or boilerplate text, and refuses a hypothesis this lineage already tried
  unless the repeat is declared deliberate.

## Quick start

```bash
# 1. read the lineage from ANY run id in it. Read-only, spends nothing.
python3 helpers/read_tree.py <run-id>

# 2. read `prior_rationales` in that output. This is the step that makes it
#    a loop instead of a random walk. Then write a hypothesis it does not
#    already answer.

# 3. branch one candidate carrying that hypothesis.
python3 helpers/derive_candidate.py <run-id> \
  --rationale "Name the currency explicitly in the output schema. Every failing
  row is an unlabelled amount, so this should lift exact-match on those rows." \
  --prompt-file ./candidate.txt

# 4. if a steer prompted this, ack it AFTER acting, with the child id.
python3 helpers/ack_steer.py <run-id> <steer-id> \
  --consumed-by <agent-session-id> --note "applied as derive on run <child-id>"
```

Then stop. Report the child run id and the console link.

## Relationship to the neighbouring skills

```
eval-run          creates and reads ONE run. No lineage mutation.
eval-iterate      branches the lineage. One derive per invocation.
prompt-versioning owns the label move. The promotion decision lands here.
```

Each of the three refuses the next one's job, and none of them calls another.
The agent orchestrates across them; a skill does not.

## Honest limits

- **Prompt candidates only.** Adapter derive is refused by the API in two
  different ways, and the difference matters:
  `eval_derive_warm_start_unavailable` is blocked (no console-side SFT
  producer exists) and `eval_derive_kind_not_implemented` is merely out of
  this slice. This skill exposes no `--kind` flag rather than offering one
  that always 400s.
- **D2L is out of scope entirely.** Doc-to-LoRA is hypernetwork context
  internalisation, a separate route from PEFT LoRA. Neither is reachable
  from here, and they are never the same thing.
- **A steer is input, not authority.** It informs the hypothesis. It cannot
  authorize a label move, a delete, an archive or a `--stop-parent`.

See [`SKILL.md`](./SKILL.md) for the full playbook, including how to read
promotion blockers, when you cannot iterate this turn, and why ranking never
crosses a comparability bucket. See [`install.md`](./install.md) for setup.

## Architecture

```
read_tree.py         → stimulir lab eval tree <id> --json      → iteration brief
derive_candidate.py  → stimulir lab eval tree <id> --json      → prior-hypothesis check
                     → stimulir lab eval derive <id> --json    → child id + status + link
ack_steer.py         → stimulir lab eval ack-steer ... --json  → write-once consumption record
```

Three scripts plus `_common.py` (CLI invocation and console-link resolution).
Stdlib only. No server, no background process, no state file: the state lives
in the console run row, which is what makes this a `loop` skill rather than a
`managed` one.

`read_tree.py` adds the selection the raw tree payload does not: champion,
promotion blockers, prior rationales, unconsumed steers, budget headroom and
projected spend. It invents nothing.

`derive_candidate.py` reads the tree before deriving, so the duplicate-
hypothesis check happens while it can still save the money rather than after.
Its idempotency key is a digest of parent run id plus rationale, so a
re-invoked iteration that crashed mid-flight returns the first child and
spends nothing.

Verbs deliberately left as bare CLI calls: `steer` (leaving one is a human
directing an agent) and `delete` (archive is one-way, hard delete 409s on
lineage). Both need a human first.

## Category marker

The frontmatter carries `metadata.category: loop`, following the taxonomy's
choice of `metadata` as the one namespace every verified consumer preserves.
Nothing reads it yet. It replaces an unenforced prose convention with a
machine-readable one, not with an enforced one.
