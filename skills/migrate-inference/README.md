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
agent's job, using its own reading of each call site's surrounding context:
OpenAI-SDK-shaped code gets the lowest-friction fix (swap `base_url` +
`api_key`, same client, same method calls, works unchanged because
stimulir's gateway speaks the OpenAI request/response shape verbatim);
Anthropic-SDK-shaped code has no direct compatibility and needs converting
to the OpenAI request shape or to stimulir's native `client.agent()` SDK
call instead. See [`SKILL.md`](./SKILL.md) for the full before/after diff
patterns and conversion guidance, and note the hard rule that the new
`hyb_*` key always goes in the adopter's own secrets/env setup -- never
hardcoded, never committed.

## Quick start

```bash
# 1. scan the adopter's repo -- report only, no edits
python helpers/scan_codebase.py /path/to/adopter-repo --out scan_report.json

# 2. read scan_report.json, then for each hit:
#    - openai-sdk-compatible      -> base_url + api_key swap (SKILL.md step 2)
#    - anthropic-sdk-needs-conversion -> convert request shape or use client.agent() (SKILL.md step 3)
#    - raw-http                   -> same swap applied to the request builder (SKILL.md step 5)
```

See [`SKILL.md`](./SKILL.md) for the full playbook (including the exact
before/after diffs and the OpenAI-vs-Anthropic compatibility split) and
[`install.md`](./install.md) for setup, including where to get a
`STIMULIR_API_KEY`.
