"""Stimulir gateway client: the inference layer for every simulated turn.

Kept beside `_common.py` and just as dependency-light: one `httpx.post` against
the OpenAI-compatible chat/completions surface. No SDK, so the helper runs in a
bare sandbox with only httpx installed.

Inference is covered by the gateway key the workspace already injects, so this
skill declares no `required_secrets` of its own.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from _common import require_env

CHAT_COMPLETIONS_PATH = "/api/v1/inference/chat/completions"
DEFAULT_MODEL = "stimulir/fusion"


def api_base() -> str:
    return os.environ.get("STIMULIR_API_BASE", "https://api.stimulir.com").rstrip("/")


def headers() -> dict[str, str]:
    """Auth plus optional project scope (sent only when the workspace sets it)."""
    h = {"Authorization": f"Bearer {require_env('STIMULIR_API_KEY')}"}
    project = os.environ.get("STIMULIR_PROJECT_ID", "").strip()
    if project:
        h["X-Project-Id"] = project
    return h


def complete(
    *,
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 700,
    timeout: float = 60.0,
    tags: list[str] | None = None,
) -> str:
    """One completion. Returns the assistant text.

    Raises on transport/HTTP failure, so callers decide whether one bad turn is
    fatal. `step.py` catches per persona so a single failure never sinks a batch.
    """
    body: dict[str, Any] = {
        "model": model or os.environ.get("STIMULIR_MODEL") or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    if tags:
        body["tags"] = tags

    resp = httpx.post(
        api_base() + CHAT_COMPLETIONS_PATH, headers=headers(), json=body, timeout=timeout
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"unexpected gateway response shape: {exc}") from exc


def complete_json(**kwargs: Any) -> Any:
    """`complete` plus a tolerant JSON parse.

    Models wrap JSON in prose or fences even when told not to, so slice from the
    first brace to the last rather than trusting the whole string.
    """
    text = complete(**kwargs)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])
