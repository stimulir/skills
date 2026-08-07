# stimulir-skills

Agent skills for integrating the [Stimulir](https://www.stimulir.com) AI
gateway into your own product. Each skill is a self-contained directory a
coding agent (Claude Code, Codex, or any agent that reads `SKILL.md` files)
can install and use directly. You install it, as the adopting engineer or
product person, then hand it to whichever agent you already run.

Stimulir's own positioning is "one gateway, every AI workflow, gets sharper
as it runs". The gateway swap is table stakes; the real differentiator is
the feedback loop from live traffic back into better inference. These
skills are sequenced to match that: get connected, wire your existing code
onto the gateway, then turn the feedback loop on.

## The onboarding journey

| Stage | Skill | What it does |
|---|---|---|
| 0. Connect | [`connect`](./skills/connect/) | Install the CLI, authenticate, create a workspace-scoped key, send one real inference call, confirm the cost shows up. Minutes, not hours. |
| 1. Migrate | [`migrate-inference`](./skills/migrate-inference/) | Scan your own codebase for direct OpenAI/Anthropic calls and rewire them onto Stimulir. The Stimulir Python SDK (`StimulirClient`) is the preferred landing point; the OpenAI-compatible `base_url` swap is the fallback for non-Python code. |
| 1. Migrate (alt) | [`byok-register`](./skills/byok-register/) | Keep your existing provider contract by registering your own key with Stimulir instead of switching to managed inference. |
| 1. Migrate (voice) | [`voice-modalities`](./skills/voice-modalities/) | Wire voice onto the gateway: one realtime WebSocket covers speech-to-speech, live transcription, and verbatim text-to-speech. Omni-model native, verified live. |
| 2. Flywheel | [`capture-traces`](./skills/capture-traces/) | Turn live traffic into curated data assets (Raw → Cleaning → Clean View → Snapshot). This is the mechanism behind "gets sharper as it runs." |
| 2. Flywheel | [`privacy-layer`](./skills/privacy-layer/) | Redact/mask PII before it's captured or forwarded. Sequence this *before* `capture-traces`, since captured traces become future training data. |
| 3. Close the loop | [`prompt-versioning`](./skills/prompt-versioning/) | Version and label prompts instead of hardcoding strings; promote through environments deliberately. |
| 3. Close the loop | [`eval-run`](./skills/eval-run/) | Compare a prompt or model change against a curated dataset before promoting to prod. |
| 3. Close the loop | [`eval-iterate`](./skills/eval-iterate/) | Advance an existing eval lineage by one branch: read the tree and its prior hypotheses, derive one new prompt candidate, hand back the child run id. One iteration per invocation. |
| Ongoing | [`usage-audit`](./skills/usage-audit/) | Cost-per-task visibility. Runs alongside every other stage, not sequential. |

Everything past Stage 0 assumes `connect` has already run: the CLI is
installed, authenticated, and pointed at the right workspace.

## Managed skills

Agent capabilities rather than onboarding stages. These are imported into a
workspace and run in the sandbox.

| Skill | What it does | External key |
|---|---|---|
| [`web-scrape`](./skills/web-scrape/) | Plain text extraction from one URL, a list of URLs, or an index page whose links should be followed. Parallel fetch and extract, structured JSON out. No scoring and no research judgment; reach for `deep-research` when you want a cited report instead. | *(none)* |
| [`deep-research`](./skills/deep-research/) | Exhaustive web research: Serper discovery, parallel fetch/extract fan-out, cited report plus CSV. HTTP-only by default; browser-use (Chromium) optional. | `SERPER_API_KEY` |
| [`opposition-enrich`](./skills/opposition-enrich/) | Competitor and opposition intelligence: discover a rival's properties, research them in parallel, extract structured attributes, compile a sourced brief for one competitor or a landscape. | `SERPER_API_KEY` |
| [`scenario-simulate`](./skills/scenario-simulate/) | What-if against a described population. Materialise personas from a context, fan their reactions out through the gateway, return a segment-level distribution plus a narrative explaining the split. Market, electorate, users or workforce; resumable one timestep at a time. Output is synthetic by construction and must never be presented as measurement. | *(none)* |

The "External key" column says which key the skill reads. It is not a scope. A
managed run injects **every** key the workspace vault holds, so a skill that
reads one key can still reach the rest. The injection is per business profile,
so this is intra-workspace, not cross-tenant. Put `SERPER_API_KEY` in the vault
of the workspace that runs the two research skills. Rows marked *(none)* need
nothing beyond the gateway `STIMULIR_API_KEY` a managed run already provides.

## Two axes: stage and runtime contract

The onboarding journey table sequences skills by **stage**. That is one axis.
The second axis is the **runtime contract**: where a skill runs, what it can
reach, and whether it leaves state behind. Every skill carries it in
frontmatter as `metadata.category`.

| Category | Runtime contract | Count |
|---|---|---|
| `operator` | Needs the `stimulir` CLI and a `~/.stimulir` session on the caller's machine. Shells out to the CLI rather than reimplementing REST auth. No vault injection. | 9 |
| `managed` | Runs inside the Stimulir sandbox with the workspace vault injected into its environment. No CLI session. Hard-bounded at four agent turns by the sandbox runner, so anything long has to be resumable a step at a time. | 4 |
| `loop` | Carries state across invocations against a console-side run row, champion pointer and iteration budget. Exactly one iteration per invocation. | 1 |

The axes are independent, and neither replaces the other. `capture-traces` is
Stage 2 and `operator`. `deep-research` is `managed` and belongs to no stage at
all. `eval-iterate` is Stage 3 and `loop`, which is why it appears in the stage
table above and in this one. Stage tells you when to reach for a skill.
Category tells you what has to be true for it to run.

`metadata` is the namespace because it is the one the installer preserves. Note
that it is a **reserved namespace with behaviour-changing keys**, not a free-form
bag: `npx skills add` already acts on `metadata.internal` to hide a skill from
install. Nothing acts on `metadata.category` today, so for now it replaces an
unenforced prose convention with a machine-readable one, not with an enforced
one. Treat `category` as a key we have claimed inside someone else's namespace,
and check upstream before adding another `metadata.*` key.

### Why `loop` skills do exactly one iteration per invocation

A loop needs three things: an iteration budget, a champion pointer naming the
incumbent a challenger has to beat, and a stopping rule. All three live in the
console, on the run row. None of them live in the skill.

So a `loop` skill turns the crank once and returns. It never decides the
lineage is finished, it never polls for a result, and it never invokes another
skill. Deciding when to stop and calling the next skill are the two things
this repo refuses in nine places, most sharply at
`prompt-versioning/SKILL.md:258-261`. When the budget is spent the API refuses
the next branch, and that refusal is the stop signal. If more iterations are
wanted, the caller invokes the skill again, having read the last result. There
is no `--max-iterations` flag, because a skill that held one would be holding
the stopping rule.

### On `required_secrets`

Four skills used to declare a `required_secrets` list in frontmatter. It has
been **removed**, not documented, and the reason is that it read as a security
control while being none.

Nothing parsed it. The console's frontmatter reader is a line splitter that
cannot represent a list, and `SkillCandidate` never carried the field. More to
the point, both sandbox injection sites enumerate the whole workspace vault and
pass every key to the skill's environment regardless of what the skill
declared. A field named `required_secrets` sitting next to a vault that injects
everything invites exactly one wrong conclusion, which is that declaring one
key excludes the others.

`metadata.category: managed` now does the membership marking that
`required_secrets` was actually doing, since it discriminated by key presence
rather than by value: two of the four declared an empty list. The genuine
requirement survives in prose, in each skill's "Secrets this skill needs"
section and in the table above. If per-skill vault scoping is built later, it
should be a server-side allowlist that the injection sites enforce, and the
frontmatter field can come back then, meaning something.

## Install

### `npx skills add`

```bash
npx skills add stimulir/skills
```

Seven of the fourteen skills are standard-library only. Their helpers shell
out to the `stimulir` CLI rather than reimplementing REST auth, so there is no
`uv sync` to run for `connect`, `migrate-inference`, `byok-register`,
`capture-traces`, `prompt-versioning`, `eval-run`, or `eval-iterate`.

The rest call an API directly and need dependencies:

| Skill | Needs |
|---|---|
| `privacy-layer`, `usage-audit` | `httpx` |
| `voice-modalities` | `stimulir[realtime]`, since the CLI has no voice commands to shell out to |
| `web-scrape`, `deep-research`, `opposition-enrich` | `httpx`, `trafilatura` |
| `scenario-simulate` | `httpx` |

```bash
cd ~/.claude/skills/privacy-layer      # or ~/.codex/skills/privacy-layer
uv sync
```

Repeat per skill. Each owns its own `pyproject.toml`.

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills

cd ~/Developer/stimulir-skills/skills/privacy-layer
uv sync
```

Then point your host at the skill directories you want:

```bash
for s in connect migrate-inference byok-register voice-modalities capture-traces \
         privacy-layer prompt-versioning eval-run eval-iterate usage-audit \
         web-scrape deep-research opposition-enrich scenario-simulate; do
  ln -s ~/Developer/stimulir-skills/skills/$s ~/.claude/skills/$s
done
```

Swap `~/.claude/skills` for `~/.codex/skills` for Codex.

## Configuration

Most onboarding skills shell out to the `stimulir` CLI, which handles auth
itself (`stimulir login`, session cached in `~/.stimulir/`). Run `connect`
first.

Some skills call the Stimulir API directly and read `STIMULIR_API_KEY`
instead: `privacy-layer` (always), `usage-audit` (only on its REST fallback
path), and `scenario-simulate` (every simulated turn is a gateway call).
`migrate-inference`'s reference snippets document the same variable for the
adopter's own post-migration code, but the skill itself makes no network
calls. Where noted in a skill's own `install.md`, `STIMULIR_API_BASE` and
`STIMULIR_PROJECT_ID` apply too.

For the **adopter's application code** these skills steer to the
**Stimulir Python SDK** (`pip install stimulir` → `StimulirClient`):
`client.agent(...)` for one-shots, `client.request("POST",
"/api/v1/inference/chat/completions", json_body={...})` with a full
`messages` array for system prompts + conversation history, plus prompts,
data assets, and eval runs from the same client. The OpenAI-SDK
`base_url` swap remains available for non-Python codebases.

## Repo layout

```text
stimulir-skills/
├── .codex-plugin/
├── .claude-plugin/
└── skills/
    ├── connect/
    ├── migrate-inference/
    ├── byok-register/
    ├── capture-traces/
    ├── privacy-layer/
    ├── prompt-versioning/
    ├── eval-run/
    ├── eval-iterate/
    ├── usage-audit/
    ├── web-scrape/
    ├── deep-research/
    ├── opposition-enrich/
    ├── scenario-simulate/
    └── voice-modalities/
        ├── SKILL.md
        ├── README.md
        ├── install.md
        ├── pyproject.toml
        └── helpers/
```

Each skill owns its own `pyproject.toml`. There is intentionally no
repo-root `uv sync` entrypoint.
