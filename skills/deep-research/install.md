# Install — deep-research

Two runtime deps for the default path, one external API key. ~3 minutes.

## 0. Prereqs

```bash
# if the environment uses uv:
uv sync
# otherwise, just the two runtime deps:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27" "trafilatura>=1.8"
```

The discovery, fetch, fan-out, and synthesis helpers use only `httpx` +
`trafilatura` (plus the Python standard library) — no browser, so they run in a
bare sandbox.

## 1. Serper key (required)

```bash
export SERPER_API_KEY="..."   # from serper.dev — 2,500 free queries on signup
```

This is the skill's one `required_secret`. In a managed Stimulir run it is
injected from the workspace vault automatically; standalone, export it yourself.
The helpers fail loudly with the exact variable name if it's missing.

## 2. Browser upgrade (optional)

Only where a real browser is available — a Lambda MicroVM image with Chromium
baked in, or a machine with Playwright. **Not installable in a bare AgentCore
code-interpreter sandbox.**

```bash
pip install "browser-use>=0.1" "playwright>=1.40"
python3 -m playwright install chromium
```

`--browser` on `fetch_page.py` / `research_targets.py` then routes each fetch
through browser-use. browser-use is itself an agent, so it also needs an LLM
key — `STIMULIR_API_KEY` in a managed run, or your own provider key standalone.

## 3. Symlink into an agent's skills dir

```bash
ln -s "$PWD" ~/.claude/skills/deep-research     # Claude Code
ln -s "$PWD" ~/.codex/skills/deep-research       # Codex
```

## Notes

- Everything but the Serper call is offline/deterministic. The Serper call is
  the only outbound dependency on the default path.
- No key ever goes on a command line — `SERPER_API_KEY` is read from the
  environment only. That is deliberate: it is what makes the skill safe to run
  as a managed skill where the platform injects the key.
