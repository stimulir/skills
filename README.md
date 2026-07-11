# stimulir-skills

Agent skills for integrating the [Stimulir](https://www.stimulir.com) AI
gateway into your own product. Each skill is a self-contained directory a
coding agent (Claude Code, Codex, or any agent that reads `SKILL.md` files)
can install and use directly — installed by you, the adopting engineer or
product person, and handed to whichever agent you already run.

Stimulir's own positioning is "one gateway, every AI workflow, gets sharper
as it runs" — the gateway swap is table stakes, the real differentiator is
the feedback loop from live traffic back into better inference. These
skills are sequenced to match that: get connected, wire your existing code
onto the gateway, then turn the feedback loop on.

## The onboarding journey

| Stage | Skill | What it does |
|---|---|---|
| 0 — Connect | [`connect`](./skills/connect/) | Install the CLI, authenticate, create a workspace-scoped key, send one real inference call, confirm the cost shows up. Minutes, not hours. |
| 1 — Migrate | [`migrate-inference`](./skills/migrate-inference/) | Scan your own codebase for direct OpenAI/Anthropic calls and rewire them onto Stimulir — the Stimulir Python SDK (`StimulirClient`) is the preferred landing point; the OpenAI-compatible `base_url` swap is the fallback for non-Python code. |
| 1 — Migrate (alt) | [`byok-register`](./skills/byok-register/) | Keep your existing provider contract — register your own key with Stimulir instead of switching to managed inference. |
| 1 — Migrate (voice) | [`voice-modalities`](./skills/voice-modalities/) | Wire voice onto the gateway: one realtime WebSocket covers speech-to-speech, live transcription, and verbatim text-to-speech — omni-model native, verified live. |
| 2 — Flywheel | [`capture-traces`](./skills/capture-traces/) | Turn live traffic into curated data assets (Raw → Cleaning → Clean View → Snapshot). This is the mechanism behind "gets sharper as it runs." |
| 2 — Flywheel | [`privacy-layer`](./skills/privacy-layer/) | Redact/mask PII before it's captured or forwarded — sequence this *before* `capture-traces`, since captured traces become future training data. |
| 3 — Close the loop | [`prompt-versioning`](./skills/prompt-versioning/) | Version and label prompts instead of hardcoding strings; promote through environments deliberately. |
| 3 — Close the loop | [`eval-run`](./skills/eval-run/) | Compare a prompt or model change against a curated dataset before promoting to prod. |
| Ongoing | [`usage-audit`](./skills/usage-audit/) | Cost-per-task visibility — runs alongside every other stage, not sequential. |

Everything past Stage 0 assumes `connect` has already run — the CLI is
installed, authenticated, and pointed at the right workspace.

## What's deliberately not here

Real GPU training jobs (SFT/RL/D2L/projector runs), compute
provisioning/teardown, API key or BYOK-credential revocation, destructive
data operations, and the Stimulir CLI Agent's attach-and-execute loop are
all out of scope for this repo. Those either spend real money, destroy
state irreversibly, or — in the CLI Agent's case — are a standing session
loop, which breaks the same "no skill becomes a server" rule these skills
otherwise follow. Use the Stimulir CLI or console directly for those, with
a human confirming every step.

## Install

### `npx skills add`

```bash
npx skills add stimulir/skills
```

Six of the nine skills are standard-library only — their helpers shell
out to the `stimulir` CLI rather than reimplementing REST auth, so there's
no `uv sync` to run for `connect`, `migrate-inference`, `byok-register`,
`capture-traces`, `prompt-versioning`, or `eval-run`. Three call the
Stimulir API directly and need dependencies: `privacy-layer` and
`usage-audit` (`httpx`), and `voice-modalities` (`stimulir[realtime]` —
the CLI has no voice commands to shell out to):

```bash
cd ~/.claude/skills/privacy-layer      # or ~/.codex/skills/privacy-layer
uv sync   # installs httpx

cd ~/.claude/skills/usage-audit
uv sync   # installs httpx

cd ~/.claude/skills/voice-modalities
uv sync   # installs stimulir[realtime]
```

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills

cd ~/Developer/stimulir-skills/skills/privacy-layer
uv sync   # installs httpx

cd ~/Developer/stimulir-skills/skills/usage-audit
uv sync   # installs httpx
```

Then point your host at the skill directories you want:

```bash
for s in connect migrate-inference byok-register voice-modalities capture-traces \
         privacy-layer prompt-versioning eval-run usage-audit; do
  ln -s ~/Developer/stimulir-skills/skills/$s ~/.claude/skills/$s
done
```

Swap `~/.claude/skills` for `~/.codex/skills` for Codex.

## Configuration

Most skills shell out to the `stimulir` CLI, which handles auth itself
(`stimulir login`, session cached in `~/.stimulir/`) — run `connect` first.
A few skills call the Stimulir API directly instead: `privacy-layer`
(always) and `usage-audit` (only for its REST fallback path) read
`STIMULIR_API_KEY`; `migrate-inference`'s reference snippets document the
same env var for the adopter's own post-migration code, but the skill
itself makes no network calls. Where noted in a skill's own `install.md`,
`STIMULIR_API_BASE` / `STIMULIR_PROJECT_ID` apply too.

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
    └── voice-modalities/
        ├── SKILL.md
        ├── README.md
        ├── install.md
        ├── pyproject.toml
        └── helpers/
```

Each skill owns its own `pyproject.toml`. There is intentionally no
repo-root `uv sync` entrypoint.
