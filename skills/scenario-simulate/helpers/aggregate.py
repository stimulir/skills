#!/usr/bin/env python3
"""Fold a simulation state into a distribution plus a narrative.

The distribution is computed deterministically here, because counting is not a job for
a model. The narrative is one gateway call over the *aggregate*, not over raw
reactions, so it summarises the population rather than echoing one persona.

  python3 aggregate.py --state s2.json --out report.json
  python3 aggregate.py --state s2.json --no-narrative --out counts.json

Every output carries `synthetic: true` and the `basis` the population was built
from. Keep both when rendering: the numbers are model variance, not measurement.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from _common import emit, load_json
from gateway import complete

STANCES = ("support", "oppose", "neutral")

NARRATIVE_SYSTEM = (
    "You summarise the result of a synthetic population simulation for an "
    "analyst. Explain WHY the population split the way it did and where the "
    "disagreement sits. Three sentences maximum. State plainly that this is "
    "simulated, not measured. No numbers beyond those given to you."
)


def distribution(reactions: list[dict]) -> dict:
    ok = [r for r in reactions if r.get("ok")]
    failed = [r for r in reactions if not r.get("ok")]

    overall = Counter((r.get("stance") or "unknown").lower() for r in ok)
    by_segment: dict[str, Counter] = defaultdict(Counter)
    intensity: dict[str, list[float]] = defaultdict(list)

    for r in ok:
        seg = r.get("segment") or "unknown"
        by_segment[seg][(r.get("stance") or "unknown").lower()] += 1
        try:
            intensity[seg].append(float(r.get("intensity") or 0.0))
        except (TypeError, ValueError):
            pass

    concerns = Counter(
        c.strip().lower() for r in ok for c in (r.get("concerns") or []) if isinstance(c, str) and c.strip()
    )

    total = len(ok)
    return {
        "responded": total,
        "failed": len(failed),
        "overall": {s: overall.get(s, 0) for s in STANCES},
        "overall_share": (
            {s: round(overall.get(s, 0) / total, 3) for s in STANCES} if total else {}
        ),
        "by_segment": {
            seg: {
                "counts": {s: c.get(s, 0) for s in STANCES},
                "mean_intensity": (
                    round(sum(intensity[seg]) / len(intensity[seg]), 3) if intensity[seg] else None
                ),
            }
            for seg, c in sorted(by_segment.items())
        },
        "top_concerns": [{"concern": k, "count": v} for k, v in concerns.most_common(8)],
    }


def narrate(state: dict, dist: dict, *, timeout: float) -> str:
    lines = [
        f"Population: {state.get('population')} ({dist['responded']} simulated respondents)",
        f"Derived from: {state.get('basis')}",
        f"Scenario: {state.get('scenario')}",
        f"Split: {dist['overall']}",
        "By segment: "
        + "; ".join(f"{k}={v['counts']}" for k, v in dist["by_segment"].items()),
        "Top concerns: " + ", ".join(c["concern"] for c in dist["top_concerns"][:5]),
    ]
    return complete(
        system=NARRATIVE_SYSTEM,
        user="\n".join(lines),
        max_tokens=350,
        timeout=timeout,
        tags=["scenario-simulate", "narrative"],
    ).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Distribution + narrative over a simulation state.")
    ap.add_argument("--state", required=True, help="Output of step.py.")
    ap.add_argument("--no-narrative", action="store_true", help="Counts only; no gateway call.")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    state = load_json(args.state)
    dist = distribution(state.get("reactions") or [])

    report = {
        # Load-bearing: this output must never be mistaken for measurement.
        "synthetic": True,
        "basis": state.get("basis"),
        "population": state.get("population"),
        "step": state.get("step"),
        "scenario": state.get("scenario"),
        "distribution": dist,
        "history": state.get("history") or [],
    }
    if not args.no_narrative and dist["responded"]:
        report["narrative"] = narrate(state, dist, timeout=args.timeout)

    emit(report, args.out)


if __name__ == "__main__":
    main()
