#!/usr/bin/env python3
"""Wrap `stimulir usage --json` to get an aggregated cost/usage summary.

This is a THIN wrapper, on purpose. It builds the argv for
`stimulir usage --window <window> --group-by <group_by> --json`, runs it,
and re-emits whatever the CLI printed on stdout. It does not aggregate,
re-bucket, or reinterpret numbers itself -- the `stimulir` CLI already
handles auth (via its own ~/.stimulir/ session cache) and the actual
summarization. This helper's only job is a stable, scriptable entry point
plus a clear failure message if the CLI is missing or not authenticated.

A summary is a SNAPSHOT for one window/group-by pair, computed server-side.
It is not a substitute for the raw event ledger -- see usage_events.py for
that -- and this helper does not attempt to reconcile the two itself. That
reconciliation is the agent's job (see SKILL.md).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def run_usage_summary(window: str, group_by: str, extra_args: list[str] | None = None) -> dict:
    """Run `stimulir usage --window <window> --group-by <group_by> --json`
    and return the parsed JSON payload.

    Raises SystemExit with a clear message if the `stimulir` binary is
    missing, the call fails, or its stdout isn't valid JSON.
    """
    if shutil.which("stimulir") is None:
        raise SystemExit(
            "usage_summary.py: 'stimulir' CLI not found on PATH. This helper "
            "shells out to it rather than reimplementing REST auth -- install "
            "and authenticate the CLI first (see install.md)."
        )

    argv = ["stimulir", "usage", "--window", window, "--group-by", group_by, "--json"]
    if extra_args:
        argv.extend(extra_args)

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"usage_summary.py: 'stimulir usage' timed out: {e}") from e

    if proc.returncode != 0:
        raise SystemExit(
            f"usage_summary.py: 'stimulir usage' exited {proc.returncode}.\n"
            f"stderr: {proc.stderr.strip()}"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"usage_summary.py: 'stimulir usage --json' did not return valid JSON: {e}\n"
            f"stdout: {proc.stdout[:500]}"
        ) from e


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window", default="30d",
        help="lookback window, e.g. 24h, 7d, 30d (default: 30d)",
    )
    parser.add_argument(
        "--group-by", default="model",
        help="aggregation dimension, e.g. model, task, agent, day (default: model)",
    )
    parser.add_argument(
        "--out", default=None,
        help="write the JSON payload here instead of stdout",
    )
    args = parser.parse_args()

    payload = run_usage_summary(args.window, args.group_by)

    text = json.dumps(payload, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
