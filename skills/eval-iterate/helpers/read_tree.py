#!/usr/bin/env python3
"""Read one eval lineage and fold it into a brief for exactly one iteration.

Thin wrapper around `stimulir lab eval tree <run_id> --json`. Read-only: it
creates nothing, mutates nothing and spends nothing. Pass ANY run id in the
tree -- root, leaf or middle -- and you get the same answer, because the tree
is named by its root and every member run carries that root.

What this adds on top of the raw tree payload is the part an iteration needs
and would otherwise be reconstructed by hand every turn:

  * the champion, meaning the leading prompt_version arm of the bucket the
    requested run belongs to, plus its promotion blockers;
  * PRIOR RATIONALES -- every hypothesis already tried anywhere on this
    lineage. This is the whole reason the loop can learn instead of
    re-proposing what it already disproved, and it is why the rationale
    column exists;
  * unconsumed steers, which arrive on the tree's pending_work rather than
    being pushed anywhere;
  * an advisory budget reading and an advisory projected spend for the next
    branch.

Everything this prints is a REPORT. This helper never refuses an iteration
and never decides one is finished. `iteration_readiness` is advisory: the
API owns the stopping rule and enforces it by refusing a derive, and a
caller that trusted this helper's opinion over the API's refusal would be
reimplementing the budget in the agent's context, which is the thing the
console-side budget exists to prevent.
"""
import argparse
import json
from typing import Any, Optional

from _common import console_url, normalise_rationale, require_cli, run_cli

HELPER = "read_tree.py"

# Runs that have not reached a terminal status. DRAFT counts: a --no-start
# derive leaves a DRAFT child, and the API's open-branch cap counts it.
NON_TERMINAL_STATUSES = {"draft", "queued", "running"}

# The API's documented caps, mirrored here ONLY to report headroom. They are
# server constants and this helper does not enforce them -- if these drift,
# the API's refusal is still correct and this reading is merely stale.
DOCUMENTED_MAX_DEPTH = 8
DOCUMENTED_MAX_OPEN_BRANCHES = 4

PROMPT_KIND = "prompt_version"


def _bucket_for(body: dict, bucket_key: Optional[str]) -> Optional[dict]:
    for bucket in body.get("buckets") or []:
        if isinstance(bucket, dict) and str(bucket.get("bucket") or "") == str(bucket_key or ""):
            return bucket
    return None


def _champion(body: dict) -> tuple[Optional[dict], list[str]]:
    """The arm a derive would branch from, and why it may not be promotable.

    Scoped to the REQUESTED run's bucket. Nodes are only ever ranked inside a
    comparability bucket -- runs that realized the same case set, evaluator,
    judge and context mode -- so reaching across buckets for a "better" score
    would compare arms that never measured the same thing.
    """
    bucket = _bucket_for(body, body.get("requested_bucket"))
    if bucket is None:
        return None, ["no_comparability_key"]
    by_kind = bucket.get("best_by_kind") if isinstance(bucket.get("best_by_kind"), dict) else {}
    entry = by_kind.get(PROMPT_KIND)
    if not isinstance(entry, dict):
        return None, ["no_scored_prompt_arm"]
    return entry, list(entry.get("promotion_blockers") or [])


