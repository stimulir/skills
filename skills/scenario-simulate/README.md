# scenario-simulate

Simulate how a described population reacts to a change: materialise personas
from a context, run their reactions in parallel through the Stimulir gateway,
and fold the result into a segment-level distribution plus a narrative
explaining *why* they split. Domain-agnostic — market, electorate, user base, or
workforce — because the capability was never the domain. Resumable one timestep
at a time, so a long run survives the managed 180-second budget. `httpx` is the
only dependency and inference rides the workspace gateway key, so
`required_secrets` is empty. Output is synthetic by construction and carries
`"synthetic": true` plus its `basis` — never present it as measurement. See
[`SKILL.md`](./SKILL.md) and [`install.md`](./install.md).
