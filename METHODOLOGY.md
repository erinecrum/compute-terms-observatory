# Methodology and Disclosure

## How this site works

The Compute Terms Observatory is an automated research tracker. It works in
three stages:

1. **Archive.** Twice daily, an automated workflow fetches the public terms of
   service, service level agreements, and related legal pages of the tracked
   providers and archives a plain text snapshot. The "last checked" timestamp
   on the main page reflects the most recent run. All snapshots and their
   full change history are public in this site's repository.

2. **Detect.** When a provider's terms change, the system captures the exact
   diff between the old and new text. The change log on this site is generated
   from those diffs.

3. **Classify.** An AI model (Claude, by Anthropic) reads the changed
   documents and classifies them against a fixed, published taxonomy of
   contract terms. Every classification must include a verbatim supporting
   quote from the source document, and the system mechanically verifies that
   the quote actually appears in the archived text. Classifications whose
   quotes cannot be verified are marked "unverified" and should be given no
   weight.

## What this site is not

This site is AI-generated analysis of public documents. No attorney reviews
individual classifications before publication. Nothing here is legal advice,
and no attorney-client relationship is created by reading it. Classifications
may be wrong, incomplete, or out of date, and public terms are only the
starting point: negotiated agreements routinely differ from a provider's
public documents.

Do not rely on this site for any decision. Read the underlying documents,
which are linked from every datapoint, and consult your own counsel.

## Corrections

Every datapoint links to its source and to the archived snapshot it was
classified from. If you spot an error, open an issue in the repository or
email the address on the About page. Corrections are logged publicly.

## Provenance

Each classification records the model used, the date, and the snapshot
version it was derived from, so any datapoint on this site can be traced to
the exact text that produced it.
