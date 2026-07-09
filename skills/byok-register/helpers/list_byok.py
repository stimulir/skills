#!/usr/bin/env python3
"""List registered BYOK credentials in the active Stimulir workspace.

Wraps `stimulir byok list --json`. Read-only, no side effects, no
confirmation gate. Passes the CLI's own JSON straight through -- this
helper does not reshape or interpret it; that's the calling agent's job.
"""
import argparse
import json
import shutil
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    if shutil.which("stimulir") is None:
        raise SystemExit(
            "list_byok.py: `stimulir` CLI not found on PATH. This skill assumes "
            "`connect` has already run (CLI installed + authenticated + workspace "
            "selected) -- see install.md."
        )

    cmd = ["stimulir", "byok", "list", "--json"]
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise SystemExit("list_byok.py: `stimulir byok list` timed out after 30s.")

    if result.returncode != 0:
        raise SystemExit(
            f"list_byok.py: `stimulir byok list` failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    stdout = result.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else []
    except json.JSONDecodeError:
        raise SystemExit(f"list_byok.py: could not parse CLI output as JSON: {stdout[:500]}")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
