# Install — web-scrape

Two runtime deps for the default path, **no API key**. ~2 minutes.

## 0. Prereqs

```bash
# if the environment uses uv:
uv sync
# otherwise, just the two runtime deps:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27" "trafilatura>=1.8"
```

The fetch, parallel fan-out, and link-follow helpers use only `httpx` +
`trafilatura` (plus the Python standard library) — no browser, so they run in a
bare sandbox.

## 1. Secrets — none required

The default path (fetch + extract + follow-links) needs **no external API key**,
which is why the skill's frontmatter declares `required_secrets: []`. Nothing to
export, nothing for a managed run to inject. That is the whole point: it is safe
to run anywhere with zero vault setup.

## 2. Browser upgrade (optional)

Only where a real browser is available — a Lambda MicroVM image with Chromium
baked in, or a machine with Playwright. **Not installable in a bare AgentCore
code-interpreter sandbox.**

```bash
pip install "browser-use>=0.1" "playwright>=1.40"
python3 -m playwright install chromium
```

`--browser` on `fetch_page.py` / `research_targets.py` then routes each fetch
through browser-use for JS-heavy pages. browser-use is itself an agent, so it
also needs an LLM key — `STIMULIR_API_KEY` in a managed run, or your own provider
key standalone. It still does **not** handle login/auth, so gated social feeds
remain out of reach.

## 3. Symlink into an agent's skills dir

```bash
ln -s "$PWD" ~/.claude/skills/web-scrape     # Claude Code
ln -s "$PWD" ~/.codex/skills/web-scrape       # Codex
```

## Notes

- The default path is fully offline/deterministic apart from the outbound
  fetches to the pages you scrape — no discovery API, no model, no key.
- No key ever goes on a command line. The only key involved anywhere is the
  optional `--browser` LLM key, read from the environment only.
