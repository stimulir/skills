#!/usr/bin/env python3
"""Read-only onboarding gate: install-check -> login-check -> workspace check.

This helper is a REPORTER, not an actor. It imports check_environment.py's
functions directly (no subprocess-of-a-subprocess) and layers a single
next-action decision on top of its report -- including the real
`workspace.active_workspace_id` signal read from ~/.stimulir/config.json
(NOT inferred from workspace count: an authenticated account can have
exactly one workspace and still not have selected it yet, so "1 workspace
exists" alone is not "ready"). It never calls `stimulir workspace use <id>`
itself, even when there's only one candidate to pick.

It NEVER runs any of the following, because each either requires interactive
human input or mutates remote/local state:
    stimulir login                  (device-flow browser interaction)
    stimulir login --token <token>  (the caller must supply the token)
    stimulir workspace use <id>     (mutates the CLI's local selection)
    stimulir keys create ...        (creates a real, billable credential)

Instead, for each gate that isn't already satisfied, this helper stops and
returns a `next_command` string -- the exact command a human (or the agent,
with explicit user confirmation) should run next. Idempotent: running this
twice in a row does not change any state, it just re-reports it.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_environment import run_checks  # noqa: E402


def next_step(report: dict) -> dict:
    """Given a check_environment report, decide the single next action.

    Returns {"stage": ..., "done": bool, "next_command": str|None, "reason": str}.
    Stops at the FIRST unmet gate -- install, then auth, then workspace
    selection -- since each later stage depends on the one before it.
    """
    cli = report["cli"]
    auth = report["auth"]
    workspace = report["workspace"]

    if not cli["installed"]:
        return {
            "stage": "install",
            "done": False,
            "next_command": "uv tool install stimulir",
            "reason": "stimulir CLI is not on PATH.",
        }

    if not auth["authenticated"]:
        return {
            "stage": "login",
            "done": False,
            "next_command": "stimulir login",
            "reason": (
                "Not authenticated (or the cached 30-day session expired). "
                "This is an interactive device-flow login -- run it yourself, "
                "this helper will not attempt it for you. For headless/CI use: "
                "stimulir login --token <token>"
            ),
        }

    workspaces = auth.get("workspaces") or []
    if len(workspaces) == 0:
        return {
            "stage": "workspace",
            "done": False,
            "next_command": None,
            "reason": (
                "Authenticated, but `stimulir workspace list --json` returned "
                "zero workspaces. Create/join a workspace in the Stimulir "
                "console, then re-run this helper."
            ),
        }

    if workspace["active_workspace_id"]:
        # A workspace is already selected (read from ~/.stimulir/config.json)
        # -- confirm it's still a member of the authenticated list rather
        # than trusting a stale local file blindly.
        active_id = workspace["active_workspace_id"]
        known_ids = {w.get("id") if isinstance(w, dict) else w for w in workspaces}
        if active_id in known_ids:
            return {
                "stage": "workspace",
                "done": True,
                "next_command": None,
                "reason": f"Workspace {active_id} is already selected.",
            }
        # Selected id isn't in the current membership list -- stale local
        # state (e.g. removed from a workspace since last `workspace use`).
        return {
            "stage": "workspace",
            "done": False,
            "next_command": "stimulir workspace use <id>",
            "reason": (
                f"~/.stimulir/config.json points at workspace {active_id}, but "
                "that id is not in the current `stimulir workspace list --json` "
                "membership. Ask the user which of the listed workspaces to use."
            ),
        }

    if len(workspaces) == 1:
        ws = workspaces[0]
        ws_id = ws.get("id") if isinstance(ws, dict) else ws
        return {
            "stage": "workspace",
            "done": False,
            "next_command": f"stimulir workspace use {ws_id}",
            "reason": (
                "Exactly one workspace is available and none is selected yet. "
                "Confirm with the user, then run the command above."
            ),
        }

    return {
        "stage": "workspace",
        "done": False,
        "next_command": None,
        "reason": (
            f"Authenticated with {len(workspaces)} workspaces available and none "
            "selected yet. Ask the user which one to use, then run: "
            "stimulir workspace use <id>"
        ),
    }


def bootstrap() -> dict:
    report = run_checks()
    step = next_step(report)
    return {
        "checks": report,
        "next_step": step,
        "ready_for_key_and_smoke_test": step["stage"] == "workspace" and step["done"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    result = bootstrap()
    print(json.dumps(result, indent=2))

    # Exit 0 regardless -- an unmet gate is a normal finding for this
    # helper to report, not a crash. The agent reads next_step and decides
    # what to do (including asking the user to run an interactive command).
    return 0


if __name__ == "__main__":
    sys.exit(main())
