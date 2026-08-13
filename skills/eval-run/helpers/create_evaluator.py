#!/usr/bin/env python3
"""Mint a reusable evaluator whose invariants gate candidates before spend.

Thin wrapper around `stimulir lab eval evaluator-create`. It shells out rather
than reimplementing REST auth, per this repo's convention: the CLI already owns
login and workspace selection in ~/.stimulir/. The evaluator this creates is
attached to a run with `create-run --evaluator-id <id>` (see create_eval_run.py
--evaluator-id).

THE GUARD, and it is the CLI's own guard restated one call earlier. An
evaluator with no invariant gates no candidate, and `evaluator-create` exits 2
with a BadParameter when none is given. This helper refuses the same
combination up front, with the same reason, so the caller learns it before the
subprocess runs. The condition mirrors the CLI exactly: at least one of
--forbidden-phrase, --required-phrase or --max-prompt-chars. --invariant-key
alone does NOT satisfy it; it only names the identifier recorded on rejections
this invariant produces, and it defaults server-side, so passing it without a
phrase or a length cap still gates nothing.

WHY NO --json. `evaluator-create` prints the evaluator id AND the
`create-run --evaluator-id <id>` handoff line on its human path only, the same
asymmetry that made create_eval_run.py avoid --json. This helper runs the human
path and passes stdout through verbatim so both reach the caller. A caller that
needs a machine-shaped payload should invoke
`stimulir lab eval evaluator-create ... --json` directly.

WHAT IT DOES NOT DO. It does not attach the evaluator to a run, does not start
a run, and does not decide which phrase or length is worth enforcing. Attaching
is create_eval_run.py's --evaluator-id. The invariant is a guarantee the caller
chose; this helper only records it.
"""
import argparse
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="evaluator display name")
    parser.add_argument(
        "--forbidden-phrase", action="append", default=[],
        help="a candidate whose prompt CONTAINS this exact text is skipped before "
             "any judge spend and recorded as a rejection. Repeat for several.",
    )
    parser.add_argument(
        "--required-phrase", action="append", default=[],
        help="a candidate whose prompt is MISSING this text is skipped. Repeat for several.",
    )
    parser.add_argument(
        "--max-prompt-chars", type=int, default=None,
        help="skip a candidate whose prompt exceeds this length in characters.",
    )
    parser.add_argument(
        "--invariant-key", default=None,
        help="identifier recorded on rejections this invariant produces (CLI default: "
             "cli-invariant). NOT an invariant by itself; a phrase or length cap is still required.",
    )
    parser.add_argument(
        "--description", default=None, help="human note stored with the evaluator.",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    if not args.forbidden_phrase and not args.required_phrase and args.max_prompt_chars is None:
        raise SystemExit(
            "create_evaluator.py: pass at least one invariant: --forbidden-phrase, "
            "--required-phrase or --max-prompt-chars. An evaluator with none gates no "
            "candidate, and this verb exists to create gating ones. --invariant-key alone "
            "does not count; it only labels the rejections a real invariant produces."
        )

    if not shutil.which(args.stimulir_bin):
        raise SystemExit(
            f"create_evaluator.py: {args.stimulir_bin!r} not found on PATH. This helper "
            "shells out to the stimulir CLI rather than reimplementing REST auth. "
            "Install and authenticate it first (see install.md), or pass "
            "--stimulir-bin with a valid path."
        )

    cmd = [args.stimulir_bin, "lab", "eval", "evaluator-create", "--name", args.name]
    for phrase in args.forbidden_phrase:
        cmd += ["--forbidden-phrase", phrase]
    for phrase in args.required_phrase:
        cmd += ["--required-phrase", phrase]
    if args.max_prompt_chars is not None:
        cmd += ["--max-prompt-chars", str(args.max_prompt_chars)]
    if args.invariant_key:
        cmd += ["--invariant-key", args.invariant_key]
    if args.description:
        cmd += ["--description", args.description]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr[-4000:])

    if proc.returncode != 0:
        raise SystemExit(
            f"create_evaluator.py: 'stimulir lab eval evaluator-create' failed "
            f"(exit {proc.returncode}). The evaluator id, when one was created, is named "
            f"above; attach it with `stimulir lab eval create-run --evaluator-id <id>`."
        )


if __name__ == "__main__":
    main()
