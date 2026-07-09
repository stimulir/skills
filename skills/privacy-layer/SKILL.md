---
name: privacy-layer
description: Redact/mask PII (names, emails, phone numbers, SSNs, addresses, etc.) in agent-collected text BEFORE it is persisted as a data asset or forwarded to a model. Use whenever an agent has scraped, transcribed, extracted, or otherwise collected free text from an untrusted or user-facing source and needs to know what PII it contains, or needs to redact it, before writing it to storage, a data asset, a log, or a prompt sent to any model. CPU-only, no GPU/model-weight cost -- three thin wrappers around Stimulir's hosted privacy REST endpoints.
---

# Privacy Layer

This skill sits between "agent collected some text" and "that text gets
written somewhere or sent to a model." It is a Stage 2 gate, not a
detector of its own -- all the actual entity recognition and redaction
logic lives behind Stimulir's hosted `/api/v1/privacy/*` endpoints. This skill
is three dumb, single-purpose wrappers around those endpoints plus the
orchestration guidance for when to call which one.

**Why this needs to exist as its own skill, not inline agent logic:** any
agent that collects text from an external, untrusted, or user-facing
source (scraped pages, form submissions, call transcripts, support
tickets, uploaded documents) can end up persisting or forwarding PII it
never meant to retain -- into a data asset, a vector store, a log line, or
a prompt sent to a third-party model. Redaction needs to be a deliberate,
auditable step the agent takes before that write/forward happens, not
something left to chance or to the downstream model's own judgment.

**CPU-only, no local model weights.** Every capability here is a real
network call to Stimulir's hosted privacy plane -- there is no local NER
model, no GPU, no weight download. If the network call fails, this skill
has no local fallback; it fails loudly (see Anti-patterns).

## Placement / capability rationale

This skill assumes `connect` has already run -- CLI installed,
authenticated, workspace selected. It does not re-document that setup.

The three helpers wrap the three endpoints directly via `httpx`, not via
`stimulir privacy ...` CLI shell-outs, matching the exact precedent already
established in the sibling `agentic-frame` repo's `evidence-clip` skill
(`helpers/deid_transcript.py`, which calls this same
`/api/v1/privacy/deidentify` endpoint). That precedent is the reference
implementation for this entire skill: same `STIMULIR_API_URL` env var
(default `https://api.stimulir.com`), same `/api/v1/privacy/...` path
prefix, same `Authorization: Bearer {STIMULIR_API_KEY}` header, same
loud-failure-on-missing-key behavior. This skill's helpers exist so that
callers who need this capability outside a video/transcript context (e.g.
a scraping agent, a support-ticket ingestion agent, a data-asset writer)
don't have to depend on `evidence-clip` or reimplement the same three
calls.

## Preflight

```bash
python3 -c "import httpx; print('httpx ok')"
echo "${STIMULIR_API_KEY:+STIMULIR_API_KEY is set}"
```

`STIMULIR_API_KEY` is required for every helper in this skill -- there is
no capability here that works without it, unlike `evidence-clip` where
extraction/provenance/media-painting are local-only. If the key is unset,
every helper refuses to run rather than silently skipping the privacy
check.

## The pipeline

The three helpers map onto three distinct questions, in the order an agent
should typically ask them:

