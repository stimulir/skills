---
name: opposition-enrich
description: Competitor / opposition intelligence — given a rival, target, or opponent (by name or URL), find their web properties, research them in parallel, extract structured attributes (positioning, pricing, funding, headcount, key people, recent moves, strengths/weaknesses), and compile a sourced competitive brief. Use when the user wants to profile a competitor, enrich a target account, build a battlecard, or size up an opponent. Agent-driven: you extract and judge the attributes from the evidence; the helpers do discovery, parallel fetch, and brief formatting.
required_secrets:
  - SERPER_API_KEY
---

# Opposition Enrich

Profile a competitor or opponent from the open web, structured and sourced.
Same engine as `deep-research` (Serper discovery + parallel fetch/extract), but
pointed at one entity and producing a **structured brief** instead of a ranked
list. You do the extraction and judgment; the helpers discover, fetch in
parallel, and format.

## Secrets this skill needs

- **`SERPER_API_KEY`** — required, for discovering the opponent's properties and
  recent news (serper.dev). Injected from the workspace vault in a managed run
  (that's what the `required_secrets` frontmatter above declares); export it
  yourself standalone.
- No LLM key is listed — the attribute extraction and judgment are your
  reasoning, and the optional `--browser` path uses the environment's existing
  model key (`STIMULIR_API_KEY` in a managed run).

## Preflight

```bash
python3 -c "import httpx, trafilatura" 2>/dev/null && echo "deps ok" || echo "run: pip install httpx trafilatura"
test -n "$SERPER_API_KEY" && echo "serper key present" || echo "SERPER_API_KEY missing"
```

## Workflow

### 1. Find the opponent's web properties

```bash
python3 helpers/search_serper.py "Acme Corp official site" --num 10 --out site.json
python3 helpers/search_serper.py "Acme Corp funding OR headcount OR pricing" --type news --num 15 --out news.json
```

Search a few angles: the official site, pricing/product pages, funding/news,
leadership. Read the results and pick the URLs that actually belong to the
opponent — that judgment is yours.

### 2. Research the properties in parallel

```bash
python3 helpers/research_targets.py --targets-file site.json --concurrency 6 \
    --question "positioning, pricing, segment, funding, people, recent moves" \
    --out pages.json
```

This fetches and extracts every chosen page at once (`ok`/`error` per page).
For JS-heavy product/pricing pages that come back thin, re-run those few with
`--browser` (needs the browser extra + Chromium).

### 3. Extract the structured profile — your judgment

Read `pages.json`. Build a profile object filling only the attributes the
evidence actually supports — never guess a number. Each attribute is a short
factual statement; each material claim gets an `evidence` entry with a verbatim
quote's source:

```json
{
  "name": "Acme Corp",
  "url": "https://acme.com",
  "attributes": {
    "positioning": "...", "target_segment": "...", "pricing": "...",
    "funding": "...", "headcount": "...", "key_people": "...",
    "recent_moves": "...", "strengths": "...", "weaknesses": "..."
  },
  "evidence": [ {"claim": "raised $40M Series B", "source": "https://acme.com/news"} ]
}
```

Leave an attribute out entirely if the evidence doesn't support it. An honest
gap beats a fabricated fact.

### 4. Compile the brief

```bash
python3 helpers/brief.py --profile acme.json --title "Acme Corp" --out-md brief.md
```

For a landscape, pass a JSON **list** of profiles — the brief renders them in
sequence for a side-by-side read.

## Anti-patterns

- **Guessing an attribute.** Funding, headcount, pricing — only what a source
  states. Omit rather than invent.
- **Any key on a command line or in params.** `SERPER_API_KEY` lives in the
  environment; that's why it's a `required_secret`.
- **Trusting a same-name company.** Confirm each URL actually belongs to the
  opponent before you research it — many names collide.
- **A single search.** Positioning, pricing, funding, and people rarely live on
  one page; search several angles before you conclude.
