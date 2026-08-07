# web-scrape

Plain web and social text scraping: fetch a URL, a list of URLs, or the links
off a page, then extract clean main-body text in parallel and emit structured
JSON. HTTP-only by default so it runs in a bare code-runtime sandbox with **no
API key at all**; `browser-use` (Chromium) is an optional upgrade for JS-heavy
pages. Agent-driven — you pick what to scrape, the helpers do the deterministic
fetch/extract/link fan-out. No research judgment or scoring: for a cited,
fact-checked report use the sibling `deep-research` skill instead. The core path
needs no vault key at all. `metadata.category: managed`. See
[`SKILL.md`](./SKILL.md) and [`install.md`](./install.md).
