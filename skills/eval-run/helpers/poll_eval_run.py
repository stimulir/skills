#!/usr/bin/env python3
"""Poll a lab eval run to completion and report a pass/fail/score summary.

Thin wrapper around `stimulir lab eval get-run` -- shells out rather than
reimplementing REST auth, per this repo's convention. This helper is
read-only: it never creates, mutates, or executes anything. Given a run ID
(returned by create_eval_run.py), it repeatedly calls
`stimulir lab eval get-run --run-id <id> --json` until the run reaches a
terminal status, then prints a structured summary.

Because this is read-only polling of a run the AGENT already explicitly
created (via create_eval_run.py, optionally with --execute), it is safe to
run unattended -- there is no irreversible or costly action taken here, only
repeated GETs against a durable run resource.

This helper does NOT decide what "pass" means, whether the run's score is
good enough to promote, or what to do next -- it only reports what the
run's own status/score fields already say. That judgment belongs to the
agent reading the summary this prints.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time

TERMINAL_STATUSES = {"completed", "succeeded", "failed", "errored", "cancelled", "canceled"}


def fetch_run(stimulir_bin: str, run_id: str) -> dict:
    cmd = [stimulir_bin, "lab", "eval", "get-run", "--run-id", run_id, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:] if proc.stderr else "")
        raise SystemExit(
            f"poll_eval_run.py: 'stimulir lab eval get-run --run-id {run_id}' failed "
            f"(exit {proc.returncode}). Check the run ID exists and STIMULIR_TOKEN / "
            f"workspace selection are valid."
        )
    stdout = proc.stdout.strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"poll_eval_run.py: expected JSON from 'stimulir lab eval get-run --json' "
            f"but got non-JSON output: {stdout[:500]!r}"
        )


def summarize(run: dict) -> dict:
    """Pull a flat pass/fail/score summary out of whatever shape the CLI
    returns, without assuming field names beyond the obvious status/score
    ones -- the raw run payload is always included alongside the summary so
    nothing is silently dropped if the CLI's schema has more detail.
    """
    status = run.get("status", "unknown")
    results = run.get("results") or run.get("summary") or {}
    if not isinstance(results, dict):
        # "results" more naturally denotes per-row outcomes than aggregate
        # counts in some schemas -- if the CLI returns a list here, there's
        # no aggregate to report, but that's not a failure of this helper.
        results = {}

    return {
        "run_id": run.get("id") or run.get("run_id"),
        "status": status,
        "passed": results.get("passed"),
        "failed": results.get("failed"),
        "total": results.get("total"),
        "score": results.get("score"),
        "raw": run,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="eval run ID to poll")
    parser.add_argument(
        "--interval-seconds", type=float, default=10.0,
        help="seconds between polls (default: 10)",
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=1800.0,
        help="give up and exit non-zero after this many seconds (default: 1800 = 30min)",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    if not shutil.which(args.stimulir_bin):
        raise SystemExit(
            f"poll_eval_run.py: {args.stimulir_bin!r} not found on PATH. This helper "
            "shells out to the stimulir CLI rather than reimplementing REST auth -- "
            "install and authenticate it first (see install.md), or pass "
            "--stimulir-bin with a valid path."
        )

    start = time.monotonic()
    poll_count = 0
    while True:
        run = fetch_run(args.stimulir_bin, args.run_id)
        poll_count += 1
        status = str(run.get("status", "unknown")).lower()

        if status in TERMINAL_STATUSES:
            summary = summarize(run)
            summary["polls"] = poll_count
            summary["elapsed_seconds"] = round(time.monotonic() - start, 1)
            print(json.dumps(summary, indent=2))
            return

        elapsed = time.monotonic() - start
        if elapsed >= args.timeout_seconds:
            raise SystemExit(
                f"poll_eval_run.py: timed out after {elapsed:.0f}s waiting for run "
                f"{args.run_id} to reach a terminal status (last status: {status!r}). "
                f"Run may still be in progress -- re-run this helper with a longer "
                f"--timeout-seconds, or check the run manually."
            )

        sys.stderr.write(
            f"poll_eval_run.py: run {args.run_id} status={status!r} "
            f"(poll {poll_count}, {elapsed:.0f}s elapsed) -- waiting "
            f"{args.interval_seconds}s\n"
        )
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
