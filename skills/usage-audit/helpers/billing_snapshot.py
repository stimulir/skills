#!/usr/bin/env python3
"""Wrap `stimulir billing snapshot` to get the current billing-account state.

A billing snapshot is account-level (current balance, plan, spend-to-date,
any active limits/alerts) -- it is a DIFFERENT thing from a usage summary
(`usage_summary.py`, cost broken down by model/task/agent over a window)
and from raw usage events (`usage_events.py`, the per-call ledger). Don't
conflate the three: this helper answers "where does the account stand right
now", not "what did task X cost" or "what happened in the last 30 days".

Thin wrapper only -- shells out to the `stimulir` CLI (which already owns
auth via ~/.stimulir/) and re-emits its JSON output verbatim.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def run_billing_snapshot() -> dict:
    """Run `stimulir billing snapshot --json` and return the parsed payload.

    Raises SystemExit with a clear message if the `stimulir` binary is
    missing, the call fails, or its stdout isn't valid JSON.
    """
    if shutil.which("stimulir") is None:
        raise SystemExit(
            "billing_snapshot.py: 'stimulir' CLI not found on PATH. This helper "
            "shells out to it rather than reimplementing REST auth -- install "
            "and authenticate the CLI first (see install.md)."
        )

    argv = ["stimulir", "billing", "snapshot", "--json"]

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"billing_snapshot.py: 'stimulir billing snapshot' timed out: {e}") from e

    if proc.returncode != 0:
        raise SystemExit(
            f"billing_snapshot.py: 'stimulir billing snapshot' exited {proc.returncode}.\n"
            f"stderr: {proc.stderr.strip()}"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"billing_snapshot.py: 'stimulir billing snapshot --json' did not return "
            f"valid JSON: {e}\nstdout: {proc.stdout[:500]}"
        ) from e


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=None,
        help="write the JSON payload here instead of stdout",
    )
    args = parser.parse_args()

    payload = run_billing_snapshot()

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
