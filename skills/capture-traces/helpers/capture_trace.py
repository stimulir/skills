#!/usr/bin/env python3
"""Capture a live inference trace into a Raw-stage data asset.

Thin wrapper around `stimulir data from-trace`. This is the entry point into
the whole capture-traces pipeline: a trace-id from the migrate-inference
stage's gateway (a single logged request/response pair, already flowing
because migrate-inference routed the adopter's inference calls through
Stimulir) becomes a Raw data asset -- stage 1 of Raw -> Cleaning ->
Clean View -> Snapshot -> Lab.

This helper makes NO editorial decision about which traces are worth
capturing, what --source/--target to use, or when to call it. That's the
calling agent's job, informed by SKILL.md. This script does exactly one
thing: shell out to `stimulir data from-trace <trace-id> --source <s>
[--target <t>] --json` and return the parsed JSON asset record on stdout.

Verified against the live `stimulir` CLI (v0.1.0): `TRACE_ID` must be a
UUID, `--source` accepts exactly `agent` or `usage` (not free text), and
`--target` is OPTIONAL (filters/labels intended use downstream -- e.g.
eval/sft/preference -- but from-trace does not require it up front).

Auth/session are handled entirely by the `stimulir` CLI's own cache
(~/.stimulir/) -- this helper does not touch credentials, does not call
the REST API directly, and assumes `connect` has already run (CLI
installed, authenticated, workspace selected).

PRIVACY NOTE (see SKILL.md "Sequencing" section): captured traces can
become future training/eval data. If the adopter has a privacy-layer skill,
it must have already run PII scrubbing upstream of the trace being captured
here -- this helper has no scrubbing capability and performs none. Capturing
first and cleaning later means raw PII sits in the data asset pipeline in
the interim; that is the wrong order.
"""
import argparse
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_id", help="trace UUID from migrate-inference's logged traffic (from `stimulir lab eval ...` or the traces panel)")
    parser.add_argument(
        "--source", required=True, choices=["agent", "usage"],
        help="what generated the trace -- agent or usage (matches `stimulir data from-trace --source`)",
    )
    parser.add_argument(
        "--target", default=None,
        help='optional intended use of the resulting asset, e.g. "eval" (matches `stimulir data from-trace --target`)',
    )
    parser.add_argument(
        "--name", "-n", default=None,
        help="optional human-readable name for the resulting asset",
    )
    args = parser.parse_args()

    if not args.trace_id.strip():
        raise SystemExit("capture_trace.py: trace_id must not be empty")

    cmd = [
        "stimulir", "data", "from-trace", args.trace_id,
        "--source", args.source,
        "--json",
    ]
    if args.target:
        cmd += ["--target", args.target]
    if args.name:
        cmd += ["--name", args.name]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(
            "capture_trace.py: `stimulir data from-trace` failed. Confirm the CLI "
            "is installed and authenticated (`stimulir` should already be set up by "
            "the connect step) and that the trace ID exists in this workspace."
        )

    try:
        asset = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"capture_trace.py: `stimulir data from-trace --json` did not return valid "
            f"JSON. Raw output:\n{proc.stdout[-2000:]}"
        )

    print(json.dumps(asset, indent=2))


if __name__ == "__main__":
    main()
