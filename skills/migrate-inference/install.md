# Install — migrate-inference

No local hardware permissions, no network access, and no auth needed for
the scan step -- `scan_codebase.py` is pure standard library. Auth only
matters once you're ready to actually point the adopter's app at stimulir.
~5 minutes.

## 0. Prereqs

```bash
python3 --version   # 3.10+
```

That's it for the scanner. There is no `pyproject.toml` dependency to
install to run `scan_codebase.py` -- it imports nothing beyond the Python
standard library (`argparse`, `json`, `re`, `pathlib`, `sys`). `uv sync` in
this skill's directory is a no-op beyond confirming the environment (no
third-party runtime deps are declared).

## 1. Skill install

### Local clone + symlink

```bash
git clone <this-skills-repo-url> ~/Developer/skills
```

For Codex:
```bash
ln -s ~/Developer/skills/skills/migrate-inference ~/.codex/skills/migrate-inference
```

For Claude Code:
```bash
ln -s ~/Developer/skills/skills/migrate-inference ~/.claude/skills/migrate-inference
```

### `npx skills add`

```bash
npx skills add <org>/<skills-repo>
```

## 2. Verify the scanner (no key needed)

```bash
cd ~/Developer/skills/skills/migrate-inference
python3 -c "import ast; ast.parse(open('helpers/scan_codebase.py').read()); print('scan_codebase.py parses ok')"

# smoke test against a throwaway fixture
mkdir -p /tmp/mi_smoke && cat > /tmp/mi_smoke/example.py <<'EOF'
from openai import OpenAI
client = OpenAI(api_key="sk-test")
EOF
python3 helpers/scan_codebase.py /tmp/mi_smoke
rm -rf /tmp/mi_smoke
```

You should see one JSON report with `total_hits: 2` or more (an `import`
hit and an `OpenAI(` constructor hit), category `openai-sdk-compatible`.

## 3. Where to get a `STIMULIR_API_KEY` for the migrated app

The scanner itself needs no key. But once the agent has identified call
sites and is ready to actually rewire them (SKILL.md steps 2-5), the
adopter's app needs a real `hyb_*` key to authenticate against stimulir's
gateway:

```bash
export STIMULIR_API_KEY=hyb_...          # goes in the ADOPTER's own env/secrets, not here
export STIMULIR_API_BASE=https://api.stimulir.com   # default, override for self-hosted/staging
export STIMULIR_PROJECT_ID=...           # optional, only if using the native Python SDK's project scoping
```

Generate this key from the Stimulir console (API Keys section, under your
business's settings) -- the same credential plane used by any other
HybrIE/Stimulir-integrated skill in this collection. If you already have a
`hyb_*` key provisioned elsewhere, it works here too; this is not a
separate credential plane.

**This key does not belong in this skill's directory, in this skill's
environment, or anywhere in the stimulir tooling config.** It belongs in
the *adopter's own* application: their `.env` file (untracked,
`.gitignore`d), their secret manager, or their CI/CD platform's encrypted
secrets store — wherever their old `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
already lived. See SKILL.md step 6 for the full rule.

## 4. Installing the Stimulir SDK in the adopter's repo (the default path)

SKILL.md step 2 lands Python call sites on the Stimulir SDK — so for any
Python adopter this install happens as part of the migration. It goes in the
**adopter's** repo, not this skill's:

```bash
# inside the adopter's repo, not this skill's directory
pip install stimulir
# or
uv add stimulir
```

Skip this only when every call site takes the fallback path (non-Python
codebase, or code that must stay OpenAI-SDK-shaped — SKILL.md step 3).

## 5. Notes

- `scan_codebase.py` never needs `STIMULIR_API_KEY` -- it does not make any
  network call, ever. If you see it asking for a key or trying to reach the
  network, that's a bug, not expected behavior.
- This skill does not itself edit the adopter's files, so there's no
  "undo" mechanism to document here -- any edits the agent makes to the
  adopter's repo go through the adopter's own version control (commit
  before migrating, review the diff after).
- Corporate/offline environments can run the scan step fully air-gapped.
  Only the post-migration *runtime* calls (once the adopter's app is
  actually pointed at stimulir) need outbound HTTPS to
  `api.stimulir.com`.
