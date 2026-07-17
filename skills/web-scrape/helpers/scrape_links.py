#!/usr/bin/env python3
"""Extract the links from one page — the follow-and-scrape seed step.

Fetch a page over httpx and pull every <a href> out of it, resolved to
absolute URLs and de-duped. Optionally keep only same-domain links. The output
is a Serper-shaped result list (`{results:[{link, text}]}`) so it feeds
straight into `research_targets.py --targets-file` for parallel scraping — no
reformatting in between.

No browser, no model, no external key — just httpx plus the standard library's
HTML parser, so it runs in a bare sandbox.

  python3 scrape_links.py --url https://example.com
  python3 scrape_links.py --url https://blog.example.com --same-domain-only --limit 50 --out links.json
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from _common import DEFAULT_TIMEOUT, DEFAULT_UA, emit


class _LinkParser(HTMLParser):
    """Collect (href, anchor-text) pairs from every <a> tag. Stdlib only."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def _registrable(netloc: str) -> str:
    """Host without a leading www. — good-enough same-site test, no deps."""
    host = netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def scrape_links(url: str, *, same_domain_only: bool, limit: int, timeout: float) -> list[dict]:
    resp = httpx.get(
        url,
        headers={"User-Agent": DEFAULT_UA},
        follow_redirects=True,
        timeout=timeout,
    )
    resp.raise_for_status()
    base = str(resp.url)
    base_host = _registrable(urlparse(base).netloc)

    parser = _LinkParser()
    parser.feed(resp.text)

    seen: set[str] = set()
    out: list[dict] = []
    for href, text in parser.links:
        absolute = urldefrag(urljoin(base, href)).url
        if urlparse(absolute).scheme not in ("http", "https"):
            continue  # skip mailto:, tel:, javascript:, bare #fragments
        if same_domain_only and _registrable(urlparse(absolute).netloc) != base_host:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append({"link": absolute, "text": text})
        if limit and len(out) >= limit:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract same-or-allowed-domain links from a page.")
    ap.add_argument("--url", required=True, help="Page to pull links from.")
    ap.add_argument("--same-domain-only", action="store_true", help="Keep only links on the page's own host.")
    ap.add_argument("--limit", type=int, default=100, help="Max links to return (0 = no cap).")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out", default=None, help="Write JSON here (else stdout).")
    args = ap.parse_args()

    links = scrape_links(
        args.url,
        same_domain_only=args.same_domain_only,
        limit=args.limit,
        timeout=args.timeout,
    )
    emit(
        {
            "url": args.url,
            "same_domain_only": args.same_domain_only,
            "count": len(links),
            "results": links,
        },
        args.out,
    )


if __name__ == "__main__":
    main()
