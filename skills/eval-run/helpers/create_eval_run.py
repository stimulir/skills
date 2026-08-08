#!/usr/bin/env python3
"""Start a Lab eval run via the stimulir CLI, with one guard the CLI lacks.

Thin wrapper around `stimulir lab eval create-run`. It shells out rather than
reimplementing REST auth, per this repo's convention: the CLI already owns
login and workspace selection in ~/.stimulir/.

THE GUARD. `create-run` sends `queue: true, execute: false` on every call.
Without `--execute` the run is created QUEUED with no executor spawned, and
nothing anywhere polls for queued runs, so it sits forever while its status
claims otherwise. That is a stranded run, not a dry run. This helper
therefore requires the caller to say which one they meant: pass --execute to
start it, or --leave-queued to acknowledge that it will not start until
`stimulir lab eval execute-run <id>` is called. Neither flag is a default,
because guessing either one produces a silent failure.

WHY NO --json. The console deep link is printed on the CLI's human path only,
by `_print_handoff`. `create-run --json` drops it, so this helper runs the
human path and passes stdout through verbatim: the run id, the status and an
openable link are the deliverable here. A caller that needs a machine-shaped
payload should invoke `stimulir lab eval create-run ... --json` directly and
accept that no link is printed.

WHAT IT DOES NOT DO. It does not decide which data asset or prompt version is
worth evaluating, does not wait for the run, and does not interpret the
result. `--execute` starts real inference and judging across every case times
every candidate. That spend decision belongs to the agent reading SKILL.md.
"""
import argparse
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="eval suite display name")
    parser.add_argument(
        "--data-asset-id", default=None,
        help="reviewed, snapshotted data asset (or trace snapshot) id to evaluate against",
    )
    parser.add_argument(
        "--prompt", action="append", default=[],
        help="prompt ref as KEY, KEY:VERSION or KEY:LABEL. Repeat for several.",
    )
    parser.add_argument("--provider", default=None, help="baseline provider (CLI default: hybrie)")
    parser.add_argument(
        "--model", default=None,
        help="baseline model or endpoint model name (CLI default: hybrie-runtime-default)",
    )
    parser.add_argument(
        "--adapter-id", default=None,
        help="adapter id to add as a hot-swap candidate alongside the baseline",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="queue the run AND spawn its executor. Returns immediately; it does not wait.",
    )
    parser.add_argument(
        "--leave-queued", action="store_true",
        help="create the run without starting it. It will NOT run until "
             "`stimulir lab eval execute-run <id>` is called.",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    if args.execute == args.leave_queued:
        raise SystemExit(
            "create_eval_run.py: pass exactly one of --execute or --leave-queued. "
            "A run created without --execute is QUEUED with no executor and nothing "
            "polls for queued runs, so it never starts on its own. Say which you meant."
        )

    if not args.data_asset_id and not args.prompt:
        raise SystemExit(
            "create_eval_run.py: pass --data-asset-id, --prompt, or both. With neither, "
            "the CLI creates a `manual` run with no cases and no prompt refs, which "
            "measures nothing. If an empty manual run is genuinely what you want, call "
            "the CLI directly."
        )

    if not shutil.which(args.stimulir_bin):
        raise SystemExit(
            f"create_eval_run.py: {args.stimulir_bin!r} not found on PATH. This helper "
            "shells out to the stimulir CLI rather than reimplementing REST auth. "
            "Install and authenticate it first (see install.md), or pass "
            "--stimulir-bin with a valid path."
        )

    cmd = [args.stimulir_bin, "lab", "eval", "create-run", "--name", args.name]
    if args.data_asset_id:
        cmd += ["--data-asset-id", args.data_asset_id]
    for ref in args.prompt:
        # No shape validation here. The CLI accepts KEY, KEY:VERSION and
        # KEY:LABEL, and an earlier version of this helper rejected two of the
        # three by requiring a colon.
        cmd += ["--prompt", ref]
    if args.provider:
        cmd += ["--provider", args.provider]
    if args.model:
        cmd += ["--model", args.model]
    if args.adapter_id:
        cmd += ["--adapter-id", args.adapter_id]
    # Forward BOTH, not just --execute. The CLI now requires exactly one of them
    # for the same reason this helper does, so forwarding only --execute made
    # --leave-queued reach `create-run` with neither flag set, which exits 2.
    cmd.append("--execute" if args.execute else "--leave-queued")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr[-4000:])

    if proc.returncode != 0:
        raise SystemExit(
            f"create_eval_run.py: 'stimulir lab eval create-run' failed "
            f"(exit {proc.returncode}). If the run was created but did NOT start, the "
            f"CLI names the run id above. Start it with `stimulir lab eval execute-run "
            f"<id>` rather than creating a second run."
        )

    if args.leave_queued:
        sys.stderr.write(
            "create_eval_run.py: run is QUEUED and will not start on its own. "
            "Start it with `stimulir lab eval execute-run <run-id>`.\n"
        )


if __name__ == "__main__":
    main()
