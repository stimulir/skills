#!/usr/bin/env python3
"""Build a synthetic population from a context description.

One population = N personas, each a compact dict the step loop can role-play.
Segments come from the context you supply; this helper materialises and
validates them, and records what the population was derived from so the
provenance travels with every downstream artifact.

  python3 population.py --context ctx.json --n 40 --out pop.json
  python3 population.py --context ctx.json --n 40 --seed 7 --out pop.json

The context file is JSON:

  {"name": "Osun wards", "basis": "field reports Jun-Jul 2026",
   "segments": [{"label": "market trader", "share": 0.4,
                 "traits": ["price-sensitive", "informal economy"]}, ...]}

`share` values are normalised, so they need not sum to 1. Segments without an
explicit share are weighted equally across the remainder.
"""
from __future__ import annotations

import argparse
import random
import sys

from _common import emit, load_json


def _normalise_segments(segments: list[dict]) -> list[dict]:
    """Fill missing shares equally, then normalise to sum 1."""
    if not segments:
        raise SystemExit("error: context has no segments")

    explicit = [s for s in segments if isinstance(s.get("share"), (int, float))]
    claimed = sum(float(s["share"]) for s in explicit)
    unclaimed = [s for s in segments if s not in explicit]
    if unclaimed:
        remainder = max(0.0, 1.0 - claimed) or 1.0
        each = remainder / len(unclaimed)
        for s in unclaimed:
            s["share"] = each

    total = sum(float(s["share"]) for s in segments) or 1.0
    for s in segments:
        s["share"] = float(s["share"]) / total
    return segments


def _allocate(segments: list[dict], n: int) -> list[dict]:
    """Largest-remainder allocation so the counts sum to exactly n."""
    raw = [(s, s["share"] * n) for s in segments]
    counts = [(s, int(v)) for s, v in raw]
    shortfall = n - sum(c for _, c in counts)
    # Hand the leftover seats to the biggest fractional parts, largest first.
    order = sorted(range(len(raw)), key=lambda i: raw[i][1] - int(raw[i][1]), reverse=True)
    counts = [list(pair) for pair in counts]
    for i in order[:shortfall]:
        counts[i][1] += 1
    return [{"segment": s, "count": c} for s, c in counts]


def build(context: dict, *, n: int, seed: int | None) -> dict:
    rng = random.Random(seed)
    segments = _normalise_segments(list(context.get("segments") or []))

    personas: list[dict] = []
    for block in _allocate(segments, n):
        seg = block["segment"]
        traits = list(seg.get("traits") or [])
        for i in range(block["count"]):
            personas.append(
                {
                    "id": f"{seg.get('label', 'segment')}-{i + 1}".replace(" ", "-").lower(),
                    "segment": seg.get("label", "segment"),
                    "traits": traits,
                    # A stable per-persona tilt so identical segment members do
                    # not answer identically. Seeded, so runs are reproducible.
                    "disposition": round(rng.uniform(-1.0, 1.0), 3),
                }
            )

    return {
        "synthetic": True,
        "basis": context.get("basis") or "unspecified",
        "population": context.get("name") or "unnamed",
        "seed": seed,
        "size": len(personas),
        "segments": [
            {"label": s.get("label", "segment"), "share": round(s["share"], 4)} for s in segments
        ],
        "personas": personas,
        "step": 0,
        "history": [],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Materialise a synthetic population from context.")
    ap.add_argument("--context", required=True, help="JSON context file (see module docstring).")
    ap.add_argument("--n", type=int, default=30, help="Number of personas to materialise.")
    ap.add_argument("--seed", type=int, default=None, help="Fix for reproducible populations.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.n < 1:
        sys.stderr.write("error: --n must be at least 1\n")
        raise SystemExit(2)

    state = build(load_json(args.context), n=args.n, seed=args.seed)
    emit(state, args.out)


if __name__ == "__main__":
    main()
