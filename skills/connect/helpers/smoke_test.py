#!/usr/bin/env python3
"""Send one real inference call and one usage query to prove the loop works.

This is the "send a real task, see the result and the cost" step -- the
whole point of Stage 0 onboarding. It is NOT a dry run: `stimulir infer chat`
is a real, billable inference call against a real model. It requires an
already-authenticated session with a workspace selected; it does not attempt
login, key creation, or workspace selection itself (see bootstrap.py for the
read-only preflight, and SKILL.md for why key creation is a separate,
explicit, confirm-required step this helper never takes on its own).

Two stimulir CLI calls, in order:
    1. stimulir infer chat "<prompt>" --model <model> --json  -- the real task
    2. stimulir usage --window <window> --group-by model --json -- the cost

Fails loudly (non-zero exit, clear stderr message) if the CLI is missing or
the session is not authenticated -- this helper does not silently no-op.

MODEL SELECTION IS WORKSPACE-SPECIFIC. `--model` has no hardcoded default in
this helper on purpose: the model catalog returned by `stimulir models` is
tenant-specific, and not every id it lists is guaranteed routable through
`infer chat` on every workspace (confirmed directly: a model can appear in
`stimulir models --json` and still 404 out of `infer chat` if that
workspace's routing config doesn't wire it up). The agent must pass a model
id it has actually seen work for this workspace -- e.g. one already present
in `stimulir usage --group-by model --json` output, or the first id returned
by `stimulir models --json` that it has verified. If `--model` is omitted,
this helper stops and tells the caller to run `stimulir models --json` and
choose one, rather than guessing a name that may not resolve here.

`--window` and `--group-by` are validated against the CLI's own enums
(`7d|30d|month` and `provider|model|day|...`) by the CLI itself -- this
helper does not re-validate them, it just forwards what it's given and
surfaces the CLI's error if the choice is invalid.
"""
import argparse
import json
import shutil
import subprocess
import sys

DEFAULT_PROMPT = "Say 'stimulir connection verified' and nothing else."
DEFAULT_USAGE_WINDOW = "30d"


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"smoke_test.py: command timed out after {timeout}s: {' '.join(cmd)}"
        )


def require_cli() -> None:
    if shutil.which("stimulir") is None:
        raise SystemExit(
            "smoke_test.py: stimulir CLI not found on PATH. "
            "Run: uv tool install stimulir -- then authenticate with: stimulir login"
        )


def run_inference(prompt: str, model: str, timeout: float) -> dict:
    """Real billable call: stimulir infer chat "<prompt>" --model <model> --json.

    --json is used (not --stream) so this helper gets one parseable
    OpenAI-shaped response object back, including a `usage` block with
    token counts -- --stream is documented in SKILL.md for the agent's own
    interactive verification, not wired into this helper, which needs a
    single structured result, not an SSE token stream.
    """
    cmd = ["stimulir", "infer", "chat", prompt, "--model", model, "--json"]
    result = _run(cmd, timeout=timeout)

    if result.returncode != 0:
        raise SystemExit(
            "smoke_test.py: `stimulir infer chat` failed "
            f"(exit {result.returncode}). If the error mentions an unknown "
            "model, run `stimulir models --json` and pass a --model id "
            "confirmed for this workspace (not every listed id is routable "
            "-- see this file's module docstring). If it mentions auth, run "
            "helpers/bootstrap.py first. stderr:\n" + result.stderr.strip()
        )

    try:
        response = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        raise SystemExit(
            "smoke_test.py: `stimulir infer chat --json` returned non-JSON "
            "output:\n" + result.stdout.strip()
        )

    return {
        "command": cmd,
        "model": model,
        "prompt": prompt,
        "response": response,
    }


def run_usage(window: str, timeout: float) -> dict:
    """Real read-only call: stimulir usage --window <window> --group-by model --json."""
    cmd = ["stimulir", "usage", "--window", window, "--group-by", "model", "--json"]
    result = _run(cmd, timeout=timeout)

    if result.returncode != 0:
        raise SystemExit(
            "smoke_test.py: `stimulir usage` failed "
            f"(exit {result.returncode}). stderr:\n" + result.stderr.strip()
        )

    try:
        usage = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        raise SystemExit(
            "smoke_test.py: `stimulir usage --json` returned non-JSON output:\n"
            + result.stdout.strip()
        )

    return {"command": cmd, "window": window, "usage": usage}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt", default=DEFAULT_PROMPT,
        help=f"prompt to send as the real task (default: {DEFAULT_PROMPT!r})",
    )
    parser.add_argument(
        "--model", required=True,
        help=(
            "model id to run the smoke prompt against. Required, no default -- "
            "run `stimulir models --json` first and pass an id confirmed "
            "routable for this workspace (see module docstring for why)."
        ),
    )
    parser.add_argument(
        "--usage-window", default=DEFAULT_USAGE_WINDOW,
        help=f"usage lookback window (default: {DEFAULT_USAGE_WINDOW})",
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0,
        help="per-command subprocess timeout in seconds (default: 60)",
    )
    args = parser.parse_args()

    require_cli()

    inference = run_inference(args.prompt, args.model, args.timeout)
    usage = run_usage(args.usage_window, args.timeout)

    report = {
        "ok": True,
        "inference": inference,
        "usage": usage,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
