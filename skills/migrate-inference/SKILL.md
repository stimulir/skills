---
name: migrate-inference
description: Find direct LLM provider SDK/HTTP calls (OpenAI, Anthropic) inside an ADOPTER'S OWN application codebase and rewire them onto stimulir — preferring the Stimulir Python SDK (StimulirClient) as the landing point, with the OpenAI-compatible base_url swap as the fallback for non-Python or must-stay-OpenAI-shaped code. Use when a user wants to migrate/point their existing app's LLM calls at stimulir, add stimulir as an inference provider to a project that already calls OpenAI or Anthropic directly, or audit a repo for hardcoded provider API usage before a gateway migration.
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
- `import google.generativeai` (legacy), `from google import genai` /
  `genai.Client(` (current), `GenerativeModel(` / `.generate_content(`,
  `import vertexai` / `aiplatform` (Vertex) — category
  `google-gemini-needs-conversion`
- Raw `fetch`/`requests`/`httpx`/`axios`/`curl`-style string literals whose
  URL contains `api.openai.com`, `api.anthropic.com`,
  `generativelanguage.googleapis.com`, or `*-aiplatform.googleapis.com` —
  category `raw-http`

Output is one JSON report: `{target, total_hits, by_category, hits: [...]}`,
where each hit is `{file, line, pattern, category, snippet}`. This is a
**report for the agent to act on**, not an auto-fixer — read every hit
before touching anything.

### 2. Default for Python call sites: migrate to the Stimulir SDK

**This is the preferred landing point for every Python hit** — OpenAI-SDK,
Anthropic-SDK, or raw-HTTP alike. The Stimulir SDK is the first-class
integration surface: it carries workspace/project scope on the `hyb_*` key
(no headers to hand-roll), attaches `tags` for trace attribution, and the
same client object later drives prompts, data assets, and eval runs when the
adopter turns the flywheel on (`capture-traces`, `eval-run`) — none of which
the redirected OpenAI SDK can reach.

```bash
pip install stimulir        # or: uv add stimulir
```

```python
from stimulir import StimulirClient

client = StimulirClient()   # reads STIMULIR_API_KEY / STIMULIR_API_BASE / STIMULIR_PROJECT_ID

# One-shot prompt — simplest call shape:
result = client.agent(
    prompt="Summarize this ticket.",
    model="stimulir/claude-sonnet-4-6",
    tags=["support-triage"],
)
print(result.content)       # AgentResponse: .content .status .cost .token_usage .error
```

For a **system prompt + multi-turn conversation history** (the common
production shape), send the full OpenAI-compatible `messages` array through
the same client — `client.agent()` is deliberately a one-shot helper, not
the multi-turn path:

```python
resp = client.request("POST", "/api/v1/inference/chat/completions", json_body={
    "model": "stimulir/claude-sonnet-4-6",
    "messages": [
        {"role": "system",    "content": "You are a concise assistant."},
        {"role": "user",      "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
        {"role": "user",      "content": "follow-up"},
    ],
    "max_tokens": 800,
})
print(resp["choices"][0]["message"]["content"])
```

Model-id guidance when rewriting call sites:

- `stimulir/claude-sonnet-4-6` / `stimulir/claude-opus-4-6` — managed
  frontier Claude on Stimulir's own capacity; no provider key needed.
- `stimulir/fusion` / `stimulir/fusion-max` — panel+judge virtual models.
- `zai-org/GLM-5.2`, `moonshotai/Kimi-K2.6`, `MiniMaxAI/MiniMax-M2.5`,
  `Qwen/Qwen2.5-VL-72B-Instruct` — managed open models.
- Bare vendor ids (`claude-sonnet-4-6`, `gpt-4o`, `gemini-2.5-pro`) route
  through the workspace's own BYOK credential when one is registered (see
  `byok-register`); without one they fall to Stimulir's managed floor.
- Set `max_tokens` generously (≥800): several managed models are reasoning
  models, and a tight cap can be consumed by reasoning before any visible
  output is emitted.

