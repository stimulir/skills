#!/usr/bin/env python3
"""Register an adopter's own provider API key with Stimulir (bring-your-own-key).

Wraps `stimulir byok add --provider <p> --label <l>`. The provider's raw
secret is NEVER accepted as a CLI argument and NEVER written to a log or
file by this helper. The caller names an environment variable that already
holds the secret (--key-env); this helper reads it in-process and pipes it
to the `stimulir` CLI's own interactive `--secret` prompt over stdin, the
same channel a human typing the secret at a terminal would use. The value
never appears in argv, so it never lands in `ps`, shell history, or a
process-listing tool.

Confirmed directly against the installed CLI (`stimulir byok add --help`):
`--secret` is optional and "omit to be prompted without echo" -- omitting it
makes the CLI's own getpass-style prompt read one line from stdin. That is
the exact indirection this helper relies on.

This is a REAL, IRREVERSIBLE side effect: it registers a live credential in
the adopter's Stimulir workspace. Defaults to a dry run that prints exactly
what would be executed (never the secret value) and does nothing. Pass
--confirm to actually run it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

# Exact provider enum from `stimulir byok add --help` on the installed CLI
# (v0.1.0). Hyphenated forms some docs use (e.g. "gemini", "bedrock",
# "together-ai") are accepted as aliases and mapped to the real enum value.
PROVIDERS = [
    "openai",
    "anthropic",
    "google_gemini",
    "mistral",
    "aws_bedrock",
    "azure_openai",
    "together_ai",
    "nebius",
]

PROVIDER_ALIASES = {
    "gemini": "google_gemini",
    "bedrock": "aws_bedrock",
    "together-ai": "together_ai",
    "together": "together_ai",
    "azure": "azure_openai",
    "azure-openai": "azure_openai",
}


def resolve_provider(value: str) -> str:
    normalized = value.strip().lower()
    normalized = PROVIDER_ALIASES.get(normalized, normalized)
    if normalized not in PROVIDERS and "-" in normalized:
        normalized = PROVIDER_ALIASES.get(normalized.replace("-", "_"), normalized.replace("-", "_"))
    if normalized not in PROVIDERS:
        raise SystemExit(
            f"register_byok.py: unknown --provider {value!r}. "
            f"Valid values: {', '.join(PROVIDERS)} "
            f"(aliases accepted: {', '.join(sorted(PROVIDER_ALIASES))})"
        )
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", required=True, help=f"one of: {', '.join(PROVIDERS)}")
    parser.add_argument("--label", required=True, help="human-readable label for this credential")
    parser.add_argument(
        "--key-env",
        required=True,
        help=(
            "name of an environment variable that already holds the provider's raw "
            "API key, e.g. MY_OPENAI_KEY. This helper reads os.environ[<name>] -- "
            "never pass the key value itself here."
        ),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually run `stimulir byok add`. Without this flag, prints the dry-run plan and exits.",
    )
    args = parser.parse_args()

    provider = resolve_provider(args.provider)

    if shutil.which("stimulir") is None:
        raise SystemExit(
            "register_byok.py: `stimulir` CLI not found on PATH. This skill assumes "
            "`connect` has already run (CLI installed + authenticated + workspace "
            "selected) -- see install.md."
        )

    secret = os.environ.get(args.key_env)
    key_present = bool(secret)
    if args.confirm and not key_present:
        raise SystemExit(
            f"register_byok.py: environment variable {args.key_env!r} is not set or "
            "empty. Export the adopter's existing provider API key into that variable "
            "first -- this helper never accepts the raw key as a CLI argument."
        )

    cmd = ["stimulir", "byok", "add", "--provider", provider, "--label", args.label, "--json"]

    if not args.confirm:
        print(json.dumps({
            "dry_run": True,
            "would_run": cmd,
            "provider": provider,
            "label": args.label,
            "key_env": args.key_env,
            "key_present": key_present,
            "note": (
                "No credential was registered. The secret is never placed on argv; "
                "it is piped to the CLI's own --secret stdin prompt. Re-run with "
                "--confirm to actually register this credential."
            ),
        }, indent=2))
        return

    # secret is piped over stdin to the CLI's own getpass-style --secret
    # prompt -- never passed as --secret <value>, never logged, never
    # written to a file by this helper.
    try:
        result = subprocess.run(
            cmd,
            input=secret + "\n",
            text=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit("register_byok.py: `stimulir byok add` timed out after 60s.")

    if result.returncode != 0:
        # stderr from the CLI on a bad key is a provider rejection message,
        # not the key itself -- the key was never passed as an argument or
        # printed by this helper, so it cannot appear in this output.
        sys.stderr.write(result.stderr)
        raise SystemExit(f"register_byok.py: `stimulir byok add` failed (exit {result.returncode}).")

    stdout = result.stdout.strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {"raw_output": stdout}

    print(json.dumps({"dry_run": False, "provider": provider, "label": args.label, "result": payload}, indent=2))


if __name__ == "__main__":
    main()
