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
