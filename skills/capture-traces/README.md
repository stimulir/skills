# capture-traces

Turn live inference traffic already flowing through Stimulir (from the
`migrate-inference` stage) into curated, versioned data assets -- Raw →
Cleaning → Clean View → Snapshot → Lab, one stage at a time -- for Codex /
Claude Code. This is the literal mechanism behind "gets sharper as it
runs": without it, an integration is just a pass-through gateway with none
of the self-improvement value. Should run AFTER a privacy-layer skill has
scrubbed PII from the same traffic, not before -- captured traces can
become future training data, so PII gets scrubbed at the source, not
retroactively across pipeline stages.

## Quick start

```bash
# 1. capture a trace into a Raw-stage data asset
python helpers/capture_trace.py <trace-id> --source agent --target eval

# 2. advance it one stage at a time (never skips a stage)
python helpers/advance_stage.py <asset-id> --to cleaning
python helpers/advance_stage.py <asset-id> --to clean_view

# 3. snapshot before anything reproducible depends on it (dry-run by default --
#    review the plan it prints, then re-run with --confirm; snapshots are immutable)
python helpers/snapshot_asset.py <asset-id> --label "eval-baseline"
python helpers/snapshot_asset.py <asset-id> --label "eval-baseline" --confirm

# 4. promote to Lab once a Snapshot exists
python helpers/advance_stage.py <asset-id> --to lab
```

See [`SKILL.md`](./SKILL.md) for the full pipeline playbook (including the
privacy-layer sequencing requirement and why stages can't be skipped) and
[`install.md`](./install.md) for setup and verification.
