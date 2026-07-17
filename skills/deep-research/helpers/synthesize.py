#!/usr/bin/env python3
"""Compile a findings array into a cited Markdown report + a CSV.

Deterministic formatting only — the JUDGMENT (scores, ranking, what matters)
is the agent's job and arrives already baked into the findings you pass in.
This helper never calls a model; it turns the agent's structured conclusions
into shippable artifacts with citations intact.

Findings shape (a JSON list):
  [
    {
      "name": "Acme Corp",            # or "url"
      "url": "https://acme.com",
      "score": 8,                      # optional, agent-assigned
      "summary": "One-paragraph synthesis.",
      "evidence": [ {"quote": "...", "source": "https://..."} ]
    }
  ]

  python3 synthesize.py --findings scored.json --title "Series B fintech" \
      --out-md report.md --out-csv results.csv
"""
from __future__ import annotations

import argparse
import csv
import sys

from _common import load_json


def _label(item: dict) -> str:
    return str(item.get("name") or item.get("url") or "(unnamed)")


def build_markdown(items: list[dict], title: str) -> str:
    ranked = sorted(items, key=lambda it: it.get("score") or 0, reverse=True)
    lines = [f"# {title}", "", f"{len(ranked)} results, ranked by score.", ""]
    for it in ranked:
        score = it.get("score")
        head = f"## {_label(it)}" + (f" — {score}/10" if score is not None else "")
        lines.append(head)
        if it.get("url"):
            lines.append(f"<{it['url']}>")
        lines.append("")
        if it.get("summary"):
            lines.append(it["summary"])
            lines.append("")
        evidence = it.get("evidence") or []
        if evidence:
            lines.append("**Evidence**")
            for ev in evidence:
                quote = str(ev.get("quote", "")).strip()
                src = ev.get("source", "")
                lines.append(f"- \"{quote}\" — {src}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_csv(items: list[dict], path: str) -> None:
    ranked = sorted(items, key=lambda it: it.get("score") or 0, reverse=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "url", "score", "summary", "evidence_count"])
        for it in ranked:
            w.writerow(
                [
                    _label(it),
                    it.get("url", ""),
                    it.get("score", ""),
                    (it.get("summary", "") or "").replace("\n", " "),
                    len(it.get("evidence") or []),
                ]
            )


def main() -> None:
    ap = argparse.ArgumentParser(description="Compile findings into a cited report + CSV.")
    ap.add_argument("--findings", required=True, help="JSON findings array (or {findings:[...]}) .")
    ap.add_argument("--title", default="Research report")
    ap.add_argument("--out-md", default="report.md")
    ap.add_argument("--out-csv", default="results.csv")
    args = ap.parse_args()

    data = load_json(args.findings)
    items = data.get("findings", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        sys.stderr.write("error: findings must be a JSON list (or {findings:[...]})\n")
        raise SystemExit(2)

    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(items, args.title))
    write_csv(items, args.out_csv)
    sys.stderr.write(f"wrote {args.out_md} and {args.out_csv} ({len(items)} items)\n")


if __name__ == "__main__":
    main()
