#!/usr/bin/env python3
"""Resolve a prompt by key (+ optional label or version) via the stimulir CLI.

Thin wrapper around `stimulir prompts get KEY [--label L | --version N] --json`.
Read-only -- no side effects, safe to call as often as needed.

This is the CLI-side counterpart to what the adopter's own runtime code
should be calling through the SDK instead (`client.prompts.get(key,
label=...)`) -- this helper is for the AGENT to inspect/compare prompt
content while doing versioning work, not something the adopter's
application imports at request time.

Exactly one of --label / --version may be given. With neither, the CLI
returns whatever its own default resolution is (confirm against `stimulir
prompts get --help` in your environment if this matters -- this helper does
not invent a default of its own).
"""
import argparse
import json
import subprocess


def run_get(key: str, label: str | None, version: int | None) -> dict:
    cmd = ["stimulir", "prompts", "get", key]
    if label:
        cmd += ["--label", label]
    if version is not None:
        cmd += ["--version", str(version)]
    cmd.append("--json")

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise SystemExit(
            f"get_prompt.py: `{' '.join(cmd)}` failed (exit {proc.returncode}):\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"get_prompt.py: could not parse JSON from `{' '.join(cmd)}`: {e}\n"
            f"stdout was: {proc.stdout[:500]}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", help="stable prompt key")
    parser.add_argument("--label", default=None, help="label to fetch, e.g. prod or staging")
    parser.add_argument("--version", type=int, default=None, help="specific version number to fetch")
    args = parser.parse_args()

    if args.label and args.version is not None:
        raise SystemExit("get_prompt.py: pass --label or --version, not both.")

    result = run_get(args.key, args.label, args.version)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
