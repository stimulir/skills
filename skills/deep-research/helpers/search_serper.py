#!/usr/bin/env python3
"""Serper.dev search — the discovery step. HTTP only, sandbox-native.

Over-collects so the agent can filter: pass --num generously and let the
agent's own judgment pick which results are worth deep-researching.

Needs SERPER_API_KEY (a deep-research required_secret). Get 2,500 free
queries at serper.dev.

  python3 search_serper.py "series B fintech london" --num 20
  python3 search_serper.py "acme corp funding" --type news --out hits.json
"""
from __future__ import annotations

import argparse
import sys

import httpx

from _common import DEFAULT_TIMEOUT, emit, require_env

ENDPOINTS = {
    "search": "https://google.serper.dev/search",
    "news": "https://google.serper.dev/news",
    "places": "https://google.serper.dev/places",
}


def serper_search(query: str, *, num: int, kind: str) -> list[dict]:
    api_key = require_env("SERPER_API_KEY")
    url = ENDPOINTS.get(kind)
    if not url:
        sys.stderr.write(f"error: unknown --type {kind!r} (search|news|places)\n")
        raise SystemExit(2)

    resp = httpx.post(
        url,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": max(1, min(num, 100))},
        timeout=DEFAULT_TIMEOUT,
    )
    if resp.status_code != 200:
        sys.stderr.write(f"error: serper HTTP {resp.status_code}: {resp.text[:300]}\n")
        raise SystemExit(1)

    payload = resp.json()
    rows = payload.get("organic") or payload.get("news") or payload.get("places") or []
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "title": r.get("title"),
                "link": r.get("link") or r.get("url"),
                "snippet": r.get("snippet") or r.get("description"),
                "position": r.get("position"),
                "date": r.get("date"),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Serper.dev discovery search.")
    ap.add_argument("query", help="Search query.")
    ap.add_argument("--num", type=int, default=10, help="Results to request (max 100).")
    ap.add_argument("--type", dest="kind", default="search", choices=list(ENDPOINTS), help="Serper endpoint.")
    ap.add_argument("--out", default=None, help="Write JSON here (else stdout).")
    args = ap.parse_args()

    results = serper_search(args.query, num=args.num, kind=args.kind)
    emit({"query": args.query, "type": args.kind, "count": len(results), "results": results}, args.out)


if __name__ == "__main__":
    main()
