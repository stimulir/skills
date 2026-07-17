---
name: deep-research
description: Exhaustive web research on a topic, market, or set of targets — discover sources with Serper, fetch and extract many in parallel, then synthesize a cited report and CSV. Use when the user wants a thorough, multi-source, evidence-backed answer: competitor/opposition research, a list of companies matching an ICP, market landscape, prospect enrichment, or "find everything about X." Agent-driven: you do the judgment (which sources, how to score, what to conclude); the helpers do the deterministic heavy lifting.
required_secrets:
  - SERPER_API_KEY
---

# Deep Research

Thorough web research done the way it actually works: **discover → fan out →
synthesize**. You (the agent) make every judgment call — which results are
worth chasing, how to score fit, what the evidence supports. The helpers only
do the deterministic, parallelizable work: search, fetch, extract, format.

Exhaustiveness comes from **process-level fan-out** in `research_targets.py`,
not from any special agent tooling — it fetches and extracts many targets at
once. Where a real browser is available, `--browser` routes each fetch through
browser-use, and each browser-use process is itself a research sub-agent.

## Secrets this skill needs

- **`SERPER_API_KEY`** — required, for the discovery search (serper.dev; 2,500
  free queries). In a managed run it is injected from the workspace vault; the
  frontmatter `required_secrets` above is what tells the platform to prompt for
  it. Standalone, export it yourself.
- The LLM key is **not** listed here — synthesis is your reasoning, and the
  optional `--browser` path uses whatever model key the environment already
  provides (`STIMULIR_API_KEY` in a managed run). Only genuinely external,
  skill-specific keys go in `required_secrets`.

## Preflight

```bash
python3 -c "import httpx, trafilatura" 2>/dev/null && echo "deps ok" || echo "run: pip install httpx trafilatura"
test -n "$SERPER_API_KEY" && echo "serper key present" || echo "SERPER_API_KEY missing"
```

`trafilatura` + `httpx` are the only runtime deps for the default path. The
`browser` extra (`browser-use` + `playwright`) is optional and only installs
where Chromium exists — do **not** assume it in a bare sandbox.

## Workflow

### 1. Discover — over-collect, then you filter

```bash
python3 helpers/search_serper.py "series B fintech london 2025" --num 20 --out hits.json
```

Ask broadly and request more than you need. Read `hits.json` and decide which
links are worth researching — that judgment is yours, not the helper's. Run
several queries from different angles for real coverage (by product, by
segment, by "competitors of X", by news).

### 2. Fan out — research many targets in parallel

```bash
python3 helpers/research_targets.py --targets-file hits.json --concurrency 6 \
    --question "Is this a fit for our ICP?" --out findings.json
```

This fetches and extracts every target concurrently and returns a per-target
result array (`ok` / `error` per item — one bad page never sinks the batch).
Feed it a Serper result file directly, or `--targets a.com,b.com`. For
JS-heavy pages where the http extraction comes back thin, re-run those few
with `--browser` (needs the browser extra + Chromium).

### 3. Judge — this is the part only you can do

Read `findings.json`. For each target, decide: is it relevant, what does the
evidence actually say, how well does it fit the criteria the user gave? Write
your conclusions into a scored findings array — `name`, `url`, `score` (1–10),
`summary`, and `evidence` as `{quote, source}` pairs so every claim is
traceable. Keep quotes verbatim from the extracted text; never invent a source.

### 4. Synthesize — compile the report + CSV

```bash
python3 helpers/synthesize.py --findings scored.json --title "Series B fintech" \
    --out-md report.md --out-csv results.csv
```

Deterministic: it ranks by your score and emits a cited Markdown report plus a
CSV, judgment intact. It never calls a model.

## Scaling up (optional, when the substrate allows)

- **More targets, still fast:** raise `--concurrency`. The fan-out is bounded
  by a semaphore, so a big list stays polite.
- **A spawner tool, if the runtime offers one:** in a code-runtime session that
  exposes a `spawn_subagents` tool, you may fan the *judgment* step out too —
  one sub-agent per cluster of targets, each returning a scored sub-report you
  merge. This is an enhancement, never a requirement: `research_targets.py`'s
  own concurrency already gives exhaustive coverage without it.

## Anti-patterns

- **Putting `SERPER_API_KEY` (or any key) on a command line or into params.**
  It belongs in the environment only — that's why it's a `required_secret`.
- **Fabricating a citation.** Every `evidence` quote must be lifted verbatim
  from an extracted `text`, with its real `source` URL.
- **Assuming `--browser` works.** It needs Chromium; default to the http path
  and only reach for the browser on pages that genuinely need JS rendering.
- **One narrow query.** Exhaustive means several angles — discover more than
  once before you conclude "that's everything."