1. **"What can this service even detect?"** -- `check_capabilities.py`.
   Call this once per session (or whenever you need to decide a redaction
   strategy) to learn what entity types and methods are actually
   supported, before assuming a given PII category (e.g. "national ID
   numbers") is covered.
2. **"What's actually in THIS text?"** -- `extract_entities.py`. Call this
   to see what would be found in a specific piece of collected text,
   without modifying it. Useful for deciding whether redaction is even
   needed, or for choosing `deidentify.py` parameters (e.g. whether
   `--keep-tail` makes sense for an account number found in the text).
3. **"Produce the safe artifact"** -- `deidentify.py`. Call this to get
   back the redacted text. **Persist or forward only this helper's
   `text` output** -- never the original collected text -- once you've
   decided redaction is warranted.

### 1. Discover capabilities

```bash
python helpers/check_capabilities.py
```

Wraps `GET /api/v1/privacy/capabilities`. No arguments -- capabilities are a
property of the service, not of any input text. Prints the server's JSON
response verbatim to stdout (the response shape is not independently
confirmed the way `deidentify`'s is, so this helper does not destructure,
rename, or invent fields -- treat whatever keys come back as the ground
truth for what the other two helpers can actually do).

### 2. Extract entities (read-only, no redaction)

```bash
python helpers/extract_entities.py --text "Contact Jane Doe at jane@example.com or 555-123-4567"
```

Wraps `POST /api/v1/privacy/extract` with body `{"text": ...}`. Prints the
server's JSON response verbatim to stdout -- same reasoning as
`check_capabilities.py`: the response shape isn't confirmed against
source, so no field is renamed or invented. This call does NOT modify the
text; it's purely informational. Use it to decide whether redaction is
warranted at all, and to sanity-check that `deidentify.py`'s
`entity_types` output afterward matches what you expected to see.

### 3. De-identify (produces the artifact you actually persist/forward)

```bash
python helpers/deidentify.py --text "Contact Jane Doe at jane@example.com or 555-123-4567"

# with explicit masking parameters
python helpers/deidentify.py --text "..." --method mask --mask-char "*" --keep-tail 4
```

Wraps `POST /api/v1/privacy/deidentify` with body `{"text": ...}` plus
`method`/`mask_char`/`keep_tail` only when those flags are explicitly
supplied (omitted from the request body otherwise, so the server's own
default behavior applies -- this helper never guesses a default on your
behalf). Confirmed response shape (matches `evidence-clip`'s
`deid_transcript.py`, same endpoint, same Rust source struct):

```json
{"text": "<redacted text>", "redactions": <int>, "entity_types": ["<str>", ...]}
```

This helper's stdout is JSON with exactly these three fields --
`text`, `redactions`, `entity_types` -- nothing invented, nothing dropped.
A human-readable one-line summary (`redacted N span(s), entity types: [...]`)
also goes to stderr for quick eyeballing, but the machine-consumable
contract is the stdout JSON.

**The redacted `text` field is what gets persisted as the data asset or
forwarded to a model -- never the original `--text` input.**

## CLI reference

| Helper | Endpoint | Method | Required flags | Optional flags |
|---|---|---|---|---|
| `check_capabilities.py` | `/api/v1/privacy/capabilities` | GET | none | none |
| `extract_entities.py` | `/api/v1/privacy/extract` | POST | `--text` | none |
| `deidentify.py` | `/api/v1/privacy/deidentify` | POST | `--text` | `--method`, `--mask-char`, `--keep-tail` |

All three read `STIMULIR_API_URL` (default `https://api.stimulir.com`) and
require `STIMULIR_API_KEY` (a `hyb_*` key -- see `install.md`). All three
exit non-zero with a clear message on missing key, network failure, or
non-200 response -- there is no silent failure mode.

`extract_entities.py` and `deidentify.py` accept text either via `--text`
or on stdin (omit `--text` and pipe the text in instead) -- prefer stdin
when the text itself is sensitive, since command-line arguments are
visible in `ps` output and shell history:

```bash
echo "Contact Jane Doe at jane@example.com" | python helpers/deidentify.py
```

## Output contract

Every helper prints exactly one JSON object to stdout on success and
nothing else on stdout (diagnostic text goes to stderr only). This makes
each helper safe to pipe into `jq` or capture directly as a subprocess
result:

- `check_capabilities.py` -> server's capabilities response, verbatim.
- `extract_entities.py` -> server's extraction response, verbatim.
- `deidentify.py` -> `{"text": ..., "redactions": ..., "entity_types": [...]}`.

On any failure (missing key, network error, non-200), the helper raises
`SystemExit` with a descriptive message and a non-zero exit code -- no
JSON is printed to stdout in the failure case.

## Anti-patterns (do NOT do)

- **Persisting or forwarding the original, pre-redaction text** after
  calling `deidentify.py`. The whole point of this skill is that only the
  `text` field of the response -- the redacted version -- is safe to write
  to a data asset, a log, or a model prompt. Keeping the original around
  "just in case" after redaction defeats the purpose of calling this skill
  at all.
- **Treating `redactions == 0` as proof the text is clean.** A zero count
  means the service found nothing to redact *among the entity types it
  currently supports* -- it is not a guarantee the text contains no PII by
  any definition. Cross-check against `check_capabilities.py` if the
  category you care about might not be covered, and don't present a
  zero-redaction result to a user as "verified PII-free."
- **Calling any helper without `STIMULIR_API_KEY` set and expecting a
  local fallback.** There isn't one -- every capability in this skill is a
  real hosted call, not an optional enhancement. All three helpers refuse
  to run and exit non-zero rather than silently skipping the privacy
  check.
- **Logging or printing the raw `--text` input** anywhere in a wrapper
  script, error message, or debug trace built on top of these helpers.
  None of the three helpers themselves echo the input text back (only
  `extract_entities.py`'s and `deidentify.py`'s server *responses* are
  printed, which is the point of calling them) -- don't add logging around
  them that reintroduces the leak this skill exists to prevent.
- **Assuming `deidentify.py`'s response carries match offsets or original
  matched values.** It does not -- the confirmed response shape is exactly
  `text`/`redactions`/`entity_types`. If a downstream step needs to know
  *where* in the original text a redaction happened (e.g. to align with
  timestamps in an evidence-clip-style workflow), that's a text diff the
  agent must do itself; this endpoint doesn't provide it.
- **Guessing at `extract_entities.py` or `check_capabilities.py` response
  field names in downstream code.** Their shapes are not independently
  confirmed against source the way `deidentify`'s is. Both helpers print
  the server's JSON verbatim for exactly this reason -- treat whatever
  keys actually come back as authoritative, don't hardcode assumptions
  about field names beyond what a live call returns.
- **Always sending `method`/`mask_char`/`keep_tail` in the `deidentify`
  request body even when the caller didn't ask for them.** This helper
  only includes those fields when the corresponding flag is explicitly
  passed, so the server's own default redaction behavior applies
  otherwise. Don't hardcode a default value into the wrapper on the
  server's behalf.
- **Skipping `extract_entities.py` and jumping straight to `deidentify.py`
  "to save a call"** when the downstream decision actually depends on
  knowing what's in the text first (e.g. choosing `--keep-tail`, or
  deciding redaction isn't needed at all). The extra call is cheap; a
  wrong redaction parameter chosen blind is not.
- **Passing sensitive text via `--text` when stdin is available.** Command
  arguments show up in `ps`, shell history, and process-listing tools on
  shared machines -- for a skill whose entire job is not leaking PII,
  putting the raw pre-redaction text in argv is a subtle self-defeat. Pipe
  the text on stdin instead whenever the caller controls how the helper is
  invoked.