def _prior_rationales(body: dict) -> list[dict[str, Any]]:
    """Every hypothesis already on this lineage, newest depth last.

    Read the whole tree, not just the current bucket: a hypothesis that was
    tried and failed under a different evaluator is still a hypothesis this
    lineage has already spent money on, and proposing it again is the
    failure mode this list exists to stop.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for node in body.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        rationale = str(node.get("rationale") or "").strip()
        if not rationale:
            continue
        key = normalise_rationale(rationale)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "rationale": rationale,
                "run_id": node.get("run_id"),
                "candidate_key": node.get("candidate_key"),
                "candidate_type": node.get("candidate_type"),
                "depth": node.get("depth"),
                "mean_score": node.get("mean_score"),
                "scored_count": node.get("scored_count"),
                "total_count": node.get("total_count"),
                "eligible_for_promotion": node.get("eligible_for_promotion"),
            }
        )
    out.sort(key=lambda row: (row.get("depth") or 0))
    return out


def _budget(body: dict) -> dict[str, Any]:
    members = [row for row in (body.get("runs") or []) if isinstance(row, dict)]
    depths = [int(row.get("depth") or 0) for row in members]
    open_branches = [
        row
        for row in members
        if int(row.get("depth") or 0) > 0
        and str(row.get("status") or "").lower() in NON_TERMINAL_STATUSES
        and not row.get("archived_at")
    ]
    deepest = max(depths) if depths else 0
    return {
        "deepest_member_depth": deepest,
        "next_child_depth": deepest + 1,
        "documented_max_depth": DOCUMENTED_MAX_DEPTH,
        "open_branch_count": len(open_branches),
        "documented_max_open_branches": DOCUMENTED_MAX_OPEN_BRANCHES,
        "open_branch_run_ids": [row.get("run_id") for row in open_branches],
        "advisory": (
            "Reported, never enforced here. The API owns both caps and refuses a "
            "derive with eval_derive_depth_exceeded or eval_derive_open_branch_limit. "
            "The open-branch count is also only advisory server-side: concurrent "
            "derives from different leaves can overshoot it."
        ),
    }


def _projected_spend(champion: Optional[dict]) -> dict[str, Any]:
    """Roughly what the next branch costs, read before spending it.

    A branch copies the parent's cases verbatim, carries the source arm
    forward as the incumbent and adds exactly one new arm, so it re-runs the
    FULL case set for BOTH arms. The authoritative number is `projected` on
    the derive response; this is the same arithmetic one call earlier, so the
    number is available before the money is committed rather than after.
    """
    case_count = int(champion.get("total_count") or 0) if champion else 0
    return {
        "case_count": case_count,
        "candidate_count": 2,
        "result_count": case_count * 2,
        "note": (
            "Estimated from the champion's case count x 2 arms. The derive response's "
            "`projected` block is authoritative."
        ),
    }


def _readiness(body: dict, champion: Optional[dict], budget: dict) -> dict[str, Any]:
    blockers: list[str] = []
    if not body.get("requested_bucket"):
        blockers.append("requested_run_has_no_comparability_key")
    if champion is None:
        blockers.append("no_scored_prompt_version_arm_to_branch_from")
    elif champion.get("mean_score") is None:
        blockers.append("champion_has_no_mean_score")
    if budget["next_child_depth"] > budget["documented_max_depth"]:
        blockers.append("depth_cap_reached")
    if budget["open_branch_count"] >= budget["documented_max_open_branches"]:
        blockers.append("open_branch_cap_reached")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "advisory": (
            "A reading, not a gate. Nothing here refuses a derive; the API does. "
            "When it refuses, that refusal IS the stop signal for this lineage -- "
            "report it and end the invocation rather than working around it."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="any run id in the tree: root, leaf or middle")
    parser.add_argument(
        "--include-archived", action="store_true",
        help="include archived member runs (archive is one-way; they are hidden by default)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="also print the complete tree payload under `raw` (large on a deep tree)",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    require_cli(args.stimulir_bin, HELPER)
    cmd = [args.stimulir_bin, "lab", "eval", "tree", args.run_id, "--json"]
    if args.include_archived:
        cmd.append("--include-archived")
    body = run_cli(
        cmd,
        helper=HELPER,
        hint="Check the run id exists in this workspace and the CLI session is valid.",
    )
    if not isinstance(body, dict):
        raise SystemExit(f"{HELPER}: expected a JSON object from `lab eval tree`, got {type(body).__name__}.")

    champion, blockers = _champion(body)
    budget = _budget(body)
    pending = body.get("pending_work") if isinstance(body.get("pending_work"), dict) else {}
    review = body.get("review") if isinstance(body.get("review"), dict) else {}

    brief: dict[str, Any] = {
        "requested_run_id": body.get("requested_run_id"),
        "root_run_id": body.get("root_run_id"),
        "requested_bucket": body.get("requested_bucket"),
        "aggregate_status": body.get("aggregate_status"),
        "member_run_count": body.get("member_run_count"),
        "member_status_counts": body.get("member_status_counts"),
        "console_url": console_url(str(body.get("requested_run_id") or args.run_id), view="tree"),
        "champion": champion,
        "champion_promotion_blockers": blockers,
        "champion_action_hint": (champion or {}).get("action_hint"),
        "prior_rationales": _prior_rationales(body),
        "unconsumed_steers": pending.get("unconsumed_steers") or [],
        "unconsumed_steer_count": pending.get("unconsumed_steer_count") or 0,
        "pending_work": {
            "runs_running": pending.get("runs_running"),
            "runs_queued": pending.get("runs_queued"),
            "results_pending": pending.get("results_pending"),
            "results_running": pending.get("results_running"),
        },
        "review": review,
        "budget": budget,
        "projected_next_spend": _projected_spend(champion),
        "iteration_readiness": _readiness(body, champion, budget),
        "warnings": body.get("warnings") or [],
        "unbucketed_run_ids": body.get("unbucketed_run_ids") or [],
    }
    if args.full:
        brief["raw"] = body

    print(json.dumps(brief, indent=2, default=str))


if __name__ == "__main__":
    main()
