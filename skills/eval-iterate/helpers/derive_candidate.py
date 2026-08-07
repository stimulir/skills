#!/usr/bin/env python3
"""Branch ONE child run from one arm of a parent run, with a stated hypothesis.

Thin wrapper around `stimulir lab eval derive`. It performs exactly one
derive and returns. It does not loop, does not wait for the child, does not
poll, and does not decide whether another iteration should follow.

Only prompt_version derives. There is deliberately no --kind flag, because
the other two kinds are refused by the API and offering a flag that always
400s would be worse than not offering it:

  * adapter_warm_start is BLOCKED (eval_derive_warm_start_unavailable). It is
    a train-derive, and while the engine can warm-start a PEFT LoRA from an
    exported adapter directory, this console has no SFT job record, no poller
    and no SFT-produced adapter manifest to point one at. Train out of band,
    then hot-swap the result.
  * adapter_hot_swap is OUT OF SLICE (eval_derive_kind_not_implemented). The
    candidate row and the executor already carry adapter id, format, route
    and hot-swap, so it is a build away, not a blocker.

Those two are different answers and this helper keeps them different. Use the
CLI directly (`stimulir lab eval derive ... --kind ...`) if you want to see
the refusal for yourself.

--stop-parent is not exposed here either. It permanently skips the parent's
pending results, which makes the parent a partial measurement forever AND
adds run_stopped to its promotion blockers. That is an operator decision, not
an iteration step. It remains on the CLI.

THE RATIONALE IS THE PRODUCT. A branch with no stated hypothesis is a rerun
with extra steps, and the rationale column is what lets the next iteration
read what this lineage has already disproved instead of proposing it again.
This helper refuses an empty or boilerplate rationale outright, and refuses
one that already appears on the tree unless you say the repeat is deliberate.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

from _common import handoff, normalise_rationale, require_cli, run_cli

HELPER = "derive_candidate.py"

MIN_RATIONALE_CHARS = 24
MIN_RATIONALE_WORDS = 5

# Phrases that pass a length check while stating nothing testable. Matched on
# the normalised form. The list is short on purpose: it catches the reflexes,
# and the length/word floor catches the rest. A rationale that squeaks past
# all three and still says nothing is a judgment failure no helper can catch.
EMPTY_RATIONALES = {
    "improve the prompt",
    "make the prompt better",
    "improve prompt",
    "better prompt",
    "try again",
    "next iteration",
    "iterate on the prompt",
    "new version",
    "test a new prompt",
    "tweak the prompt",
}


def _validate_rationale(rationale: str) -> str:
    text = rationale.strip()
    normalised = normalise_rationale(text)
    if not text:
        raise SystemExit(f"{HELPER}: --rationale is empty. A branch with no stated hypothesis is a rerun.")
    if len(text) < MIN_RATIONALE_CHARS or len(normalised.split()) < MIN_RATIONALE_WORDS:
        raise SystemExit(
            f"{HELPER}: --rationale is too thin ({len(text)} chars, "
            f"{len(normalised.split())} words). Write the hypothesis this branch "
            "tests: what you changed, and what you expect it to move. It is read "
            "back by the next iteration to avoid re-proposing a disproved change."
        )
    if normalised in EMPTY_RATIONALES:
        raise SystemExit(
            f"{HELPER}: --rationale {text!r} states no testable claim. Say what "
            "changed and what you expect it to move, e.g. 'name the currency "
            "explicitly in the output schema; the failures are all unlabelled "
            "amounts, so this should lift the exact-match rate on those rows'."
        )
    return text


def _prior_rationales(stimulir_bin: str, run_id: str) -> list[dict[str, Any]]:
    """Every hypothesis already on this lineage, read straight off the tree.

    Read-only and cheap. This runs BEFORE the derive on purpose: the check it
    feeds is the one mechanism that stops the loop paying twice for the same
    idea, and it is worthless after the money is spent.

    Returns RAW node rows, deliberately unlike read_tree.py's function of the
    same name, which dedupes and sorts by depth for a human to read. This one
    feeds a membership test and wants every node, including the duplicates
    that reading would collapse. Do not "unify" them without checking which
    caller needs which shape.
    """
    body = run_cli(
        [stimulir_bin, "lab", "eval", "tree", run_id, "--json"],
        helper=HELPER,
        hint="Could not read the parent's lineage to check prior hypotheses.",
    )
    rows: list[dict[str, Any]] = []
    if isinstance(body, dict):
        for node in body.get("nodes") or []:
            if isinstance(node, dict) and str(node.get("rationale") or "").strip():
                rows.append(node)
    return rows


def _idempotency_key(run_id: str, rationale: str, explicit: Optional[str]) -> str:
    """Stable across a retried iteration, distinct across a new one.

    A skill that gets re-invoked will re-run this command after a crash or a
    timeout. Keyed on parent + hypothesis, the repeat returns the FIRST child
    and spends nothing, which is exactly the behaviour a retried iteration
    wants. A genuinely new hypothesis produces a different digest and a new
    child, which is what the loop wants next.
    """
    if explicit:
        return explicit
    digest = hashlib.sha256(f"{run_id}\n{normalise_rationale(rationale)}".encode()).hexdigest()
    return f"eval-iterate-{digest[:32]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="parent run id to branch from")
    parser.add_argument(
        "--rationale", required=True,
        help="the hypothesis this branch tests: what changed, and what you expect it to move",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--prompt-file",
        help="file holding the new prompt content, pushed as a NEW version of the source arm's prompt key",
    )
    source.add_argument(
        "--prompt-ref",
        help="an existing prompt as KEY, KEY:VERSION or KEY:LABEL; its key must match the source arm's",
    )
    parser.add_argument(
        "--source-candidate-key",
        help="branch from this arm instead of the parent's best-scoring one",
    )
    parser.add_argument(
        "--instruction",
        help="immutable provenance: what this child was steered with, usually a steer body verbatim",
    )
    parser.add_argument(
        "--idempotency-key",
        help="override the derived retry-safe key (default: digest of parent run id + rationale)",
    )
    parser.add_argument(
        "--no-start", action="store_true",
        help="leave the child DRAFT instead of queueing it. A DRAFT child still "
             "counts against the tree's open-branch cap, so do not walk away from one",
    )
    parser.add_argument(
        "--max-cases", type=int,
        help="cap cases drained by the FIRST execution (1-500). Honoured: it "
             "truncates the claimed case list. It does not cap a re-execution",
    )
    parser.add_argument(
        "--max-candidates", type=int,
        help="cap candidates drained by the FIRST execution (1-50). Same scope as --max-cases",
    )
    parser.add_argument(
        "--allow-repeat-rationale", action="store_true",
        help="permit a hypothesis already on this lineage. Only for a deliberate "
             "re-measurement, and say so in the rationale itself",
    )
    parser.add_argument(
        "--stimulir-bin", default="stimulir",
        help="path to the stimulir CLI binary (default: 'stimulir' on PATH)",
    )
    args = parser.parse_args()

    require_cli(args.stimulir_bin, HELPER)
    rationale = _validate_rationale(args.rationale)

    # The CLI declares --prompt-file as typer.FileText and opens the path
    # itself, so a bad path fails inside typer's argument parsing. Checked
    # here first only so the message names the helper and the path.
    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.is_file():
            raise SystemExit(f"{HELPER}: --prompt-file {args.prompt_file!r} is not a readable file.")
        if not path.read_text().strip():
            raise SystemExit(
                f"{HELPER}: --prompt-file {args.prompt_file!r} is empty. A derive pushes "
                "this content as a new version of the source arm's prompt key, and an "
                "empty prompt is a mistake, not a valid candidate."
            )

    # NOTE: --allow-repeat-rationale skips this block, and with it the ONLY
    # pre-derive read this helper makes. The flag is a wider bypass than its
    # name suggests; that is acceptable because the read exists solely to feed
    # the duplicate check, but do not add other preconditions inside it.
    if not args.allow_repeat_rationale:
        target = normalise_rationale(rationale)
        for node in _prior_rationales(args.stimulir_bin, args.run_id):
            if normalise_rationale(node.get("rationale") or "") == target:
                raise SystemExit(
                    f"{HELPER}: this lineage already tried that hypothesis on run "
                    f"{node.get('run_id')} arm {node.get('candidate_key')} "
                    f"(mean_score {node.get('mean_score')}, "
                    f"{node.get('scored_count')}/{node.get('total_count')} scored). "
                    "Read that result and propose something it does not already "
                    "answer, or pass --allow-repeat-rationale if the repeat is a "
                    "deliberate re-measurement."
                )

    cmd = [
        args.stimulir_bin, "lab", "eval", "derive", args.run_id,
        "--rationale", rationale,
        "--idempotency-key", _idempotency_key(args.run_id, rationale, args.idempotency_key),
        "--json",
    ]
    if args.prompt_file:
        cmd += ["--prompt-file", args.prompt_file]
    else:
        cmd += ["--prompt-ref", args.prompt_ref]
    if args.source_candidate_key:
        cmd += ["--source-candidate-key", args.source_candidate_key]
    if args.instruction:
        cmd += ["--instruction", args.instruction]
    for flag, value in (("--max-cases", args.max_cases), ("--max-candidates", args.max_candidates)):
        if value is not None:
            cmd += [flag, str(value)]
    cmd.append("--no-start" if args.no_start else "--start")

    # Two different failures reach this line and they need OPPOSITE responses,
    # so the hint must not assume one. A structured API refusal carries a
    # `code` and IS the answer: report it and stop. A CLI, auth, or network
    # failure carries no code and is merely broken: fix it and retry. Telling
    # an agent to end the invocation on an expired session would be this
    # skill's own failure mode, so the hint names both branches.
    result = run_cli(
        cmd,
        helper=HELPER,
        hint=(
            "If the output above carries a `code` (eval_derive_*), that is the API "
            "refusing this derive for a stated reason. A refusal is an answer: "
            "report it and end this invocation rather than retrying around it. If "
            "there is no such code, this is a CLI, auth, or network failure "
            "instead: fix it and run the same command again, which is safe because "
            "the idempotency key is stable."
        ),
    )
    if not isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
        return

    child = result.get("run") if isinstance(result.get("run"), dict) else {}
    child_id = str(child.get("id") or "")
    out = {
        "handoff": handoff(child_id or "unknown", child.get("status")),
        "replayed": bool(result.get("replayed")),
        "rationale": rationale,
        "lineage": result.get("lineage"),
        "incumbent_arm": result.get("incumbent_arm"),
        "projected": result.get("projected"),
        "parent": result.get("parent"),
        "raw": result,
    }
    if args.no_start:
        out["next_step"] = (
            f"Child left DRAFT. Start it with `stimulir lab eval execute-run {child_id}`. "
            "It counts against the tree's open-branch cap until it does."
        )
    print(json.dumps(out, indent=2, default=str))
    if out["replayed"]:
        sys.stderr.write(
            f"{HELPER}: replayed under an existing idempotency key. Nothing new was "
            "created and nothing was spent; this is the same child as the first attempt.\n"
        )


if __name__ == "__main__":
    main()
