#!/usr/bin/env python3
"""Move a data asset forward exactly one stage in the pipeline.

Thin wrapper around `stimulir data stage <asset-id> <stage>`. The pipeline
is fixed and linear:

    Raw -> Cleaning -> Clean View -> Snapshot -> Lab

This helper's own CLI takes `--to <stage>` (matching this skill's public
interface); it passes that through to the underlying `stimulir` CLI as a
positional STAGE argument -- verified against the live CLI's own --help
(`stimulir data stage ASSET_ID STAGE`, stage one of raw, cleaning,
clean_view, snapshot, lab -- no `--to` flag exists on the real CLI).

This helper enforces "one stage at a time" as a hard rule, not a suggestion:
it checks the asset's CURRENT stage (via `stimulir data list --json`,
matched against the given asset id) and refuses to run if `--to` is not the
immediate next stage in the sequence above. It will not skip Raw straight to
Clean View, and it will not move an asset backwards. This is a mechanical
adjacency check only -- it has no opinion on whether the DATA itself is
actually clean/ready; that judgment belongs to the agent (or a human) before
it calls this helper.

Snapshot is a special case: promoting TO Snapshot is expected to be paired
with (or followed by) snapshot_asset.py, which is the helper that actually
creates the immutable version. advance_stage.py only moves the asset's
pipeline-stage marker; it does not itself create a snapshot artifact.
"""
import argparse
import json
import subprocess
import sys

STAGES = ["raw", "cleaning", "clean_view", "snapshot", "lab"]

# Human-readable labels as they appear in stimulir's docs/UI, keyed by the
# lowercase/underscore form used on the CLI and in this helper's checks.
STAGE_LABELS = {
    "raw": "Raw",
    "cleaning": "Cleaning",
    "clean_view": "Clean View",
    "snapshot": "Snapshot",
    "lab": "Lab",
}


def normalize_stage(value):
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def get_current_stage(asset_id):
    # `data list` is paginated (--cursor/--limit, max 200) -- page through all
    # of it rather than checking only the first page, or a valid asset past
    # page 1 would falsely report as "not found".
    cursor = None
    while True:
        cmd = ["stimulir", "data", "list", "--json", "--limit", "200"]
        if cursor:
            cmd += ["--cursor", cursor]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr[-4000:])
            raise SystemExit("advance_stage.py: `stimulir data list --json` failed while looking up current stage.")

        try:
            page = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise SystemExit(
                f"advance_stage.py: `stimulir data list --json` did not return valid JSON. "
                f"Raw output:\n{proc.stdout[-2000:]}"
            )

        # Verified shape (stimulir CLI v0.1.0): {"assets": [...], "next_cursor": ...}.
        # Also accept a bare list defensively, in case a future CLI version
        # returns an unwrapped array.
        if isinstance(page, dict):
            assets = page.get("assets") or page.get("data") or []
            next_cursor = page.get("next_cursor")
        else:
            assets = page
            next_cursor = None

        for asset in assets:
            asset_identifier = asset.get("id") or asset.get("asset_id")
            if str(asset_identifier) == str(asset_id):
                stage = asset.get("stage")
                if not stage:
                    raise SystemExit(f"advance_stage.py: asset {asset_id} has no 'stage' field in `stimulir data list --json` output.")
                return normalize_stage(stage)

        if not next_cursor:
            break
        cursor = next_cursor

    raise SystemExit(
        f"advance_stage.py: asset id {asset_id} not found in `stimulir data list --json` output "
        "after paging through all results."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_id", help="data asset ID to advance")
    parser.add_argument(
        "--to", required=True,
        help="target stage: raw, cleaning, clean_view, snapshot, or lab (must be the immediate next stage)",
    )
    parser.add_argument(
        "--skip-adjacency-check", action="store_true",
        help="DANGEROUS escape hatch -- bypasses the one-stage-at-a-time rule. "
             "Only use this if you have an explicit, verified reason (e.g. correcting a "
             "stage that was set out of band). Not for normal pipeline progression.",
    )
    args = parser.parse_args()

    to_stage = normalize_stage(args.to)
    if to_stage not in STAGES:
        raise SystemExit(
            f"advance_stage.py: --to must be one of {', '.join(STAGES)} (got {args.to!r})"
        )

    if not args.skip_adjacency_check:
        current_stage = get_current_stage(args.asset_id)
        current_idx = STAGES.index(current_stage)
        target_idx = STAGES.index(to_stage)

        if target_idx != current_idx + 1:
            direction = "backwards" if target_idx <= current_idx else "by skipping intermediate stage(s)"
            raise SystemExit(
                f"advance_stage.py: refusing to move asset {args.asset_id} from "
                f"'{STAGE_LABELS[current_stage]}' to '{STAGE_LABELS[to_stage]}' -- that "
                f"jumps {direction}. The pipeline only advances one stage at a time: "
                f"{' -> '.join(STAGE_LABELS[s] for s in STAGES)}. "
                f"Call this again with --to {STAGES[current_idx + 1] if current_idx + 1 < len(STAGES) else '<n/a, already at Lab>'} "
                f"first, or pass --skip-adjacency-check if you have a verified reason to override this."
            )

    cmd = ["stimulir", "data", "stage", args.asset_id, to_stage, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit("advance_stage.py: `stimulir data stage` failed. Confirm the asset id and target stage are valid.")

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"advance_stage.py: `stimulir data stage --json` did not return valid JSON. "
            f"Raw output:\n{proc.stdout[-2000:]}"
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
