#!/usr/bin/env python3
"""Move a label to point at a specific prompt version, via the stimulir CLI.

Wraps `stimulir prompts label KEY VERSION LABEL --json`. This is the
promotion/rollback primitive: whatever code resolves `client.prompts.get(key,
label="prod")` at runtime starts serving VERSION the moment this command
succeeds -- there is no separate "deploy" step. That makes this the one
helper in this skill with real, immediate, production-facing side effects.

DEFAULT POSTURE: DRY RUN. Without --confirm, this helper only PRINTS the
exact `stimulir prompts label ...` command it would run and exits 0 -- it
never calls the CLI. Pass --confirm to actually execute it.

This is a mechanical guard only. It does NOT decide whether promoting is a
good idea, does NOT check whether an eval was run, does NOT check whether
--label is "prod" vs "staging" and treat them differently in code. That
judgment belongs to the agent orchestrating this skill (see SKILL.md's
version -> label -> promote workflow) -- this helper stays dumb and applies
the same --confirm gate to every label, every environment, uniformly.
"""
import argparse
import json
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("key", help="prompt key")
    parser.add_argument("version", type=int, help="version number to label")
    parser.add_argument("label", help="label to move, e.g. staging or prod")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually execute the label move. Without this flag, prints the "
        "command that would run and exits without calling the CLI.",
    )
    args = parser.parse_args()

    cmd = ["stimulir", "prompts", "label", args.key, str(args.version), args.label, "--json"]

    if not args.confirm:
        print(json.dumps({
            "dry_run": True,
            "would_run": " ".join(cmd),
            "note": (
                f"This would move label '{args.label}' to point at "
                f"{args.key} v{args.version}, effective immediately for any "
                f"caller resolving that key+label. Re-run with --confirm to "
                f"actually execute it."
            ),
        }, indent=2))
        return

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"label_prompt.py: label move failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"label_prompt.py: could not parse JSON from label: {e}\n"
            f"stdout was: {proc.stdout[:500]}"
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
