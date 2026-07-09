#!/usr/bin/env python3
"""Create an immutable snapshot (version) of a data asset.

Thin wrapper around `stimulir data snapshot <asset-id>`. A snapshot is the
irreversible step in the pipeline: once created, that version of the asset
is frozen and citable (e.g. as the exact data a Lab experiment or eval run
was built on). It cannot be un-created or edited in place -- a mistake here
is fixed by creating a NEW, correct snapshot, not by mutating the old one.

Verified against the live `stimulir` CLI (v0.1.0): `stimulir data snapshot`
takes only `ASSET_ID` and `--json` -- there is no `--label`/`--name`/
`--description` flag on the real command. This helper accepts an optional
`--label` purely as a LOCAL note echoed back in this helper's own dry-run
and result output (e.g. for the agent's own bookkeeping in a provenance
trail); it is never passed to the underlying `stimulir` CLI call.

Because this action is irreversible, this helper defaults to DRY-RUN. It
prints exactly what it WOULD do (asset id, resulting CLI call) and exits
without calling `stimulir data snapshot` unless the caller passes --confirm.
This mirrors the repo-wide rule: any helper whose action is irreversible or
costs money must default to dry-run and require an explicit confirm flag --
see SKILL.md's Anti-patterns section.

This helper does not decide WHEN a snapshot is warranted (e.g. "before a Lab
run" or "after Clean View sign-off") -- that judgment belongs to the agent
reading SKILL.md, informed by the pipeline stage the asset is currently in.
"""
import argparse
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_id", help="data asset ID to snapshot")
    parser.add_argument(
        "--label", default=None,
        help="optional local note for this snapshot (e.g. purpose, run name). "
             "NOT sent to the stimulir CLI -- it has no --label flag -- this is "
             "echoed back in this helper's own output only, for the agent's "
             "own bookkeeping (e.g. a provenance record).",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="REQUIRED to actually create the snapshot. Without this flag, the helper "
             "only prints what it would do and exits 0 without calling the CLI. "
             "Snapshots are immutable -- there is no undo.",
    )
    args = parser.parse_args()

    cmd = ["stimulir", "data", "snapshot", args.asset_id, "--json"]

    if not args.confirm:
        print(json.dumps({
            "dry_run": True,
            "would_run": " ".join(cmd),
            "asset_id": args.asset_id,
            "label": args.label,
            "note": (
                "Snapshot creation is irreversible. Re-run with --confirm to actually "
                "create it. Nothing was created."
            ),
        }, indent=2))
        return

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit("snapshot_asset.py: `stimulir data snapshot` failed. Confirm the asset id is valid and reachable.")

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"snapshot_asset.py: `stimulir data snapshot --json` did not return valid JSON. "
            f"Raw output:\n{proc.stdout[-2000:]}"
        )

    if args.label:
        # Local-only annotation -- the stimulir CLI has no --label field, so this
        # is never sent upstream. Kept in this helper's own output only so a
        # caller piping this into provenance.py-style tracking has it available.
        result["_local_label"] = args.label

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
