#!/usr/bin/env python3
"""Parallel fan-out research over N targets — the exhaustiveness engine.

This is where "exhaustive" comes from, and it needs no agent-level subagent
tool: the fan-out is ordinary process-level concurrency (asyncio + a
semaphore). One target = one URL to fetch and extract. Runs many at once,
bounded by --concurrency, and returns a per-target result array — one
failure never aborts the batch.

  # from a Serper result file (list of {link}) or a comma list of URLs
  python3 research_targets.py --targets-file hits.json --concurrency 6
  python3 research_targets.py --targets https://a.com,https://b.com --out findings.json

Where a real browser is available, --browser routes every fetch through
browser-use; each browser-use process is itself a research sub-agent, so the
fan-out becomes N parallel agents with zero extra wiring.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from _common import DEFAULT_TIMEOUT, emit, load_json
from fetch_page import fetch


def _targets_from_args(args) -> list[str]:
    urls: list[str] = []
    if args.targets:
        urls.extend(u.strip() for u in args.targets.split(",") if u.strip())
    if args.targets_file:
        data = load_json(args.targets_file)
        rows = data.get("results", data) if isinstance(data, dict) else data
        for r in rows:
            link = r.get("link") or r.get("url") if isinstance(r, dict) else r
            if link:
                urls.append(link)
    # De-dupe, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def _research(urls: list[str], *, concurrency: int, use_browser: bool, timeout: float, max_chars: int) -> list[dict]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(url: str) -> dict:
        async with sem:
            # fetch() is sync; run it off the loop so N fetches truly overlap.
            return await asyncio.to_thread(
                fetch, url, use_browser=use_browser, timeout=timeout, max_chars=max_chars
            )

    return await asyncio.gather(*(one(u) for u in urls))


def main() -> None:
    ap = argparse.ArgumentParser(description="Parallel fetch/extract over many targets.")
    ap.add_argument("--targets", default=None, help="Comma-separated URLs.")
    ap.add_argument("--targets-file", default=None, help="JSON: a list, or a Serper {results:[{link}]}.")
    ap.add_argument("--question", default=None, help="Optional research question (echoed into output for the agent).")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--browser", action="store_true", help="Route every fetch through browser-use (Chromium).")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--max-chars", type=int, default=12000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    urls = _targets_from_args(args)
    if not urls:
        sys.stderr.write("error: no targets (pass --targets or --targets-file)\n")
        raise SystemExit(2)

    results = asyncio.run(
        _research(
            urls,
            concurrency=args.concurrency,
            use_browser=args.browser,
            timeout=args.timeout,
            max_chars=args.max_chars,
        )
    )
    ok = sum(1 for r in results if r.get("ok"))
    emit(
        {
            "question": args.question,
            "target_count": len(urls),
            "ok_count": ok,
            "findings": results,
        },
        args.out,
    )


if __name__ == "__main__":
    main()
