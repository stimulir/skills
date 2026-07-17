#!/usr/bin/env python3
"""Fetch one URL and extract its main text.

Two paths, same output shape:
  - default: httpx GET + trafilatura extraction. No browser. Runs in a bare
    sandbox. Good for static and most server-rendered pages.
  - --browser: browser-use (Chromium) for JS-heavy / interactive pages. Needs
    a real browser (a MicroVM image with Chromium, or local Playwright) AND an
    LLM key, because browser-use is itself an agent. Falls back to the httpx
    path with a clear note if the browser stack isn't available.

  python3 fetch_page.py https://example.com
  python3 fetch_page.py https://spa.example.com --browser --out page.json
"""
from __future__ import annotations

import argparse
import sys

import httpx

from _common import DEFAULT_TIMEOUT, DEFAULT_UA, emit


def fetch_http(url: str, *, timeout: float, max_chars: int) -> dict:
    """httpx + trafilatura. The sandbox-native default."""
    try:
        import trafilatura
    except ImportError:
        sys.stderr.write("error: trafilatura not installed (pip install trafilatura)\n")
        raise SystemExit(2)

    resp = httpx.get(
        url,
        headers={"User-Agent": DEFAULT_UA},
        follow_redirects=True,
        timeout=timeout,
    )
    resp.raise_for_status()
    html = resp.text
    text = trafilatura.extract(html, include_links=False, include_comments=False) or ""
    # trafilatura's own metadata pass gives a clean title without extra deps.
    meta = trafilatura.extract_metadata(html)
    title = getattr(meta, "title", None) if meta else None
    return {
        "url": str(resp.url),
        "title": title,
        "text": text[:max_chars],
        "chars": len(text),
        "via": "http",
        "ok": True,
    }


def fetch_browser(url: str, *, timeout: float, max_chars: int) -> dict:
    """browser-use (Chromium). The JS-heavy upgrade path.

    Kept intentionally thin — browser-use's own agent loop does the work; we
    only ask it to open the page and return the visible text. Requires the
    `browser` extra AND a browser binary AND an LLM (STIMULIR_API_KEY in a
    managed run, or your own provider key standalone).
    """
    try:
        # Imported lazily so the default path never pays for it.
        from browser_use import Agent, Browser  # type: ignore
    except ImportError:
        sys.stderr.write(
            "note: browser-use not installed; falling back to the http path.\n"
            "      install the browser extra where Chromium is available.\n"
        )
        return fetch_http(url, timeout=timeout, max_chars=max_chars)

    import asyncio

    async def _run() -> dict:
        browser = Browser()
        try:
            agent = Agent(
                task=f"Open {url} and return the full visible article/body text, verbatim.",
                browser=browser,
            )
            result = await agent.run()
            text = str(result)[:max_chars]
            return {"url": url, "title": None, "text": text, "chars": len(text), "via": "browser", "ok": True}
        finally:
            await browser.close()

    return asyncio.run(_run())


def fetch(url: str, *, use_browser: bool, timeout: float, max_chars: int) -> dict:
    try:
        if use_browser:
            return fetch_browser(url, timeout=timeout, max_chars=max_chars)
        return fetch_http(url, timeout=timeout, max_chars=max_chars)
    except Exception as exc:  # noqa: BLE001 — report per-URL, never crash a batch
        return {"url": url, "title": None, "text": "", "chars": 0, "via": "error", "ok": False, "error": str(exc)[:200]}


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch + extract one page.")
    ap.add_argument("url")
    ap.add_argument("--browser", action="store_true", help="Use browser-use (Chromium) instead of httpx.")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--max-chars", type=int, default=20000, help="Truncate extracted text.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    result = fetch(args.url, use_browser=args.browser, timeout=args.timeout, max_chars=args.max_chars)
    emit(result, args.out)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
