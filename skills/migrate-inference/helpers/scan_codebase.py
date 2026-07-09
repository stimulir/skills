#!/usr/bin/env python3
"""Scan a THIRD-PARTY (adopter) codebase for direct LLM provider SDK/HTTP usage.

THIS HELPER DETECTS AND REPORTS ONLY -- it never edits the adopter's source
files. It is pure standard library (no network, no provider SDKs imported)
and walks a directory tree line-by-line looking for text patterns that
indicate a direct OpenAI or Anthropic integration:

  - `import openai`, `from openai import ...`, `OpenAI(` / `AsyncOpenAI(`
    constructor calls                                  -> openai-sdk-compatible
  - `import anthropic`, `from anthropic import ...`,
    `anthropic.Anthropic(` / `Anthropic(` constructor calls
                                                          -> anthropic-sdk-needs-conversion
  - raw `requests`/`httpx`/`fetch`/`axios`/`curl` calls whose URL string
    contains `api.openai.com` or `api.anthropic.com`     -> raw-http (host-specific
                                                             sub-category recorded)

Every hit is one JSON object: {file, line, pattern, category, snippet}. The
agent reading migrate-inference's SKILL.md is the one who decides what to do
with each hit -- this script does not rewrite, comment out, or otherwise
touch anything it scans. Read-only, no side effects, safe to run repeatedly.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Directories we never descend into -- dependency trees and build/VCS noise,
# not adopter-authored source. Matched against any path component.
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "vendor", "venv", ".venv", "env", ".env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", "target", "out",
    "site-packages", ".tox", ".eggs",
}

# File extensions worth grepping. Source + a few config/doc formats where
# inline snippets or SDK wiring commonly show up. Deliberately excludes
# ".env" -- a bare ".env" file has no suffix (Path(".env").suffix == "")
# and its filename also matches DEFAULT_EXCLUDE_DIRS, so it would never be
# scanned anyway; .env files hold key VALUES, not provider SDK call sites,
# so there is nothing for this scanner to usefully detect in them.
DEFAULT_INCLUDE_EXTS = {
    ".py",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".rb", ".go", ".java", ".kt", ".php", ".cs",
    ".yaml", ".yml", ".toml", ".md",
}

# Skip files larger than this -- avoids choking on data/lockfiles/binaries
# that happen to have a source-like extension.
MAX_FILE_BYTES = 2_000_000

# (category, pattern_name, compiled regex). Order matters only for the
# pattern_name recorded in output, not for matching -- every pattern is
# tried against every line independently, so a line can produce >1 hit if
# it genuinely matches more than one pattern (e.g. "import openai, anthropic").
PATTERNS = [
    # --- openai-sdk-compatible ---------------------------------------------
    ("openai-sdk-compatible", "import openai",
     re.compile(r"^\s*import\s+openai\b")),
    ("openai-sdk-compatible", "from openai import",
     re.compile(r"^\s*from\s+openai\b")),
    ("openai-sdk-compatible", "require('openai')",
     re.compile(r"require\(\s*['\"]openai['\"]\s*\)")),
    ("openai-sdk-compatible", "import ... from 'openai'",
     re.compile(r"import\s+.*\bfrom\s+['\"]openai['\"]")),
    ("openai-sdk-compatible", "OpenAI(",
     re.compile(r"\bOpenAI\s*\(")),
    ("openai-sdk-compatible", "AsyncOpenAI(",
     re.compile(r"\bAsyncOpenAI\s*\(")),
    ("openai-sdk-compatible", "openai.OpenAI(",
     re.compile(r"\bopenai\.OpenAI\s*\(")),
    ("openai-sdk-compatible", "openai.ChatCompletion",
     re.compile(r"\bopenai\.ChatCompletion\b")),

    # --- anthropic-sdk-needs-conversion --------------------------------------
    ("anthropic-sdk-needs-conversion", "import anthropic",
     re.compile(r"^\s*import\s+anthropic\b")),
    ("anthropic-sdk-needs-conversion", "from anthropic import",
     re.compile(r"^\s*from\s+anthropic\b")),
    ("anthropic-sdk-needs-conversion", "require('@anthropic-ai/sdk')",
     re.compile(r"require\(\s*['\"]@anthropic-ai/sdk['\"]\s*\)")),
    ("anthropic-sdk-needs-conversion", "import ... from '@anthropic-ai/sdk'",
     re.compile(r"import\s+.*\bfrom\s+['\"]@anthropic-ai/sdk['\"]")),
    ("anthropic-sdk-needs-conversion", "anthropic.Anthropic(",
     re.compile(r"\banthropic\.Anthropic\s*\(")),
    ("anthropic-sdk-needs-conversion", "Anthropic(",
     re.compile(r"(?<!\.)\bAnthropic\s*\(")),
    ("anthropic-sdk-needs-conversion", "AnthropicVertex(/AnthropicBedrock(",
     re.compile(r"\bAnthropic(Vertex|Bedrock)\s*\(")),
    ("anthropic-sdk-needs-conversion", "client.messages.create",
     re.compile(r"\.messages\.create\s*\(")),

    # --- raw-http (host string match, provider recorded in snippet) --------
    ("raw-http", "raw HTTP call to api.openai.com",
     re.compile(r"[\"']https?://api\.openai\.com[^\"']*[\"']")),
    ("raw-http", "raw HTTP call to api.anthropic.com",
     re.compile(r"[\"']https?://api\.anthropic\.com[^\"']*[\"']")),
]


def iter_source_files(root: Path, include_exts: set[str]) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in DEFAULT_EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in include_exts:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return files


def scan_file(path: Path, root: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    hits = []
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path

    for lineno, line in enumerate(text.splitlines(), start=1):
        for category, pattern_name, regex in PATTERNS:
            if regex.search(line):
                hits.append({
                    "file": str(rel),
                    "line": lineno,
                    "pattern": pattern_name,
                    "category": category,
                    "snippet": line.strip()[:300],
                })
    return hits


def scan_codebase(root: Path, include_exts: set[str] | None = None) -> list[dict]:
    exts = include_exts if include_exts is not None else DEFAULT_INCLUDE_EXTS
    all_hits = []
    for path in sorted(iter_source_files(root, exts)):
        all_hits.extend(scan_file(path, root))
    return all_hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="root directory of the adopter's codebase to scan")
    parser.add_argument(
        "--ext", action="append", default=None,
        help="additional file extension to include (e.g. --ext .vue), repeatable. "
             "Adds to the default set rather than replacing it.",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="path to write the JSON report (default: print to stdout)",
    )
    args = parser.parse_args()

    if not args.target.is_dir():
        raise SystemExit(f"scan_codebase: not a directory: {args.target}")

    include_exts = set(DEFAULT_INCLUDE_EXTS)
    if args.ext:
        include_exts.update(e if e.startswith(".") else f".{e}" for e in args.ext)

    hits = scan_codebase(args.target, include_exts)

    counts: dict[str, int] = {}
    for hit in hits:
        counts[hit["category"]] = counts.get(hit["category"], 0) + 1

    report = {
        "target": str(args.target),
        "total_hits": len(hits),
        "by_category": counts,
        "hits": hits,
    }

    output = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
        print(str(args.out))
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
