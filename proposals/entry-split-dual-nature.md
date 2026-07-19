# Proposal: split the dual-nature entries (deepseek, kimi)

**Status: proposal only. Nothing implemented. Approval required before build.**
Raised 2026-07-19, following the governing-document sweep.

## The problem

`deepseek` and `kimi` are each registered as a single `open_weight` entry, but each
publisher runs two distinct things:

- **downloadable model weights**, governed by a model licence, and
- **a hosted API platform**, governed by service terms and a privacy policy.

The governing-document rule removed publisher privacy policies from the other
open-weight entries because running downloaded weights creates no data-processing
relationship with the publisher. That reasoning does not extend to these two: their
platform documents govern a real relationship the Observatory tracks. Deleting them
would lose genuine coverage.

But leaving them on an `open_weight` entry means the matrix asserts that a set of
downloadable weights has a privacy policy and service terms, which is the same
category error in the other direction.

Currently affected:

| entry | weights-governing | platform-governing |
|---|---|---|
| deepseek | `model_license` | `service_terms` (platform.deepseek.com), `privacy_policy` (cdn.deepseek.com) |
| kimi | `model_license` | `service_terms` (platform.moonshot.ai), `privacy_policy` (platform.kimi.ai) |

This also resolves the open FOLLOWUPS.md item on Kimi/Moonshot segment placement.

## Proposed shape

Split each into two registry entries, mirroring how `mistral-open` and
`mistral-platform` are already handled. That precedent matters: the pattern exists
in the registry today and is not being invented here.

| new entry | segment | openness | documents |
|---|---|---|---|
| `deepseek` (unchanged id) | model_provider | open_weight | `model_license` only |
| `deepseek-platform` | model_provider | closed_api | `service_terms`, `privacy_policy`, and any DPA/subprocessor documents found in scoping |
| `kimi` (unchanged id) | model_provider | open_weight | `model_license` only |
| `moonshot-platform` | model_provider | closed_api | `service_terms`, `privacy_policy`, plus the same |

Naming follows the publisher of each artifact: the Kimi weights are Kimi, the
platform is Moonshot's.

## What moves

**Documents.** Only the platform-governing rows move. No document is edited,
re-fetched differently, or substituted; each keeps its URL, slug and snapshot
history. This is a re-parenting, not a re-capture.

**Extracted values.** Every value whose `source.slug` is a moved document moves with
it. Concretely, from the current corpus:

- `deepseek`: values sourced from `service_terms` and `privacy_policy`
- `kimi`: values sourced from `service_terms` and `privacy_policy`

Values sourced from `model_license` stay on the open-weight entry.

**Nothing is re-extracted.** The extraction records are keyed by provider, so the
split requires either re-running extraction for the four resulting entries, or a
migration that partitions the existing records by source slug. The second is
cheaper and avoids spending API calls to reproduce values we already hold; it is
also auditable, because the resulting values keep their original citations and
content hashes. Recommended: partition, then let the normal change-driven
re-extraction refresh each entry on its own schedule.

## Matrix and provider-page impact

- **Column count** goes from 25 to 27 providers. Cloud Infrastructure is unaffected.
- **Closed API** gains two columns; **Open Weight** keeps its two but they become
  weights-only and will show `not_applicable` across the hosted-platform dimensions,
  which is the correct reading rather than a loss.
- **Per-segment dimension sets** need no change. The existing applicability map
  already removes hosted-service dimensions from the open-weight segment; the split
  simply lets that map do its job instead of being contradicted by the data.
- **Provider pages**: two new pages; the two existing pages lose their
  platform-sourced sections.
- **Exports** follow automatically, since both the workbook and the view-scoped
  exports are generated from the segment tables.

## Change history across the split

This is the part that needs care, because the change feed is keyed on
`provider/slug`.

Snapshots live at `snapshots/<provider>/<slug>/`. Re-parenting a document to a new
provider id would orphan its history: the feed would show the document appearing
from nothing on the split date, and the redline against its previous capture would
be lost.

Two options:

1. **Move the snapshot directories** with the document, and record a one-off
   `provider_renamed_from` note in the new entry. History is preserved intact and
   the feed reads continuously. Cost: the corpus paths change, so any stored
   reference to the old path must be migrated in the same commit.
2. **Leave snapshots in place** and let the new entry point at the old provider's
   directory via an explicit alias. Less disruptive on disk, but it introduces a
   second way to resolve a snapshot path, which is exactly the sort of indirection
   that later causes a silent mismatch.

**Recommended: option 1**, in a single commit, with the split and the corpus move
landing together so no build ever sees a half-migrated state. The split itself
should be classified **non-substantive**: no governing text changes, only which
entry a document is filed under. It should appear in the change feed as an
Observatory curation event, in the same shape as the Qwen generation update, and
must not be phrased in any way implying a provider changed their terms.

## Open questions for approval

1. Are `deepseek-platform` and `moonshot-platform` the right entry ids and display
   names?
2. Should the platform entries be scoped for the full data-protection dimension set
   during the corpus expansion, or carry only the documents they have today?
3. Partition the existing extraction records as recommended, or re-extract the four
   entries from scratch for a clean provenance story?
