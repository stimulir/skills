# prompt-versioning

Manages prompts as versioned, labeled assets in the Stimulir workspace instead of hardcoded strings scattered through the adopter's codebase -- every edit becomes a new immutable version, every environment (dev/staging/prod) points at a version through a movable label, and promotion is one explicit, `--confirm`-gated CLI call rather than a code deploy; the recommended workflow always labels a new version to a non-prod environment first, evaluates it (hand off to the `eval-run` skill), and only then promotes the same version to `prod`.

## Quick start

```bash
# 0. preflight -- confirms the stimulir CLI is installed, authenticated, and
#    pointed at a workspace (connect must have already run)
stimulir prompts list --json

# 1. create a new version of a prompt (labeled to a non-prod env, not prod)
python helpers/create_prompt_version.py create \
  --key my_prompt --content "Summarize: {{text}}" --label dev

# 2. promote that version to staging -- dry-run by default
python helpers/label_prompt.py my_prompt 2 staging
python helpers/label_prompt.py my_prompt 2 staging --confirm

# 3. hand off to the eval-run skill against key=my_prompt, label=staging

# 4. only after eval passes, promote the SAME version to prod
python helpers/label_prompt.py my_prompt 2 prod --confirm

# resolve/inspect at any point
python helpers/get_prompt.py my_prompt --label prod
```

See [`SKILL.md`](./SKILL.md) for the full version -> label -> promote
workflow, the CLI reference, and the anti-patterns (most importantly: never
label a fresh version straight to `prod` without a non-prod label + eval
pass first). See [`install.md`](./install.md) for setup.
