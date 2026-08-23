# Stimulir Skills

Operator skills for connecting an adopter repository to
[Stimulir](https://www.stimulir.com), capturing production evidence, evaluating
changes, running diagnostic RSI, and promoting a reviewed winner.

These skills run with a coding agent such as Codex or Claude Code. They operate
from the adopter repository through the Stimulir CLI or SDK and do not run as
workspace-managed sandbox capabilities.

For sandbox-managed research, scraping, intelligence, and simulation skills,
use [`stimulir/managed-skills`](https://github.com/stimulir/managed-skills).

## Lifecycle

| Stage | Skill | Responsibility |
|---|---|---|
| 0. Connect | [`connect`](./skills/connect/) | Install the CLI and establish authenticated workspace context without handling credentials or spend. |
| 1. Migrate | [`migrate-inference`](./skills/migrate-inference/) | Replace direct provider calls in an adopter application with the Stimulir SDK or compatible gateway. |
| 1. Migrate | [`byok-register`](./skills/byok-register/) | Hand secret entry to the Console, then inspect and verify the non-secret credential record. |
| 1. Voice | [`voice-modalities`](./skills/voice-modalities/) | Generate speech, transcribe audio, run realtime voice, or integrate the voice lane. |
| 2. Protect | [`privacy-layer`](./skills/privacy-layer/) | De-identify sensitive text before persistence or forwarding. |
| 2. Capture | [`capture-traces`](./skills/capture-traces/) | Turn live traffic into curated, immutable data assets. |
| 3. Version | [`prompt-versioning`](./skills/prompt-versioning/) | Manage prompts as immutable versions and environment labels. |
| 3. Measure | [`eval-run`](./skills/eval-run/) | Start or inspect one durable comparison against a curated cohort. |
| 3. Iterate | [`eval-iterate`](./skills/eval-iterate/) | Advance an eval lineage by exactly one branch. |
| 3. Diagnose | [`rsi`](./skills/rsi/) | Run one action against the durable diagnostic hill-climb controller. |
| 3. Promote | [`eval-promote`](./skills/eval-promote/) | Review and apply one promotion proposal with explicit human authorization. |
| Ongoing | [`usage-audit`](./skills/usage-audit/) | Read cost, usage, and billing evidence without changing state. |

The normal sequence is:

```text
connect → human credential setup if needed → migrate → privacy → capture → version → evaluate or RSI → review → promote
```

Promotion is intentionally separate. Capture, evaluation, iteration, and RSI
must never silently move a production label.

## Runtime contracts

The catalog contains 12 skills:

| Category | Count | Contract |
|---|---:|---|
| `operator` | 11 | Performs one bounded adopter-side action through the Stimulir CLI or SDK and returns. |
| `loop` | 1 | Advances persisted console-side state by exactly one iteration and returns. |

`rsi` is categorized as an operator because the server owns its durable loop.
The coding agent issues one `run`, `status`, `overview`, `continue`, or steering
action; it does not poll or recreate the controller.

The `metadata.category` field is retained as the repository's runtime contract.
It is not a secret allowlist or a generic metadata namespace.

## Install

Install the catalog into a skill-aware coding agent:

```bash
npx skills add stimulir/skills
```

Or clone and symlink selected packages:

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills

for s in connect migrate-inference byok-register voice-modalities capture-traces \
         privacy-layer prompt-versioning eval-run eval-iterate eval-promote rsi usage-audit; do
  ln -s ~/Developer/stimulir-skills/skills/$s ~/.codex/skills/$s
done
```

Use `~/.claude/skills` instead for Claude Code.

All 12 packages use the installed Stimulir CLI. No per-skill Python
environment or dependency installation is required. The migration scanner is
standard-library-only and runs locally without network access.

## Authentication

Operator skills resolve the adopter project's Stimulir context without printing
secrets. For application work, prefer a project-local environment:

```dotenv
STIMULIR_API_BASE=https://api.stimulir.com
STIMULIR_API_KEY=hyb_...
STIMULIR_PROJECT_ID=...
```

A `hyb_*` application key is workspace-pinned and does not require a human CLI
workspace export. Human `stim_cli_*` sessions are bound to the workspace
approved in the browser; to use another workspace, select it in the Console and
log in again.

## Repository layout

```text
skills/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
└── skills/
    ├── connect/
    ├── migrate-inference/
    ├── byok-register/
    ├── voice-modalities/
    ├── privacy-layer/
    ├── capture-traces/
    ├── prompt-versioning/
    ├── eval-run/
    ├── eval-iterate/
    ├── rsi/
    ├── eval-promote/
    └── usage-audit/
```
