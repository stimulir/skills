#!/usr/bin/env python3
"""Fetch the raw usage-event ledger for spend-auditing / reconciliation.

`usage_summary.py` gives you a pre-aggregated snapshot for one window/
group-by pair -- fine for a dashboard, not sufficient for a real audit.
This helper fetches the underlying per-event records (`GET
/api/v1/usage/events`) so the agent can independently re-sum them and
cross-check against a summary, or drill into which individual task/call
produced an unexpected charge.

Auth: prefers shelling out to `stimulir usage events --json` if that
subcommand exists on the installed CLI (same session-cache auth as
usage_summary.py). Falls back to a direct REST call against
STIMULIR_API_URL using STIMULIR_API_KEY if the CLI doesn't expose an
events subcommand -- this is the one helper in this skill that may need
the REST fallback, because raw event listing is inherently paginated and
not every CLI version surfaces it as a first-class subcommand. Either
path returns the same event-list shape to the caller.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

import httpx

DEFAULT_API_URL = "https://api.stimulir.com"


def _run_cli(window: str, group_by: str | None, limit: int | None, cursor: str | None) -> dict | None:
    """Try `stimulir usage events --json`. Returns None if the CLI has no
    such subcommand (so the caller can fall back to REST) or if the binary
    isn't installed at all.
    """
    if shutil.which("stimulir") is None:
        return None

    argv = ["stimulir", "usage", "events", "--window", window, "--json"]
    if group_by:
        argv.extend(["--group-by", group_by])
    if limit is not None:
        argv.extend(["--limit", str(limit)])
    if cursor:
        argv.extend(["--cursor", cursor])

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise SystemExit(f"usage_events.py: 'stimulir usage events' timed out: {e}") from e

    if proc.returncode != 0:
        # Distinguish "subcommand doesn't exist" (fall back to REST) from a
        # real failure of a subcommand that does exist (fail loudly).
        stderr_lower = proc.stderr.lower()
        if "unknown command" in stderr_lower or "no such command" in stderr_lower:
            return None
        raise SystemExit(
            f"usage_events.py: 'stimulir usage events' exited {proc.returncode}.\n"
            f"stderr: {proc.stderr.strip()}"
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"usage_events.py: 'stimulir usage events --json' did not return valid JSON: {e}\n"
            f"stdout: {proc.stdout[:500]}"
        ) from e


def _run_rest(window: str, group_by: str | None, limit: int | None, cursor: str | None) -> dict:
    """GET {STIMULIR_API_URL}/api/v1/usage/events -- REST fallback for when
    the installed `stimulir` CLI has no `usage events` subcommand.
    """
    api_url = os.environ.get("STIMULIR_API_URL", DEFAULT_API_URL).rstrip("/")
    api_key = os.environ.get("STIMULIR_API_KEY")
    if not api_key:
        raise SystemExit(
            "usage_events.py: 'stimulir' CLI has no 'usage events' subcommand and "
            "STIMULIR_API_KEY is not set, so the REST fallback can't authenticate "
            "either. Set STIMULIR_API_KEY (a hyb_* key) -- see install.md."
        )

    params: dict[str, str] = {"window": window}
    if group_by:
        params["group_by"] = group_by
    if limit is not None:
        params["limit"] = str(limit)
    if cursor:
        params["cursor"] = cursor

    url = f"{api_url}/api/v1/usage/events"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
            timeout=30.0,
        )
    except httpx.RequestError as e:
        raise SystemExit(f"usage_events.py: request to {url} failed: {e}") from e

    if response.status_code != 200:
        body_snippet = response.text[:500] if response.text else ""
        raise SystemExit(
            f"usage_events.py: {url} returned HTTP {response.status_code}: {body_snippet}"
        )

    return response.json()


def fetch_usage_events(
    window: str,
    group_by: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict:
    """Fetch raw usage events for `window`, preferring the CLI and falling
    back to REST. Returns the parsed JSON payload from whichever path
    succeeded.
    """
    payload = _run_cli(window, group_by, limit, cursor)
    if payload is not None:
        return payload
    return _run_rest(window, group_by, limit, cursor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window", default="30d",
        help="lookback window, e.g. 24h, 7d, 30d (default: 30d)",
    )
    parser.add_argument(
        "--group-by", default=None,
        help="optional server-side grouping hint, e.g. model, task (events are still itemized)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="max events to fetch in this call (server default applies if omitted)",
    )
    parser.add_argument(
        "--cursor", default=None,
        help="pagination cursor from a previous response's 'next_cursor', if any",
    )
    parser.add_argument(
        "--out", default=None,
        help="write the JSON payload here instead of stdout",
    )
    args = parser.parse_args()

    payload = fetch_usage_events(args.window, args.group_by, args.limit, args.cursor)

    text = json.dumps(payload, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
