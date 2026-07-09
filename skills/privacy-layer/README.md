# privacy-layer

Redact/mask PII in agent-collected text before it's persisted as a data
asset or forwarded to a model -- three thin `httpx` wrappers around
Stimulir's hosted `/api/v1/privacy/capabilities`, `/api/v1/privacy/extract`,
and `/api/v1/privacy/deidentify` endpoints. CPU-only: no local NER model, no GPU,
no weight download -- every capability is a real authenticated network call
that fails loudly if `STIMULIR_API_KEY` is unset, for Codex / Claude Code.

## Why

- Stage 2 gate between "agent collected text" and "that text gets written
  somewhere" -- scraped pages, transcripts, tickets, uploaded documents can
  all carry PII an agent shouldn't silently persist or forward.
- `check_capabilities.py` lets the agent learn what entity types are
  actually supported before assuming a redaction strategy will work.
- `extract_entities.py` is read-only -- see what's in a piece of text
  without modifying it, to decide whether/how to redact.
- `deidentify.py` produces the artifact that's actually safe to persist or
  forward: `{"text": <redacted>, "redactions": <int>, "entity_types": [...]}`.
- No local fallback, by design -- if the hosted call fails, the helper
  fails loudly rather than silently skipping the privacy check.

## Quick start

```bash
export STIMULIR_API_KEY=hyb_...

# 1. what can the service detect?
python helpers/check_capabilities.py

# 2. what's in this text?
python helpers/extract_entities.py --text "Contact Jane Doe at jane@example.com"

# 3. produce the redacted artifact -- persist/forward only this output's "text"
python helpers/deidentify.py --text "Contact Jane Doe at jane@example.com" \
  --method mask --mask-char "*" --keep-tail 4
```

See [`SKILL.md`](./SKILL.md) for the full pipeline (capabilities -> extract
-> deidentify) and [`install.md`](./install.md) for setup, including where
to get a `STIMULIR_API_KEY`.
