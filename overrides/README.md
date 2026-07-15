# Human-verified overrides

Corrections a human (you) has verified against the source documents. These layer
on top of the raw model extraction when the dataset is built, and **survive
re-extraction** because they live here, not in the regenerated extraction JSON.

One file per provider: `overrides/<provider>.yaml`. Only include the dimensions
you have actually reviewed — everything else falls through to the model output.

```yaml
overrides:
  <dimension_key>:
    value: "the corrected/confirmed value"
    citation: "a section heading or a short quoted anchor"   # optional
    citation_document: customer_agreement                    # optional: slug of the cited doc
    confidence: high                                          # optional; defaults to high
    note: "Verified by <name> on <YYYY-MM-DD>: <what/why>."
```

Dimension keys: `availability_definition`, `credit_regime`, `claim_mechanics`,
`sla_exclusions`, `capacity_reservation`, `data_use_ai_training`,
`suspension_rights`, `termination`, `unilateral_modification`,
`governing_law_disputes`.

Fields carrying an override are marked `human_verified: true` in the dataset and
the site can badge them as attorney-reviewed.
