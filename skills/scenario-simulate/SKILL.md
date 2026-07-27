---
name: scenario-simulate
description: Simulate how a described population reacts to a change, and get back a distribution and a narrative — why they split, not just how much. Give it a context (who these people are) and a scenario (what happens to them); it materialises personas, runs their reactions in parallel through the gateway, and folds the result into segment-level counts plus a written explanation. Use for "what if" questions about a market, an electorate, a user base, or a workforce — campaign and pricing what-ifs, policy reaction, feature reception, message testing. Agent-driven, resumable one timestep at a time. Output is synthetic by construction and must never be presented as measurement.
required_secrets: []
---

# Scenario Simulate

Ask what a population would do before it does it.

The engine is domain-agnostic: a **described population** meets **a change**, and
you get a distribution plus a narrative. Buyers meet a campaign, voters meet an
event, users meet a feature, staff meet a policy — one skill, because the
capability was never the domain.

You do the judgment — which segments matter, whether a result is plausible, when
to stop. The helpers materialise the population, fan the reactions out in
parallel, and count deterministically.

## Secrets this skill needs

None of its own. Inference runs on the workspace's gateway key
(`STIMULIR_API_KEY`), which a managed run already injects — that's why
`required_secrets` above is empty, unlike the Serper-backed research skills.
Standalone, export `STIMULIR_API_KEY` yourself; `STIMULIR_API_BASE`,
`STIMULIR_PROJECT_ID` and `STIMULIR_MODEL` are optional overrides.

## Preflight

```bash
pip install httpx           # the only dependency
export STIMULIR_API_KEY=hyb_...
```

## Workflow

### 1. Describe the population — this is the part that decides everything

Write a context file. Segments are yours to choose; the quality of the whole run
rests on them, which is why no helper invents them for you.

```json
{
  "name": "Osun wards",
  "basis": "field reports, Jun–Jul 2026",
  "segments": [
    {"label": "market trader", "share": 0.4, "traits": ["price-sensitive", "informal economy"]},
    {"label": "civil servant", "share": 0.35, "traits": ["salary-dependent"]},
    {"label": "student", "traits": ["online-first"]}
  ]
}
```

`basis` travels with every downstream artifact — it is how a reader knows what
the personas were derived from. Shares need not sum to 1; segments without one
split the remainder equally.

```bash
python3 helpers/population.py --context ctx.json --n 40 --seed 7 --out pop.json
```

`--seed` makes the population reproducible, so two scenarios can be compared
against the *same* people rather than two different draws.

### 2. Step — one timestep per invocation

```bash
python3 helpers/step.py --state pop.json \
    --scenario "the state announces a fuel subsidy removal effective next month" \
    --concurrency 8 --out s1.json
```

Every persona reacts concurrently, one gateway call each, bounded by
`--concurrency`. Each returns `ok` or `error` — one failed persona never sinks
the batch.

Chain steps to let stances evolve; each persona's prior reaction is carried into
the next prompt:

```bash
python3 helpers/step.py --state s1.json --scenario "opposition holds a rally in ward 4" --out s2.json
```

**Why one step per call:** a managed run is synchronous with a 180-second cap, so
a long simulation is a chain — state out, state back in. You also get
resumability, inspectable intermediate states, and the ability to stop a run
that is going wrong.

**Budget it.** Measured on staging, 40 personas at `--concurrency 8` took 190s —
over the cap. The default 12 fits the same population. Raise concurrency
alongside `--n`, and time one step locally before running it managed.

### 3. Judge — this is the part only you can do

Read `s1.json` before aggregating. Are the reactions actually differentiated, or
is every persona saying the same thing in different words? Does any segment
respond in a way the context does not justify? A homogeneous result usually means
the segments were too similar or the traits too thin — fix the context and re-run
rather than aggregating noise.

A lopsided split is not automatically wrong. In testing, "fuel subsidy removed"
returned 35 of 38 opposed — which is plausible for that scenario, and the
reasoning did vary by segment (traders on transport costs, students on
transport-to-campus). But a one-sided result is also what a **leading scenario**
produces. Ask which you have before continuing: reword the scenario neutrally and
re-run; if the split holds, it was the population, not the prompt.

Also check `failed` — personas that errored are excluded from every count, so a
run with many failures is a smaller sample than it looks.

### 4. Aggregate — counts deterministically, narrates once

```bash
python3 helpers/aggregate.py --state s2.json --out report.json
```

Counting happens in Python, not in a model. The narrative is a single call over
the *aggregate*, so it explains the population rather than echoing one persona.
Use `--no-narrative` for counts alone, with no gateway call at all.

## Anti-patterns

- **Never present output as measurement.** Every artifact carries
  `"synthetic": true` and a `basis`. Keep both when rendering.
- **Never put simulated results on a chart with observed data.** Same axes reads
  as the same kind of evidence. Separate them.
- **Never report a confidence interval.** The spread is model variance, not
  sampling error. There is no sampling frame here.
- **Do not treat a rerun as corroboration.** Running it twice and getting the
  same answer measures the model's consistency, not the world's.
- **Do not skip step 3.** Aggregating undifferentiated reactions produces a
  confident-looking number from nothing.
- **Do not use it where you could measure instead.** If a real survey, a poll, or
  live traffic can answer the question, that beats simulation every time. This is
  for questions you cannot run an experiment on yet.
