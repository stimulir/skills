# Install — privacy-layer

Every capability in this skill needs network access and an API key -- there
is no local-only mode. ~5 minutes. Assumes `connect` has already run (CLI
installed, authenticated, workspace selected); this doc does not
re-cover that.

## 0. Prereqs

```bash
# if the environment uses uv:
uv sync

# otherwise, just install the one runtime dependency:
python3 -m venv .venv && source .venv/bin/activate
pip install "httpx>=0.27"
```

All three helpers (`check_capabilities.py`, `extract_entities.py`,
`deidentify.py`) use only `httpx` and the Python standard library.

## 1. Skill install

### Local clone + symlink

```bash
git clone <this-skills-repo-url> ~/Developer/skills
```

For Codex:
```bash
ln -s ~/Developer/skills/skills/privacy-layer ~/.codex/skills/privacy-layer
```

For Claude Code:
```bash
ln -s ~/Developer/skills/skills/privacy-layer ~/.claude/skills/privacy-layer
```

### `npx skills add`

```bash
npx skills add <org>/<skills-repo>
```

## 2. Network access + API key (required for every helper)

Unlike skills where the network-dependent step is optional, **every helper
in this skill requires both of the following**:

```bash
export STIMULIR_API_URL=https://api.stimulir.com   # default, override for self-hosted/staging
export STIMULIR_API_KEY=hyb_...                     # REQUIRED, no default
```

Outbound HTTPS access to `STIMULIR_API_URL` must be reachable from wherever
this skill runs (corporate proxies / egress allowlists that block arbitrary
outbound hosts will need `api.stimulir.com` added explicitly). There is no
offline/local-model fallback for any helper here -- if the network call
fails, the helper fails loudly rather than skipping the privacy check.

### Where to get a `STIMULIR_API_KEY`

Same credential plane as any other HybrIE/Stimulir-integrated skill (e.g.
`evidence-clip`'s `deid_transcript.py`, `video-edit`'s cloud VLM calls) -- a
`hyb_*` key issued from the Stimulir console under your business's API
keys settings. If you already have a `hyb_*` key provisioned for another
skill in your setup, that key works here too -- this endpoint sits on the
same plane, not a separate one. If you don't have one yet, generate it from
the Stimulir console (API Keys section) and store it in your shell profile
or secrets manager -- do not commit it to any repo.

## 3. Verify

```bash
cd ~/Developer/skills/skills/privacy-layer
python3 -c "import httpx; print('httpx ok')"
echo "${STIMULIR_API_KEY:+STIMULIR_API_KEY is set}"

# 1. capabilities -- confirms auth + connectivity, no text needed
python3 helpers/check_capabilities.py

# 2. extract -- read-only entity scan
python3 helpers/extract_entities.py --text "test contact test@example.com, call 555-123-4567"

# 3. deidentify -- produces the redacted artifact
python3 helpers/deidentify.py --text "test contact test@example.com, call 555-123-4567"
```

If any of these fail with "STIMULIR_API_KEY is not set", go back to
step 2 -- there is no local fallback for any call in this skill. If they
fail with a non-200 HTTP status, check that `STIMULIR_API_URL` points at
the right environment (production vs. self-hosted/staging) and that the
key hasn't been revoked or scoped to a different workspace.

## 4. Notes

- All three helpers print exactly one JSON object to stdout on success and
  diagnostic text to stderr only -- safe to pipe into `jq` or capture
  directly as a subprocess result.
- `extract_entities.py` and `check_capabilities.py` print the server's
  response verbatim -- their exact field names are not hardcoded anywhere
  in this skill (only `deidentify.py`'s `text`/`redactions`/`entity_types`
  shape is confirmed against source), so treat what a live call actually
  returns as authoritative.
- None of the helpers ever log or print the raw pre-redaction input text --
  only the server's responses are printed. Don't add wrapper logging on
  top of these helpers that reintroduces that leak.
