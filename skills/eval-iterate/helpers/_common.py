#!/usr/bin/env python3
"""Shared plumbing for the eval-iterate helpers.

Two things only: running the stimulir CLI and JSON-decoding its --json
output, and resolving a console deep link the same way the CLI does when it
prints one. Nothing here decides anything about an iteration.

Every helper in this skill shells out to the stimulir CLI rather than
speaking REST, matching eval-run and prompt-versioning: the CLI already owns
login and session caching in ~/.stimulir/, and the MCP server exposes no lab
tools at all, so the CLI is the only operator path to this surface.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

# The console route that renders one eval run. Must stay identical to the
# CLI's CONSOLE_EVAL_ROUTE and to what the Lab page reads off the query
# string: the Lab page is `lab/:section?` and its evaluate panel reads `run`
# and `view`.
CONSOLE_EVAL_ROUTE = "/workspaces/lab/evaluate"

CONFIG_PATH = Path.home() / ".stimulir" / "config.json"


def require_cli(stimulir_bin: str, helper: str) -> None:
    """Fail loudly and early when the CLI is missing, with the reason."""
    if not shutil.which(stimulir_bin):
        raise SystemExit(
            f"{helper}: {stimulir_bin!r} not found on PATH. This helper shells out "
            "to the stimulir CLI rather than reimplementing REST auth, and the MCP "
            "server has no lab tools, so there is no fallback path. Install and "
            "authenticate the CLI first (see install.md), or pass --stimulir-bin "
            "with a valid path."
        )


def run_cli(cmd: list[str], *, helper: str, hint: str = "") -> Any:
    """Run one CLI command that ends in --json and return the decoded body.

    Raises SystemExit with the CLI's own stderr attached on failure. Refusals
    from this surface are structured (a `code` plus a `message`, and often a
    follow-up), so the stderr is forwarded verbatim rather than summarised:
    the two adapter derive refusals differ ONLY by code, and a helper that
    flattened them would tell the caller to give up on something that is a
    build away.
    """
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if proc.stderr:
            sys.stderr.write(proc.stderr[-8000:])
        raise SystemExit(
            f"{helper}: `{' '.join(cmd[:5])} ...` failed (exit {proc.returncode}). "
            f"{hint}".strip()
        )
    stdout = proc.stdout.strip()
    if not stdout:
        raise SystemExit(f"{helper}: the CLI returned no output for `{' '.join(cmd[:5])} ...`.")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"{helper}: expected JSON from a --json command but got non-JSON "
            f"output: {stdout[:500]!r}"
        )


def console_base() -> Optional[str]:
    """STIMULIR_CONSOLE_BASE, then `console_base` in ~/.stimulir/config.json.

    Deliberately does NOT reproduce the CLI's `api.` -> `console.` hostname
    derivation. That is CLI internals, and a second implementation of it here
    would be a second place to drift: handing a human a link that 404s on a
    run that exists is worse than handing them a run id and the env var name.
    """
    explicit = os.environ.get("STIMULIR_CONSOLE_BASE")
    if not explicit and CONFIG_PATH.is_file():
        try:
            explicit = json.loads(CONFIG_PATH.read_text()).get("console_base")
        except (json.JSONDecodeError, OSError):
            explicit = None
    if explicit and str(explicit).strip():
        return str(explicit).strip().rstrip("/")
    return None


def console_url(run_id: str, *, view: Optional[str] = None) -> Optional[str]:
    """Deep link to one run, or None when the console origin is unknown."""
    base = console_base()
    if not base:
        return None
    url = f"{base}{CONSOLE_EVAL_ROUTE}?run={run_id}"
    if view:
        url += f"&view={view}"
    return url


def handoff(run_id: str, status: Any, *, view: Optional[str] = None) -> dict[str, Any]:
    """The detach block: run id, status, and a link a human can open.

    This is deliberately everything that is handed back. There is no "now poll
    with ..." field and no helper in this skill accepts a --wait, because both
    put the wait back inside the calling agent's context, which is the exact
    cost this surface exists to remove.
    """
    url = console_url(run_id, view=view)
    return {
        "run_id": run_id,
        "status": status,
        "console_url": url,
        "console_url_hint": (
            None
            if url
            else "Set STIMULIR_CONSOLE_BASE (or `console_base` in ~/.stimulir/config.json) "
            "to get an openable link. Not guessing a host."
        ),
    }


def normalise_rationale(text: str) -> str:
    """Lowercased, whitespace-collapsed form used for duplicate detection."""
    return " ".join(str(text or "").split()).strip().lower()