### 3. Fallback: OpenAI-compatible base_url + api_key swap

Use this instead of step 2 when the call site **cannot adopt the Stimulir
SDK**: non-Python codebases (Node/TS, Go, Ruby — the Stimulir SDK is
Python-only today), or Python code that must stay provider-agnostic behind
the OpenAI SDK interface. Because stimulir's gateway speaks the OpenAI
request/response shape verbatim (`messages`, `model`, `stream` fields, same
response envelope), **the OpenAI SDK client object itself does not change**
— only its two construction arguments do.

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

### 4. For `anthropic-sdk-needs-conversion` hits: no direct compatibility

Stimulir's gateway is OpenAI-shaped, not Anthropic-shaped — there is no
`base_url` swap that makes the Anthropic SDK "just work" the way step 3
works for OpenAI. Two real conversion paths, pick per call site:

**Path A (preferred) — convert to the Stimulir SDK** per step 2.
`client.agent(prompt=..., model=..., tags=[...])` for one-shots, or
`client.request("POST", "/api/v1/inference/chat/completions", json_body=...)`
with a full `messages` array for multi-turn — Anthropic's separate top-level
`system` param simply becomes the leading `{"role": "system", ...}` message.
This sidesteps hand-converting the request/response envelope onto a second
vendor SDK, and lands the adopter on the client that also drives prompts,
data assets, and evals later. Prefer this whenever the call site doesn't
need to remain OpenAI-SDK-shaped for provider-agnostic fallback reasons.

**Path B — rewrite the call site to the OpenAI request shape**, keeping the
`openai` SDK (add it as a new dependency if the adopter doesn't already have
it) pointed at stimulir per step 3. Concretely:

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

Neither path is a mechanical find/replace — read the full call site
(system prompts, tool definitions, stop sequences, max_tokens semantics
differ subtly between the two APIs) before converting it.

### 4b. For `google-gemini-needs-conversion` hits: no direct compatibility

Gemini's SDKs (`google-generativeai`, `google-genai`) and Vertex
(`vertexai` / `aiplatform`) speak neither the OpenAI nor the Anthropic
request shape, so — like Anthropic — a `base_url` swap won't work. Same two
paths, same preference:

**Path A (preferred) — convert to the Stimulir SDK** per step 2.
`client.agent(prompt=..., model="gemini-2.5-flash", ...)` for one-shots, or
`client.request("POST", "/api/v1/inference/chat/completions", json_body=...)`
with a full `messages` array for multi-turn. Concretely for the current
`google-genai` SDK:

- `genai.Client(api_key=...)` → `StimulirClient()` (key from
  `STIMULIR_API_KEY`).
- `client.models.generate_content(model="gemini-2.5-flash",
  contents=...)` → `client.request(..., json_body={"model":
  "gemini-2.5-flash", "messages": [...]})`. Gemini's `contents` list (parts
  with `role: "user"|"model"`) becomes the OpenAI `messages` array —
  Gemini's `"model"` role maps to `"assistant"`; a top-level
  `system_instruction` becomes a leading `{"role": "system", ...}` message.
- Gemini's `response.text` (or `response.candidates[0].content.parts[0].text`)
  becomes `resp["choices"][0]["message"]["content"]`.
- Streaming: `generate_content_stream(...)` / `stream=True` chunks'
  `chunk.text` become OpenAI `delta.content`.
- Multimodal parts (inline image/audio) map to OpenAI content-part lists
  (`{"type": "image_url", ...}`) — see the vision/audio parts the gateway
  already accepts.

**Path B — OpenAI request shape** per step 3, keeping the `openai` SDK
pointed at Stimulir. Note Gemini and Vertex go through the *same* Stimulir
model ids (`gemini-2.5-flash`, etc.) regardless of which Google SDK the
adopter started from; the provider is resolved by the workspace's BYOK
credential (see `byok-register`), not by the client library.

Neither path is a mechanical find/replace — Gemini's `safety_settings`,
`generation_config` (temperature/top_k/max_output_tokens), and tool/function
declarations differ from the OpenAI shape; read the full call site first.

