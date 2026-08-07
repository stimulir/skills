#!/usr/bin/env python3
"""Record that a steer was consumed, AFTER acting on it.

Thin wrapper around `stimulir lab eval ack-steer`. Write-once and idempotent:
a second ack returns the FIRST consumption instead of erroring, so an agent
that crashed after acting and before recording does not wedge the channel.
There is no un-ack and no delete.

ORDER MATTERS AND ONLY ONE ORDER IS SAFE. Act first, then ack. The tolerated
failure is a crash between acting and recording, which leaves a steer that
looks unconsumed and gets picked up again -- recoverable, and visible. The
other order loses the instruction permanently and silently, because there is
no way to un-ack a steer the agent never actually acted on.

--note is optional on the CLI and REQUIRED here. The note is the entire audit
value of the channel: it is where the child run id produced from a steer gets
written down, and an ack with no note records that someone took the
instruction without recording what came of it.
"""
import argparse
import json

from _common import handoff, require_cli, run_cli

HELPER = "ack_steer.py"

MIN_NOTE_CHARS = 8


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="run id the steer sits on")
    parser.add_argument("steer_id", help="steer id to acknowledge")
    parser.add_argument(
        "--consumed-by", required=True,
        help="who consumed it: an AGENT SESSION id, not a user id",
    )
    parser.add_argument(
        "--note", required=True,
        help="what was DONE, e.g. 'applied as derive on run <child-id>'",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    require_cli(args.stimulir_bin, HELPER)
    note = args.note.strip()
    if len(note) < MIN_NOTE_CHARS:
        raise SystemExit(
            f"{HELPER}: --note is too thin. Record what was actually done with this "
            "steer, including the child run id if it produced one. The ack is "
            "write-once, so this is the only chance to write it."
        )

    result = run_cli(
        [
            args.stimulir_bin, "lab", "eval", "ack-steer", args.run_id, args.steer_id,
            "--consumed-by", args.consumed_by,
            "--note", note,
            "--json",
        ],
        helper=HELPER,
        hint="Check the steer id belongs to that run in this workspace.",
    )
    if not isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
        return

    steer = result.get("steer") if isinstance(result.get("steer"), dict) else {}
    out = {
        "steer_id": steer.get("steer_id") or args.steer_id,
        "already_consumed": bool(result.get("already_consumed")),
        "consumed_by": steer.get("consumed_by"),
        "consumed_at": steer.get("consumed_at"),
        "consumption": steer.get("consumption"),
        "handoff": handoff(args.run_id, None),
        "raw": result,
    }
    if out["already_consumed"]:
        out["note_to_caller"] = (
            "This steer was already consumed by whoever got there first. This ack "
            "changed nothing, and the consumption on record is theirs, not yours."
        )
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
