---
name: web-scrape
description: Plain web and social text scraping — give it one URL, a list of URLs, or a page whose links should be followed, and it fetches and extracts clean main-body text in parallel, emitting structured JSON (and optionally concatenated text/markdown). Use when the user just wants the text of some pages: "scrape this page", "get the text of these links", "pull the articles off this index page", "grab this public profile/post." Agent-driven: you pick what to scrape; the helpers do the deterministic fetch + extract. No research judgment, no scoring — reach for deep-research when the user wants a fact-checked, cited report instead.
required_secrets: []
---

# Web Scrape

The plain "get me the text of these pages" skill: **fetch → extract → (optionally
follow links and fan out)**. You (the agent) decide *what* to scrape — one page,
a list, or the links off an index page. The helpers do only the deterministic,
parallelizable work: fetch, extract main-body text, list links, format.

No judgment, no scoring, no synthesis — that is deliberately out of scope. If the
user wants a thorough, cited, fact-checked report, use **deep-research** instead;
this skill just returns the text.

Parallelism comes from **process-level fan-out** in `research_targets.py` (shared,
verbatim, with deep-research) — it fetches and extracts many URLs at once. Where a
real browser is available, `--browser` routes each fetch through browser-use.

## Secrets this skill needs

- **None by default.** `required_secrets` is an empty list. The core path —
  fetch, extract, and follow-links — is HTTP-only (`httpx` + `trafilatura` + the
  standard library) and needs no external API key at all. That is what makes it
  safe to run anywhere, including a bare managed sandbox, with zero vault setup.
- The optional **`--browser`** path is the only exception: browser-use is itself
  an agent, so it needs a browser binary (Chromium) **and** an LLM key from the
  environment (`STIMULIR_API_KEY` in a managed run, or your own provider key
  standalone). That key is supplied by the environment, never by this skill —
  which is why it is *not* in `required_secrets`.

## A note on social pages — read before promising anything

Be honest with the user about what "social scraping" can and cannot do here:

- **Works on the HTTP path:** public, server-rendered pages — a public blog post,
  a docs page, many news articles, and social pages that ship real HTML to a
  logged-out visitor. If `curl` would see the text, so will this skill.
- **Does *not* work on the HTTP path:** most modern, logged-in, or JS-heavy social
  feeds (timelines, infinite-scroll profiles, DMs, anything behind a login wall).
  These render client-side and often require authentication. The `--browser` path
  can render the JS, but this skill does **not** handle login, cookies, or
  anti-bot challenges — so gated content is out of reach. Say so plainly rather
  than implying a private feed will scrape.

## Preflight

```bash
python3 -c "import httpx, trafilatura" 2>/dev/null && echo "deps ok" || echo "run: pip install httpx trafilatura"
echo "no API key required for the default path"
```

`trafilatura` + `httpx` are the only runtime deps for the default path. The
`browser` extra (`browser-use` + `playwright`) is optional and only installs
where Chromium exists — do **not** assume it in a bare sandbox.

## Workflow

### 1. Scrape one — a single page

```bash
python3 helpers/fetch_page.py https://example.com --out page.json
```

Returns `{url, title, text, chars, via, ok}`. Read the text and you're done. If a
page comes back thin (JS-heavy), re-run that one with `--browser` (needs the
browser extra + Chromium).

### 2. Scrape many — a list, in parallel

```bash
python3 helpers/research_targets.py --targets https://a.com,https://b.com --concurrency 6 --out pages.json
# or from a JSON file that is a list of URLs, or {results:[{link}]}:
python3 helpers/research_targets.py --targets-file urls.json --concurrency 6 --out pages.json
```

Fetches and extracts every URL concurrently and returns a per-target array
(`ok` / `error` per item — one bad page never sinks the batch). Bounded by
`--concurrency`, so a big list stays polite.

### 3. Follow a page's links — then fan out

```bash
# pull the links off an index/listing page (optionally same-domain only):
python3 helpers/scrape_links.py --url https://blog.example.com --same-domain-only --limit 50 --out links.json
# feed them straight into the parallel scraper — links.json is already the right shape:
python3 helpers/research_targets.py --targets-file links.json --concurrency 6 --out pages.json
```

`scrape_links.py` emits `{results:[{link, text}]}` — the exact shape
`research_targets.py --targets-file` consumes, so no reformatting is needed
between the two steps. Use `--same-domain-only` to stay on one site; drop it to
follow off-site links too. You pick which links matter — the helper just lists
them.

### 4. Emit text/markdown (optional)

The JSON from steps 1–3 already carries the extracted `text` per page. When the
user wants one concatenated document, assemble it yourself from those `text`
fields (e.g. join with `## {title}\n{url}\n\n{text}` separators) — that
formatting is your call, not a helper's, and keeps the skill free of scoring or
synthesis logic.

## Scaling up (optional, when the substrate allows)

- **More URLs, still fast:** raise `--concurrency`. The fan-out is bounded by a
  semaphore, so a large list stays polite.
- **JS-heavy pages:** re-run just those few with `--browser` (needs Chromium +
  an LLM key). Each browser-use process is its own agent, so the fan-out becomes
  N parallel browsers with zero extra wiring — but never assume it is available.

## Anti-patterns

- **Assuming a private social feed will scrape.** Public server-rendered pages
  work on the HTTP path; logged-in / JS-heavy / anti-bot feeds do not, and this
  skill handles no auth. Tell the user that up front instead of overpromising.
- **Assuming `--browser` works.** It needs Chromium *and* an LLM key. Default to
  the HTTP path and only reach for the browser on pages that genuinely need JS
  rendering.
- **Putting any key on a command line or into params.** This skill needs none by
  default; the `--browser` LLM key is read from the environment only, never
  passed as an argument.
- **Doing research here.** No scoring, no citations, no fact-checking — this skill
  returns text. If the user wants an evidence-backed, cited report, that is
  deep-research's job, not this one.
