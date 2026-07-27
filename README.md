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
| Ongoing | [`usage-audit`](./skills/usage-audit/) | Cost-per-task visibility. Runs alongside every other stage, not sequential. |

Everything past Stage 0 assumes `connect` has already run: the CLI is
installed, authenticated, and pointed at the right workspace.

## Managed skills

Agent capabilities rather than onboarding stages. These are imported into a
workspace and run in the sandbox. Inference is covered by the gateway key a
managed run already provides. A skill that also needs an external key declares
it in its own `required_secrets` frontmatter, where a managed run injects it
from the workspace vault; see that skill's `install.md` for which.

| Skill | What it does |
|---|---|
| [`web-scrape`](./skills/web-scrape/) | Plain text extraction from one URL, a list of URLs, or an index page whose links should be followed. Parallel fetch and extract, structured JSON out. No scoring and no research judgment; reach for `deep-research` when you want a cited report instead. |
| [`deep-research`](./skills/deep-research/) | Exhaustive web research: source discovery, parallel fetch/extract fan-out, cited report plus CSV. HTTP-only by default; browser-use (Chromium) optional. |
| [`opposition-enrich`](./skills/opposition-enrich/) | Competitor and opposition intelligence: discover a rival's properties, research them in parallel, extract structured attributes, compile a sourced brief for one competitor or a landscape. |
| [`scenario-simulate`](./skills/scenario-simulate/) | What-if against a described population. Materialise personas from a context, fan their reactions out through the gateway, return a segment-level distribution plus a narrative explaining the split. Market, electorate, users or workforce; resumable one timestep at a time. Output is synthetic by construction and must never be presented as measurement. |

## Install

### `npx skills add`

```bash
npx skills add stimulir/skills
```

Six of the nine onboarding skills are standard-library only. Their helpers
shell out to the `stimulir` CLI rather than reimplementing REST auth, so
there is no `uv sync` to run for `connect`, `migrate-inference`,
`byok-register`, `capture-traces`, `prompt-versioning`, or `eval-run`.

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
         privacy-layer prompt-versioning eval-run usage-audit \
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
