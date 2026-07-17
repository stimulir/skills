"""Shared helpers for deep-research: env resolution, JSON I/O, HTTP defaults.

Deliberately tiny and dependency-light so every helper stays runnable in a
bare sandbox with only httpx + trafilatura installed.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

# A real desktop UA — many sites 403 the default httpx UA.
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20.0


def require_env(name: str) -> str:
    """Return env var `name` or exit with a clear, actionable message.

    This is the single place a missing skill secret surfaces. The message
    names the exact variable so a managed-skills run knows which vault key
    to inject (see the skill's `required_secrets`).
    """
    val = os.environ.get(name)
    if not val or not val.strip():
        sys.stderr.write(
            f"error: {name} is not set.\n"
            f"  This skill needs {name} in its environment. In a managed run it\n"
            f"  comes from the workspace vault; standalone, export it yourself.\n"
        )
        raise SystemExit(2)
    return val.strip()


def emit(data: Any, out_path: str | None) -> None:
    """Write JSON to `out_path`, or pretty-print to stdout when None."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        sys.stderr.write(f"wrote {out_path}\n")
    else:
        print(text)


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
