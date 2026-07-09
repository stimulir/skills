#!/usr/bin/env python3
"""Read-only check of the local stimulir CLI environment.

THIS HELPER NEVER CHANGES ANYTHING. It shells out to two side-effect-free
stimulir CLI invocations -- `stimulir --version` and `stimulir workspace
list --json` -- and does one more read: `~/.stimulir/config.json`'s
`workspace_id` field, which is where `stimulir workspace use` persists the
active selection (confirmed directly against the file; `workspace list
--json` itself does NOT mark the active one -- only the human-readable
table view does, via a `●` column that has no JSON equivalent). Only the
non-secret `workspace_id` field is read; `~/.stimulir/credentials.json`
(the cached session token) is never opened by this helper. This helper
never runs `stimulir login`, `stimulir keys create`, or `stimulir workspace
use`; those are either interactive (login) or mutate state (workspace use,
keys create), and both are the agent's call to make after reading this
report, not this helper's.

Exit code is always 0 if the checks themselves ran without crashing -- a
missing CLI or missing auth is a normal, expected finding, not a helper
failure. Callers should read the JSON `checks` and act on it, not the
process exit code, except for the case where stimulir itself is not on
PATH at all (still exit 0, but every downstream check reports
"skipped: cli_not_found").
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Where `stimulir workspace use <id>` persists the active selection. Not
# configurable via any documented env var -- this is the CLI's one fixed
# local config location.
STIMULIR_CONFIG_PATH = Path.home() / ".stimulir" / "config.json"


def _run(cmd: list[str], timeout: float = 20.0) -> dict:
    """Run a subprocess and capture its outcome without raising.

    Returns a dict with ok/returncode/stdout/stderr/error so callers can
    inspect exactly what happened instead of catching exceptions.
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "error": None,
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "", "error": "not_found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "", "error": "timeout"}


def check_cli_installed() -> dict:
    """Is `stimulir` on PATH, and what version does it report?"""
    path = shutil.which("stimulir")
    if path is None:
        return {
            "installed": False,
            "path": None,
            "version": None,
            "hint": "stimulir CLI not found on PATH. Run: uv tool install stimulir",
        }
    version_result = _run(["stimulir", "--version"])
    version = version_result["stdout"] if version_result["ok"] else None
    return {
        "installed": True,
        "path": path,
        "version": version,
        "hint": None if version else "stimulir found on PATH but --version failed; see stderr",
        "stderr": version_result["stderr"] if not version_result["ok"] else None,
    }


def check_auth_status(cli_installed: bool) -> dict:
    """Auth status inferred from `stimulir workspace list --json`.

    This is read-only: listing workspaces requires a valid cached session
    but does not create, select, or mutate anything. A failure here is
    treated as "not authenticated" (or "cli not found"), never escalated
    into an exception -- an unauthenticated environment is the expected
    steady state before onboarding completes.
    """
    if not cli_installed:
        return {
            "authenticated": None,
            "workspaces": None,
            "hint": "skipped: cli_not_found",
        }

    result = _run(["stimulir", "workspace", "list", "--json"])
    if not result["ok"]:
        return {
            "authenticated": False,
            "workspaces": None,
            "hint": "Not authenticated (or session expired). Run: stimulir login",
            "stderr": result["stderr"] or None,
        }

    try:
        workspaces = json.loads(result["stdout"]) if result["stdout"] else []
    except json.JSONDecodeError:
        return {
            "authenticated": None,
            "workspaces": None,
            "hint": "stimulir workspace list --json returned non-JSON output; inspect manually",
            "raw_stdout": result["stdout"],
        }

    return {
        "authenticated": True,
        "workspaces": workspaces,
        "hint": None,
    }


def check_active_workspace() -> dict:
    """Read-only: the workspace_id `stimulir workspace use` last persisted.

    Only ~/.stimulir/config.json is opened -- never
    ~/.stimulir/credentials.json (the cached session token). Missing file,
    missing field, or unparseable JSON are all reported as
    active_workspace_id: None, not raised as errors -- an unselected
    workspace is a normal pre-onboarding state.
    """
    if not STIMULIR_CONFIG_PATH.is_file():
        return {"active_workspace_id": None, "config_path": str(STIMULIR_CONFIG_PATH)}
    try:
        config = json.loads(STIMULIR_CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"active_workspace_id": None, "config_path": str(STIMULIR_CONFIG_PATH)}
    return {
        "active_workspace_id": config.get("workspace_id"),
        "config_path": str(STIMULIR_CONFIG_PATH),
    }


def run_checks() -> dict:
    cli = check_cli_installed()
    auth = check_auth_status(cli["installed"])
    workspace = check_active_workspace()

    missing = []
    if not cli["installed"]:
        missing.append("stimulir CLI is not installed -- run: uv tool install stimulir")
    elif not auth["authenticated"]:
        missing.append("Not authenticated -- run: stimulir login")
    elif not workspace["active_workspace_id"]:
        missing.append("No active workspace selected -- run: stimulir workspace use <id>")

    return {
        "cli": cli,
        "auth": auth,
        "workspace": workspace,
        "ready": cli["installed"] and bool(auth["authenticated"]) and bool(workspace["active_workspace_id"]),
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    report = run_checks()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
