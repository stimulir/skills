---
name: migrate-inference
description: Find direct LLM provider SDK/HTTP calls (OpenAI, Anthropic) inside an ADOPTER'S OWN application codebase and rewire them onto stimulir's OpenAI-compatible inference gateway. Use when a user wants to migrate/point their existing app's LLM calls at stimulir, add stimulir as an inference provider to a project that already calls OpenAI or Anthropic directly, or audit a repo for hardcoded provider API usage before a gateway migration.
---

# Migrate Inference

This skill is different in kind from other skills in this collection: its
job is to help the agent edit a **third-party codebase** — the adopter's own
application source — not to call stimulir's own CLI or manage stimulir-side
resources. Everything else in this repo assumes the target of the action is
stimulir/HybrIE itself; this one assumes the target is someone else's repo
that currently talks straight to OpenAI or Anthropic and wants to talk to
stimulir instead.

Because of that, the split between "detect" and "edit" is the single most
important design fact here:

- `scan_codebase.py` **only detects and reports.** It walks the adopter's
  directory tree, greps for provider-SDK/HTTP patterns, and emits structured
  JSON — file, line, matched pattern, category. It never modifies a single
  byte of the adopter's source.
- **All actual file edits are the agent's job**, done with the agent's own
  code-reading judgment — surrounding error handling, streaming vs.
  non-streaming call sites, retry/backoff wrappers, whether the client is a
  shared singleton or constructed per-request, existing env-var naming
  conventions, etc. A helper script cannot see any of that context reliably;
  blind-editing on a regex match would silently break adopter code in ways
  this skill has no way to detect. Read the surrounding function before
  touching it, every time.

## Placement rationale

This skill assumes `connect` has already run in the *agent's* environment
(stimulir CLI installed, authenticated, workspace selected) only insofar as
the agent may want to verify the new `hyb_*` key against `stimulir` CLI
commands elsewhere — but the actual migration work in this skill targets a
**different codebase** than the one the CLI is scoped to. Don't assume the
adopter's repo has the `stimulir` CLI, a stimulir config file, or any
stimulir tooling installed at all; the only things it needs, post-migration,
are network egress to `api.stimulir.com` and a `hyb_*` key in its own
secrets.

## Preflight

```bash
python3 --version                       # 3.10+
python3 -c "print('stdlib only, no imports needed for scan_codebase.py')"
```

`scan_codebase.py` is pure standard library — no dependencies to install, no
network access, no auth required. It can run against any local path the
agent can read, including a repo the agent has never seen before.

## The workflow

### 1. Scan the adopter's codebase

```bash
python helpers/scan_codebase.py <path-to-adopter-repo> [--out scan_report.json]
```

Walks the target directory (skipping `node_modules`, `.git`, `venv`,
`dist`/`build`, and similar dependency/build noise — see
`DEFAULT_EXCLUDE_DIRS` in the script) and greps every source-like file for:

- `import openai`, `from openai import ...`, `OpenAI(` / `AsyncOpenAI(`
  constructor calls, `openai.ChatCompletion` — category
  `openai-sdk-compatible`
- `import anthropic`, `from anthropic import ...`, `Anthropic(` /
  `AnthropicVertex(` / `AnthropicBedrock(` constructor calls,
  `client.messages.create(...)` — category `anthropic-sdk-needs-conversion`
- Raw `fetch`/`requests`/`httpx`/`axios`/`curl`-style string literals whose
  URL contains `api.openai.com` or `api.anthropic.com` — category
  `raw-http`

Output is one JSON report: `{target, total_hits, by_category, hits: [...]}`,
where each hit is `{file, line, pattern, category, snippet}`. This is a
**report for the agent to act on**, not an auto-fixer — read every hit
before touching anything.

### 2. For each `openai-sdk-compatible` hit: base_url + api_key swap

This is the lowest-friction migration path that exists. Because stimulir's
gateway speaks the OpenAI request/response shape verbatim (`messages`,
`model`, `stream` fields, same response envelope), **the OpenAI SDK client
object itself does not change** — only its two construction arguments do.

Before:

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
)
```

After:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["STIMULIR_API_KEY"],          # hyb_* key, not sk-*
    base_url="https://api.stimulir.com/api/v1/inference",
)
resp = client.chat.completions.create(
    model="gpt-4o",                                   # unchanged, or a stimulir-routed model id
    messages=[{"role": "user", "content": prompt}],
)
```

