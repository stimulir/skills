#!/usr/bin/env python3
"""Create a lab eval run via the stimulir CLI.

Thin wrapper around `stimulir lab eval create-run` -- shells out rather than
reimplementing REST auth, per this repo's convention: the stimulir CLI
already handles login/session caching in ~/.stimulir/, so every skill that
just needs to DO a CLI-shaped action shells out to it instead of re-deriving
Authorization / X-Business-Profile-Id headers itself.

This helper is DUMB on purpose. It does not decide which data asset or
prompt version to evaluate against, does not decide whether to pass
--execute, and does not interpret the result -- it builds one CLI invocation
from explicit flags, runs it, and returns the CLI's own --json output
(or a structured error) on stdout. All judgment (is the data asset a real
reviewed snapshot? is this prompt version ready to compare? should the run
execute immediately or stay queued?) belongs to the agent reading SKILL.md,
not to this script.

--execute is opt-in and named explicitly to make its cost/effect visible in
any command line or log that invoked this helper -- creating a run can be
free/cheap (queued for later) but --execute kicks off real evaluation work
against the data asset immediately.
"""
import argparse
import json
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="human-readable name for the eval run")
    parser.add_argument(
        "--data-asset-id", required=True,
        help="ID of the curated data asset (snapshot) to evaluate against",
    )
    parser.add_argument(
        "--prompt", required=True,
        help="prompt reference as <key>:<version>, e.g. summarize-ticket:4",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="start execution immediately after creating the run (real eval "
             "work against the data asset -- omit to leave the run queued)",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    if ":" not in args.prompt:
        raise SystemExit(
            f"create_eval_run.py: --prompt must be in <key>:<version> form, got {args.prompt!r}"
        )

    if not shutil.which(args.stimulir_bin):
        raise SystemExit(
            f"create_eval_run.py: {args.stimulir_bin!r} not found on PATH. This helper "
            "shells out to the stimulir CLI rather than reimplementing REST auth -- "
            "install and authenticate it first (see install.md), or pass "
            "--stimulir-bin with a valid path."
        )

    cmd = [
        args.stimulir_bin, "lab", "eval", "create-run",
        "--name", args.name,
        "--data-asset-id", args.data_asset_id,
        "--prompt", args.prompt,
        "--json",
    ]
    if args.execute:
        cmd.append("--execute")

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:] if proc.stderr else "")
        raise SystemExit(
            f"create_eval_run.py: 'stimulir lab eval create-run' failed "
            f"(exit {proc.returncode}). Check --data-asset-id and --prompt exist "
            f"and STIMULIR_TOKEN / workspace selection are valid."
        )

    stdout = proc.stdout.strip()
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"create_eval_run.py: expected JSON from 'stimulir lab eval create-run "
            f"--json' but got non-JSON output: {stdout[:500]!r}"
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
