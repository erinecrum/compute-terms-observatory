# Follow-ups (not yet actioned)

Deferred items to revisit deliberately, not in passing.

## Revisit Kimi segment assignment after the per-segment migration lands
The Kimi entry is currently sourced from Moonshot's **platform model-use agreement**,
which is a hosted-service contract (its availability/SLA and service-terms quotes are
verified against that document). That makes Kimi behave like a *service* in several
dimensions the open-weight map treats as inapplicable.

Longer term, Kimi may belong in **Closed API as a platform entry** — parallel to how
`mistral-platform` is classified — with the **open weights tracked as a separate
open-weight entry**. Revisit the segment assignment (and whether to split Kimi into two
registry entries) after the per-segment dimension-set migration is complete.

Raised 2026-07-18.

## Qwen tracked generation lags the provider's own documentation

The registry now tracks **Qwen3-235B-A22B** (Apache-2.0), moved from Qwen2.5-72B on
2026-07-19. Qwen's own `ai_documentation` names **Qwen3.5 and Qwen3.6**, but no
license resolves at those Hugging Face paths yet (401), so the flagship with a
resolvable license is as far as the tracked generation can move today.

Recheck `huggingface.co/Qwen/Qwen3.5-*` and `Qwen3.6-*` at the next run and move the
tracked generation again when a newer flagship license resolves. Each move is an
Observatory curation update, not a provider relicensing.

Raised 2026-07-19.