### 5. Raw HTTP call sites (`raw-http` hits)

Same preference order as the SDK call sites, applied to the request builder
directly:

- **Python call sites: replace the hand-rolled request with the Stimulir
  SDK** (step 2) — `client.request("POST",
  "/api/v1/inference/chat/completions", json_body=...)` keeps the exact same
  OpenAI-compatible body the raw call was already building, and deletes the
  bespoke auth/base-URL/error plumbing around it.
- Non-Python call sites: point the existing `fetch`/`axios`/`curl` call at
  `https://api.stimulir.com/api/v1/inference/chat/completions`, keep the
  OpenAI-compatible JSON body shape (`{"model", "messages", "stream", ...}`),
  swap the `Authorization: Bearer sk-...` header for `Authorization: Bearer
  hyb_...`. Add `X-Business-Profile-Id` / `X-Project-Id` headers if the
  adopter is scoping to a specific stimulir project.
- If the existing raw call was already building an Anthropic-shaped body
  (`/v1/messages`, `max_tokens` at top level, content-block responses),
  it needs the same request/response conversion as step 4's Path B before
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
| **Stimulir Python SDK (preferred)** | `pip install stimulir` / `uv add stimulir`; `StimulirClient()`; `client.agent(prompt=..., model=..., tags=[...])` for one-shots, `client.request("POST", "/api/v1/inference/chat/completions", json_body={model, messages:[...]})` for system-prompt + multi-turn history | Env: `STIMULIR_API_KEY`, `STIMULIR_API_BASE`, `STIMULIR_PROJECT_ID` (key carries workspace scope) |
| OpenAI SDK, redirected (fallback) | Same `openai.OpenAI(...)` / `new OpenAI(...)` client shape, only `base_url` + `api_key` change — for non-Python or must-stay-OpenAI-shaped code | `api_key` = `hyb_*` |
| Gateway REST endpoint | `POST https://api.stimulir.com/api/v1/inference/chat/completions` — OpenAI-compatible `messages`/`model`/`stream` request and response | `Authorization: Bearer hyb_*` + optional `X-Business-Profile-Id` / `X-Project-Id` |
| Anthropic SDK call sites | **No direct compatibility.** Convert to the Stimulir SDK (step 4, Path A) or to the OpenAI request shape (step 4, Path B) | n/a |
| Gemini / Vertex SDK call sites | **No direct compatibility.** Convert to the Stimulir SDK (step 4b, Path A) or to the OpenAI request shape (step 4b, Path B); same Stimulir model ids either way | n/a |

## Anti-patterns (do NOT do)

- **Defaulting Python call sites to the redirected OpenAI SDK when the
  Stimulir SDK fits.** The base_url swap is the fallback for non-Python or
  deliberately provider-agnostic code, not the default — a Python adopter
  landed on the OpenAI SDK never reaches `tags`, project scoping, prompts,
  data assets, or eval runs without a second migration later.
- **Using `client.agent()` for multi-turn conversations.** It is a one-shot
  helper (single prompt + role). System prompts and conversation history go
  through `client.request(...)` with a full OpenAI-shaped `messages` array —
  do not build a fake transcript by concatenating turns into one prompt
  string.
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
- **Reading a zero-hit scan as "nothing to migrate."** The scanner matches
  known provider surfaces (OpenAI, Anthropic, Gemini/Vertex, and their raw
  hosts). A codebase can still have a real inference layer the scan can't
  see: a house-rolled LLM wrapper, an unlisted provider (Mistral, Cohere,
  Together, Bedrock via boto3), a proxy/gateway indirection, or calls behind
  a local helper module. When `total_hits` is 0, do NOT conclude the repo is
  clean — confirm it against the repo's own architecture (grep for the
  model-id strings it uses, its LLM config, its `requirements`/`package.json`
  provider deps) before reporting "nothing to migrate." The scan is a
  fast first pass, not proof of absence.