Nothing else in the call site changes — no different method names, no
different response parsing, streaming (`stream=True`) works the same way.
This is true in every language whose OpenAI SDK exposes a base-URL override
(Python, Node/TS, Go, etc.) — the same two-argument swap applies regardless
of language. JS/TS equivalent:

```ts
const client = new OpenAI({
  apiKey: process.env.STIMULIR_API_KEY,
  baseURL: "https://api.stimulir.com/api/v1/inference",
});
```

If the adopter's code constructs the client in one shared place (a client
singleton, a config module, a DI container), that is the *only* edit site —
resist the urge to touch every call site individually if the SDK object is
already centralized. If it's constructed ad hoc at each call site (no
central factory), that's itself worth flagging back to the user as a
pre-existing code-smell, separate from the migration.

### 3. For `anthropic-sdk-needs-conversion` hits: no direct compatibility

Stimulir's gateway is OpenAI-shaped, not Anthropic-shaped — there is no
`base_url` swap that makes the Anthropic SDK "just work" the way step 2
works for OpenAI. Two real conversion paths, pick per call site:

**Path A — rewrite the call site to the OpenAI request shape**, keeping the
`openai` SDK (add it as a new dependency if the adopter doesn't already have
it) pointed at stimulir per step 2. Concretely:

- `anthropic.Anthropic(api_key=...)` → `openai.OpenAI(api_key=<hyb_*>,
  base_url="https://api.stimulir.com/api/v1/inference")`
- `client.messages.create(model=..., max_tokens=..., messages=[...],
  system=...)` → `client.chat.completions.create(model=..., messages=[{"role":
  "system", "content": ...}, *messages], max_tokens=...)` — note Anthropic's
  separate top-level `system` param becomes a `{"role": "system", ...}`
  message in the OpenAI shape; there is no such field on the OpenAI request.
- Anthropic's content-block list response
  (`response.content[0].text`) becomes OpenAI's
  `response.choices[0].message.content` (a plain string in the
  non-tool-use case).
- Streaming: Anthropic's `client.messages.stream(...)` context-manager shape
  becomes OpenAI's `stream=True` + iterate chunks, `delta.content` per
  chunk instead of Anthropic's `event.delta.text`.

**Path B — use stimulir's native Python SDK instead of hand-rolling the
OpenAI shape** (see step 4 below) — `client.agent(prompt=..., role="user",
model=..., tags=[...])` sidesteps needing to hand-convert the request/response
envelope at all, at the cost of adopting a stimulir-specific call signature
instead of an OpenAI-compatible one. Prefer this path when the call site
doesn't need to remain provider-agnostic (i.e. the adopter isn't trying to
keep OpenAI as a fallback provider) and when tool-use/multi-turn complexity
in the existing Anthropic call would make a faithful message-shape
conversion error-prone.

Neither path is a mechanical find/replace — read the full call site
(system prompts, tool definitions, stop sequences, max_tokens semantics
differ subtly between the two APIs) before converting it.

### 4. Stimulir's native Python SDK (alternative to the OpenAI-compatible path)

```bash
pip install stimulir
# or
uv add stimulir
```

```python
from stimulir import StimulirClient

client = StimulirClient(
    api_base=None,       # defaults to STIMULIR_API_BASE / https://api.stimulir.com
    api_key=None,         # defaults to STIMULIR_API_KEY env var
    project_id=None,      # defaults to STIMULIR_PROJECT_ID env var
)

result = client.agent(
    prompt="Summarize this ticket.",
    role="user",
    model="gpt-4o",
    tags=["support-triage"],
)
```

This is the right choice when the adopter's code isn't structured around an
OpenAI-shaped client at all (e.g. converting from Anthropic per step 3's
Path B), or when the adopter wants stimulir-specific features (`tags` for
observability/routing, `project_id` scoping) that the raw OpenAI-compatible
endpoint doesn't expose as first-class request fields. It is not a strict
upgrade over step 2's `base_url` swap — for an adopter that already has
`openai`-SDK-shaped code working, step 2 is strictly less code to change.

### 5. Raw HTTP call sites (`raw-http` hits)

Same two options as an SDK call site, applied to the request builder
directly:

