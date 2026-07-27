#!/usr/bin/env python3
"""Run ONE timestep of a scenario simulation.

Each persona reacts to the scenario, in parallel, one gateway call per persona.
The fan-out is ordinary process-level concurrency (asyncio + a semaphore) —
the same shape `deep-research` uses for page fetches, except each parallel unit
is an inference call. A failing persona returns an `error` entry; it never
sinks the batch.

One invocation = one timestep, deliberately. `dedicated-tasks/run` is
synchronous with a 180s cap, so a long simulation is a chain: state in, state
out, feed the output back as the next input.

  python3 step.py --state pop.json --scenario "fuel subsidy removed" --out s1.json
  python3 step.py --state s1.json  --scenario "opposition rally in ward 4" --out s2.json

Reading the output: `reactions[]` carries one entry per persona
(`ok` | `error`). `--concurrency` bounds simultaneous gateway calls.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from _common import emit, load_json
from gateway import complete_json

SYSTEM = (
    "You role-play one member of a described population reacting to a change. "
    "Answer ONLY as that person, grounded in their segment and traits. "
    "Respond with a JSON object and nothing else:\n"
    '{"stance": "support|oppose|neutral", "intensity": 0.0-1.0, '
    '"reasoning": "<one sentence, first person>", '
    '"concerns": ["<short phrase>", ...]}'
)


def _prompt(persona: dict, scenario: str, prior: dict | None) -> str:
    traits = ", ".join(persona.get("traits") or []) or "no specific traits"
    lean = persona.get("disposition", 0.0)
    lines = [
        f"You are a {persona.get('segment', 'person')}.",
        f"Traits: {traits}.",
        f"Baseline disposition (-1 hostile, +1 favourable): {lean}.",
    ]
    if prior:
        lines.append(
            f"Previously you said you were '{prior.get('stance')}' because: "
            f"{prior.get('reasoning')}"
        )
    lines.append(f"\nWhat happens now: {scenario}")
    lines.append("\nHow do you react?")
    return "\n".join(lines)


async def _run(
    personas: list[dict],
    scenario: str,
    priors: dict[str, dict],
    *,
    concurrency: int,
    timeout: float,
    model: str | None,
) -> list[dict]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(p: dict) -> dict:
        async with sem:
            pid = p.get("id", "?")
            try:
                # complete_json is sync; run it off the loop so calls overlap.
                reaction = await asyncio.to_thread(
                    complete_json,
                    system=SYSTEM,
                    user=_prompt(p, scenario, priors.get(pid)),
                    model=model,
                    # A reaction is one sentence plus a few phrases. Generous
                    # budgets here cost wall-clock, and wall-clock is the scarce
                    # resource inside a 180s managed invocation.
                    max_tokens=400,
                    timeout=timeout,
                    tags=["scenario-simulate", f"segment:{p.get('segment', 'unknown')}"],
                )
                return {
                    "ok": True,
                    "id": pid,
                    "segment": p.get("segment"),
                    "stance": reaction.get("stance"),
                    "intensity": reaction.get("intensity"),
                    "reasoning": reaction.get("reasoning"),
                    "concerns": reaction.get("concerns") or [],
                }
            except Exception as exc:  # noqa: BLE001 — one bad turn must not abort the run
                return {"ok": False, "id": pid, "segment": p.get("segment"), "error": str(exc)}

    return await asyncio.gather(*(one(p) for p in personas))


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one timestep of a scenario simulation.")
    ap.add_argument("--state", required=True, help="Population or prior step output.")
    ap.add_argument("--scenario", required=True, help="What happens to the population now.")
    # 12 rather than 8: measured on staging, 40 personas at 8 took ~190s, which
    # overruns a managed invocation's 180s budget. Concurrency is the cheapest
    # lever — the calls are I/O-bound.
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--model", default=None, help="Override the gateway model.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    state = load_json(args.state)
    personas = state.get("personas") or []
    if not personas:
        sys.stderr.write("error: state has no personas (run population.py first)\n")
        raise SystemExit(2)

    # Carry each persona's last reaction forward so stances can evolve.
    priors = {r["id"]: r for r in (state.get("reactions") or []) if r.get("ok")}

    reactions = asyncio.run(
        _run(
            personas,
            args.scenario,
            priors,
            concurrency=args.concurrency,
            timeout=args.timeout,
            model=args.model,
        )
    )

    ok = sum(1 for r in reactions if r.get("ok"))
    step = int(state.get("step", 0)) + 1
    history = list(state.get("history") or [])
    history.append({"step": step, "scenario": args.scenario, "ok": ok, "total": len(reactions)})

    state.update({"step": step, "scenario": args.scenario, "reactions": reactions, "history": history})
    emit(state, args.out)
    sys.stderr.write(f"step {step}: {ok}/{len(reactions)} personas reacted\n")


if __name__ == "__main__":
    main()
