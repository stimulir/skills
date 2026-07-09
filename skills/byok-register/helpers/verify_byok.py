#!/usr/bin/env python3
"""Verify a registered BYOK credential against its upstream provider.

Wraps `stimulir byok verify <credential_id> --json`. Read-only, safe,
idempotent -- no confirmation gate needed (unlike register_byok.py, this
never creates or deletes anything). Reports a normalized pass/fail JSON
object so the calling agent can branch on the outcome without parsing CLI
prose.
"""
import argparse
import json
import shutil
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("credential_id", help="credential id, from `stimulir byok list`")
    args = parser.parse_args()

    if shutil.which("stimulir") is None:
        raise SystemExit(
            "verify_byok.py: `stimulir` CLI not found on PATH. This skill assumes "
            "`connect` has already run (CLI installed + authenticated + workspace "
            "selected) -- see install.md."
        )

    cmd = ["stimulir", "byok", "verify", args.credential_id, "--json"]
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise SystemExit("verify_byok.py: `stimulir byok verify` timed out after 60s.")

    stdout = result.stdout.strip()
    payload = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None

    # The CLI's own exit code is the authoritative pass/fail signal; JSON
    # payload (when parseable) is carried through for detail, but a
    # nonzero exit always means "verified": False regardless of payload
    # shape, since a malformed/partial JSON body should never be read as
    # a pass.
    verified = result.returncode == 0
    if payload is not None:
        # Some CLI versions may additionally carry an explicit boolean --
        # respect it if present, but never let a truthy field override a
        # nonzero exit code.
        verified = verified and bool(payload.get("verified", True))

    report = {
        "id": args.credential_id,
        "verified": verified,
        "exit_code": result.returncode,
        "detail": payload if payload is not None else (stdout or result.stderr.strip()),
    }

    print(json.dumps(report, indent=2))
    if not verified:
        sys.exit(1)


if __name__ == "__main__":
    main()
