#!/usr/bin/env python3
"""Compile a competitor / opposition brief from a structured profile.

Deterministic formatting only. The JUDGMENT — what the positioning is, what
the pricing means, which moves matter — is the agent's, and arrives already
structured in the profile JSON. This helper turns that into a shippable
Markdown brief (and an optional side-by-side comparison against your own
company), with every claim carrying its source.

Profile shape (a single JSON object, or a list of them for a comparison):
  {
    "name": "Acme Corp",
    "url": "https://acme.com",
    "attributes": {
      "positioning": "...", "target_segment": "...", "pricing": "...",
      "funding": "...", "headcount": "...", "key_people": "...",
      "recent_moves": "...", "strengths": "...", "weaknesses": "..."
    },
    "evidence": [ {"claim": "raised $40M Series B", "source": "https://..."} ]
  }

  python3 brief.py --profile acme.json --out-md acme_brief.md
  python3 brief.py --profile competitors.json --title "Competitive landscape" --out-md brief.md
"""
from __future__ import annotations

import argparse
import sys

from _common import load_json

# Rendered in this order; any missing key is simply skipped.
ATTR_ORDER = [
    ("positioning", "Positioning"),
    ("target_segment", "Target segment"),
    ("pricing", "Pricing"),
    ("funding", "Funding"),
    ("headcount", "Headcount"),
    ("key_people", "Key people"),
    ("recent_moves", "Recent moves"),
    ("strengths", "Strengths"),
    ("weaknesses", "Weaknesses"),
]


def _one(profile: dict) -> list[str]:
    name = profile.get("name") or profile.get("url") or "(unnamed)"
    lines = [f"## {name}"]
    if profile.get("url"):
        lines.append(f"<{profile['url']}>")
    lines.append("")
    attrs = profile.get("attributes") or {}
    for key, label in ATTR_ORDER:
        val = attrs.get(key)
        if val:
            lines.append(f"- **{label}:** {val}")
    lines.append("")
    evidence = profile.get("evidence") or []
    if evidence:
        lines.append("**Evidence**")
        for ev in evidence:
            claim = str(ev.get("claim", "")).strip()
            src = ev.get("source", "")
            lines.append(f"- {claim} — {src}")
        lines.append("")
    return lines


def build_markdown(profiles: list[dict], title: str) -> str:
    lines = [f"# {title}", ""]
    if len(profiles) > 1:
        lines.append(f"{len(profiles)} competitors profiled.")
        lines.append("")
    for p in profiles:
        lines.extend(_one(p))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Compile a competitor/opposition brief.")
    ap.add_argument("--profile", required=True, help="JSON: one profile object, or a list for a comparison.")
    ap.add_argument("--title", default="Competitor brief")
    ap.add_argument("--out-md", default="brief.md")
    args = ap.parse_args()

    data = load_json(args.profile)
    profiles = data if isinstance(data, list) else [data]
    if not all(isinstance(p, dict) for p in profiles):
        sys.stderr.write("error: profile must be a JSON object or a list of objects\n")
        raise SystemExit(2)

    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(profiles, args.title))
    sys.stderr.write(f"wrote {args.out_md} ({len(profiles)} profile(s))\n")


if __name__ == "__main__":
    main()
