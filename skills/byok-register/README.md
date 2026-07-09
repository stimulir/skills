# byok-register

Register an adopter's own existing provider API key (OpenAI, Anthropic,
Gemini, Mistral, Bedrock, Azure OpenAI, Together AI, Nebius) with Stimulir
as a bring-your-own-key credential, then verify it works -- the Stage 1
alternate to provisioning a brand-new managed `hyb_*` key, for adopters who
want to keep their existing provider contract and pricing while still
getting Stimulir's gateway benefits (metering, fusion, privacy). Thin
wrappers around the real `stimulir byok add/list/verify` CLI subcommands --
no direct REST calls, no key ever accepted as a plain CLI argument or
written to a log (only an environment-variable *name* is passed in, and the
secret is piped to the CLI's own stdin prompt). Add + verify only; removing
or rotating a credential is a separate, destructive operation and is out of
scope for this skill.

See [`SKILL.md`](./SKILL.md) for the full workflow and
[`install.md`](./install.md) for one-time setup verification.
