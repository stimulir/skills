# deep-research

Exhaustive web research: discover sources with Serper, fetch and extract many
in parallel, synthesize a cited report and CSV. HTTP-only by default so it runs
in a bare code-runtime sandbox; `browser-use` (Chromium) is an optional upgrade
for JS-heavy pages. Agent-driven — the skill does the judgment, the helpers do
the deterministic fan-out. Declares `required_secrets: [SERPER_API_KEY]` so a
managed run knows exactly which vault key to inject. See
[`SKILL.md`](./SKILL.md) and [`install.md`](./install.md).
