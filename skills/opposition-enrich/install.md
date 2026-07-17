# Install — opposition-enrich

Two runtime deps, one external API key. ~3 minutes. (Same footprint as
`deep-research` — they share the research engine.)

## 0. Prereqs

```bash
# if the environment uses uv:
uv sync
# otherwise:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27" "trafilatura>=1.8"
```

The discovery, fetch, fan-out, and brief helpers use only `httpx` +
`trafilatura` plus the standard library — no browser, so they run in a bare
sandbox.

## 1. Serper key (required)

```bash
export SERPER_API_KEY="..."   # from serper.dev — 2,500 free queries on signup
```

The skill's one `required_secret`. Injected from the workspace vault in a
managed Stimulir run; export it yourself standalone. Helpers fail loudly with
the exact variable name if it's missing.

## 2. Browser upgrade (optional)

Only where Chromium is available (a Lambda MicroVM image with Chromium baked in,
or a machine with Playwright — **not** a bare AgentCore sandbox):

```bash
pip install "browser-use>=0.1" "playwright>=1.40"
python3 -m playwright install chromium
```

`--browser` on `fetch_page.py` / `research_targets.py` then renders JS-heavy
pricing/product pages. browser-use also needs an LLM key (`STIMULIR_API_KEY` in
a managed run).

## 3. Symlink into an agent's skills dir

```bash
ln -s "$PWD" ~/.claude/skills/opposition-enrich    # Claude Code
ln -s "$PWD" ~/.codex/skills/opposition-enrich      # Codex
```

## Notes

- No key ever goes on a command line — `SERPER_API_KEY` is read from the
  environment only. That is what makes the skill safe to run as a managed skill
  where the platform injects the key.