- Point the existing `fetch`/`requests`/`httpx` call at
  `https://api.stimulir.com/api/v1/inference/chat/completions`, keep the
  OpenAI-compatible JSON body shape (`{"model", "messages", "stream", ...}`),
  swap the `Authorization: Bearer sk-...` header for `Authorization: Bearer
  hyb_...`. Add `X-Business-Profile-Id` / `X-Project-Id` headers if the
  adopter is scoping to a specific stimulir project.
- If the existing raw call was already building an Anthropic-shaped body
  (`/v1/messages`, `max_tokens` at top level, content-block responses),
  it needs the same request/response conversion as step 3's Path A before
  it can point at stimulir's endpoint — the body shape has to change, not
  just the URL and auth header.

### 6. Where the new key goes — never in source

The new `hyb_*` key belongs in the **adopter's own** secrets/env
configuration — `.env` (untracked, in `.gitignore`), the adopter's secret
manager (AWS Secrets Manager, GCP Secret Manager, Vault, etc.), or their
CI/CD platform's encrypted secrets store (GitHub Actions secrets, GitLab CI
variables, etc.) — matching however that adopter already manages
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` today. Never hardcode it into a
source file, a config file that gets committed, a Dockerfile `ENV`
instruction, or a docstring/comment as an example value. If the adopter's
existing `OPENAI_API_KEY` was already in a tracked file (a real, if bad,
possibility in some repos), flag that as a pre-existing issue rather than
perpetuating it for the new key.

## Integration surface reference

| Path | Shape | Auth |
|---|---|---|
| Gateway REST endpoint | `POST https://api.stimulir.com/api/v1/inference/chat/completions` — OpenAI-compatible `messages`/`model`/`stream` request and response | `Authorization: Bearer hyb_*` + optional `X-Business-Profile-Id` / `X-Project-Id` |
| OpenAI SDK, redirected | Same `openai.OpenAI(...)` / `new OpenAI(...)` client shape, only `base_url` + `api_key` change | `api_key` = `hyb_*` |
| Stimulir Python SDK | `pip install stimulir` / `uv add stimulir`; `StimulirClient(api_base=None, api_key=None, project_id=None)`; `client.agent(prompt=..., role='user', model=..., tags=[...])` | Env: `STIMULIR_API_KEY`, `STIMULIR_API_BASE`, `STIMULIR_PROJECT_ID` |
| Anthropic SDK call sites | **No direct compatibility.** Convert to OpenAI request shape (step 3, Path A) or to `client.agent()` (step 3, Path B) | n/a |

## Anti-patterns (do NOT do)

- **Blind-editing source files based on `scan_codebase.py` output alone.**
  A regex hit tells you *where* to look, not *how* to safely change it. Read
  the full call site — error handling, retries, streaming, shared client
  construction — before writing a diff.
- **Auto-applying the base_url/api_key swap across every hit in one pass
  without reading each file.** Even the "lowest-friction" OpenAI-compatible
  path can hit adopter-specific wrinkles (a subclassed client, a monkeypatch,
  a test double that asserts on the old base URL) that only show up on
  inspection.
- **Treating `anthropic`-SDK hits as a base_url swap.** There is no
  compatibility shim — the request/response shape genuinely differs
  (top-level `system`, content-block responses, different streaming
  events). Skipping the conversion step produces code that imports the
  Anthropic SDK but talks to an OpenAI-shaped endpoint, which fails at
  runtime, not at review time.
- **Hardcoding the new `hyb_*` key anywhere in the adopter's committed
  source** — not in a "just for now" test file, not in a comment showing
  "how to configure it," not in a Dockerfile. It goes in the adopter's own
  env/secrets plane, exactly where their old provider key already lived.
- **Extending `scan_codebase.py` to also perform the edit.** Its contract is
  detect-and-report; if a future version needs an auto-fix mode, that is a
  new, explicitly-named helper with its own `--dry-run`/`--confirm-required`
  posture — not a silent capability bolted onto the scanner.
- **Assuming the adopter repo has the `stimulir` CLI, `~/.stimulir/`
  session, or any stimulir tooling present.** This skill's target is
  someone else's codebase; don't gate the scan or the edit guidance on
  stimulir CLI state that has nothing to do with that repo.
- **Skipping the scan and jumping straight to editing** because "I already
  know this repo only uses OpenAI." Run `scan_codebase.py` anyway — it
  catches raw-HTTP call sites and secondary files (test doubles, scripts,
  notebooks) that a quick mental scan misses, and the JSON report is cheap
  to produce.
