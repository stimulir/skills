# migrate-inference

Find direct OpenAI/Anthropic SDK and raw-HTTP calls inside an **adopter's
own** application codebase and rewire them onto stimulir's OpenAI-compatible
inference gateway -- for Codex / Claude Code. Unlike the other skills in
this collection, the target of the edit is a third-party repo, not
stimulir/HybrIE itself: `helpers/scan_codebase.py` walks the adopter's
directory tree and reports every `import openai`/`OpenAI(`, `import
anthropic`/`Anthropic(`, and raw `api.openai.com`/`api.anthropic.com` call
site as structured JSON (file, line, matched pattern, category) -- it never
edits a byte of the adopter's source itself. The actual rewiring is the
agent's job, using its own reading of each call site's surrounding context.
**The preferred landing point for Python call sites is the Stimulir SDK**
(`StimulirClient` -- `client.agent()` for one-shots, `client.request()` with
a full `messages` array for system prompts + conversation history); the
OpenAI-SDK `base_url` + `api_key` swap is the fallback for non-Python
codebases or code that must stay OpenAI-SDK-shaped (stimulir's gateway
speaks the OpenAI request/response shape verbatim, so that swap is the only
change). Anthropic-SDK-shaped code has no direct compatibility and converts
to the Stimulir SDK or to the OpenAI request shape. See
[`SKILL.md`](./SKILL.md) for the full before/after diff patterns and
conversion guidance, and note the hard rule that the new `hyb_*` key always
goes in the adopter's own secrets/env setup -- never hardcoded, never
committed.

## Quick start

```bash
# 1. scan the adopter's repo -- report only, no edits
python helpers/scan_codebase.py /path/to/adopter-repo --out scan_report.json

# 2. read scan_report.json, then for each hit:
#    - openai-sdk-compatible      -> Stimulir SDK (SKILL.md step 2); base_url swap only as fallback (step 3)
#    - anthropic-sdk-needs-conversion -> Stimulir SDK (step 4 Path A) or OpenAI shape (Path B)
#    - raw-http                   -> Stimulir SDK for Python; URL+auth swap otherwise (step 5)
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including the exact
before/after diffs and the OpenAI-vs-Anthropic compatibility split) and
[`install.md`](./install.md) for setup, including where to get a
`STIMULIR_API_KEY`.
