"""Dataset builder: assemble the current comparison dataset from the layers.

Layering order (lowest to highest priority):

    1. raw extraction        (data/extractions/<provider>.json — model output)
    2. commitment programs   (commitment_programs.yaml — the "negotiated, not
                              published" fact on the capacity dimension)
    3. human overrides       (overrides/<provider>.yaml — verified corrections)

The result is one JSON document (data/dataset.json) holding the provider list,
the dimension list, and a provider×dimension matrix of fully-resolved fields with
provenance. The site is rendered purely from this file, so the site can never
show a value that isn't in the traceable dataset.

The change log is assembled from snapshot history so the change feed (a later
step) has its data; with a single snapshot per document it is empty (baselines).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .differ import diff_text
from .extractor import load_extraction
from .overrides import apply_overrides, load_overrides
from .registry import Registry, load_registry
from .schema import (DIMENSIONS, dimension_group, is_applicable, section_of,
                     segment_config, segment_group)
from .snapshot import SnapshotStore
from .scopecheck import check as scope_check
from .textcheck import NON_TEXT_MESSAGE, looks_like_text, sufficient_content

# Which dimensions are SLA-specific (grouped at the bottom of the matrix).
_SLA_DIMS = {"availability_definition", "credit_regime", "claim_mechanics", "sla_exclusions"}

# "Terms last checked" freshness marker, written on every pipeline run and shown on
# the main page. It is public and is NOT a snapshot, so updating it never triggers
# classification and never appears in the change feed.
LAST_CHECKED_PATH = Path("data/last-checked.json")


def write_last_checked() -> str:
    ts = datetime.now(timezone.utc).isoformat()
    LAST_CHECKED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_CHECKED_PATH.write_text(
        json.dumps({"last_checked_utc": ts, "schedule": "twice daily"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return ts


def read_last_checked() -> dict:
    if LAST_CHECKED_PATH.exists():
        try:
            return json.loads(LAST_CHECKED_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}

DISCLAIMER = (
    "These values are an AI's reading of each provider's public terms, not the terms "
    "themselves and not legal advice. They can be wrong, incomplete, or out of date. "
    "Every value links to its source document, so verify anything yourself before you "
    "rely on it."
)


def load_commitment_programs(path: str | Path = "commitment_programs.yaml") -> Dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {prog["provider"]: prog for prog in raw.get("programs", [])}


WAYBACK_STALE_DAYS = 7


def _capture_stale(capture_ts: str, days: int = WAYBACK_STALE_DAYS) -> bool:
    """True if a wayback capture is older than `days` (measured at build time)."""
    if not capture_ts:
        return False
    try:
        cap = datetime.fromisoformat(capture_ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - cap) > timedelta(days=days)


def _license_bucket(value: str) -> str:
    """Normalize a classified model-license value into a filterable bucket. Derived
    from the license data (with its citation), not asserted independently."""
    v = (value or "").lower()
    if not v or "not applicable" in v or "not specified" in v or "unclear" in v:
        return ""
    if "modified mit" in v:
        return "Modified MIT"
    if "apache" in v:
        return "Apache 2.0"
    if "mit" in v:
        return "MIT"
    return "bespoke/community license"


# ---------------------------------------------------------------------------
# Status derivation (Issue 2)
#
# The extractor records only a binary quote-match status ("verified" /
# "unverified"), which conflates two very different things: a value whose quote
# could not be matched, and a value that is simply ABSENT because the provider's
# terms are silent (or the dimension does not apply at all). We derive, at build
# time, one of four honest display statuses from the field. The legacy
# human_verified flag is ignored entirely — everything on the site is presented as
# AI-reviewed, with no human/counsel-verified tier. Raw extraction files are never
# rewritten; this derivation is deterministic and reversible.
# ---------------------------------------------------------------------------

STATUSES = ("quote_verified", "quote_unverified", "no_clause_found", "not_applicable",
            "access_restricted", "not_retrievable")

# The last two describe why a document is absent from the corpus, not what a
# provider's terms say, and they are deliberately kept apart:
#
#   access_restricted  the provider's own configuration blocks retrieval
#                      (robots.txt, CAPTCHA, login wall). Reserved strictly for
#                      that. Never applied to a technical failure on our side or
#                      theirs.
#   not_retrievable    a technical failure (JavaScript-rendered page yielding no
#                      text, a broken provider link).
#
# Both count as absence of captured data for extraction, and both render neutrally
# rather than as warnings: neither is a finding about the provider's terms.
_CAPTURE_ABSENT = ("access_restricted", "not_retrievable")

# Issue 3: absence is shown with exactly two display labels, regardless of the raw
# vocabulary the model used ("not specified", "none", "no", "n/a", ...).
_ABSENCE_DISPLAY = {"no_clause_found": "silent", "not_applicable": "not applicable",
                    "access_restricted": "access restricted by provider",
                    "not_retrievable": "not retrievable"}


def display_value(field: dict) -> str:
    """The value as shown to a reader: absence is normalized to 'silent' / 'not
    applicable'; every substantive value is shown verbatim."""
    return _ABSENCE_DISPLAY.get(field.get("status", ""), field.get("value", ""))

# Values the model returns when it found no governing clause (an ABSENCE, not a
# term). Matched case-insensitively on the whole value with a trailing period
# stripped, so substantive values that merely contain "none" are not caught.
_ABSENCE_VALUES = {
    "", "not specified", "unspecified", "not stated", "not addressed",
    "not mentioned", "unclear", "unknown", "none", "no", "n/a", "na",
    "not applicable", "silent",
}

def _is_absence(value: str) -> bool:
    return (value or "").strip().lower().rstrip(".") in _ABSENCE_VALUES


def _derive_status(field: dict, dim_key: str, group: str, openness: str) -> str:
    """Derive the four-state status. A dimension the segment map removes, and
    model_license on a provider that distributes no weights, resolve to
    not_applicable (the status is kept in the data for compare mode even though the
    segment table does not render the row)."""
    # Capture-absence states describe whether a document reached the corpus at all,
    # which is not something that can be re-derived from the value: by the time a
    # value is suppressed it is empty, and re-deriving would silently downgrade it
    # to "silent", asserting the provider's terms say nothing when in fact we never
    # read the right document. They are authoritative and pass through untouched.
    if field.get("status") in _CAPTURE_ABSENT:
        return field["status"]
    # A recorded commitment-program fact ("negotiated, not published") is a real
    # value, never an absence.
    substantive = bool(field.get("commitment_program")) or not _is_absence(field.get("value", ""))
    if not is_applicable(group, dim_key):
        return "not_applicable"
    if dim_key == "model_license" and openness != "open_weight" and not substantive:
        return "not_applicable"
    if substantive:
        return "quote_verified" if field.get("status") == "verified" else "quote_unverified"
    return "no_clause_found"


def _warn_reason(field: dict, dim_key: str, group: str, openness: str):
    """Reason this cell belongs in the build-warning report, or None. Surfaces real
    content (a verified quote or a citation) that the segment map would drop, so it
    is reviewed rather than silently lost, and 'not applicable' text left in a
    dimension that stays applicable to the segment."""
    verified = field.get("status") == "verified"
    citation = (field.get("citation") or "").strip()
    value_na = (field.get("value", "") or "").strip().lower().rstrip(".") == "not applicable"
    if not is_applicable(group, dim_key):
        if verified:
            return "verified quote in a dimension removed for this segment"
        if citation:
            return "citation in a dimension removed for this segment"
        return None
    if dim_key == "model_license" and openness != "open_weight" and citation:
        return "model_license citation on a provider that distributes no weights"
    if value_na and dim_key != "model_license":
        return "value says 'not applicable' but the dimension applies to this segment"
    return None


def _enrich_capacity(field: dict, program: Optional[dict]) -> dict:
    """Attach the negotiated-commitment fact to the capacity dimension without
    disturbing the published-capacity terms the model extracted."""
    if not program:
        return field
    field = dict(field)
    field["commitment_program"] = {
        "program": program["program"],
        "value": program["value"],  # "negotiated, not published"
        "citation_url": program["citation_url"],
        "note": program.get("citation_note", ""),
    }
    return field


def build_dataset(registry: Optional[Registry] = None) -> dict:
    registry = registry or load_registry("registry.yaml")
    store = SnapshotStore("snapshots")
    programs = load_commitment_programs()

    # Generation-mismatch sweep, run once before the matrix is assembled. Documents
    # naming an older generation than the entry tracks have their values suppressed;
    # documents naming a NEWER one are a registry-update signal, not a data problem,
    # so their values stand and the finding is reported instead.
    from .generation import sweep as _generation_sweep

    stale_extractions: List[dict] = []
    generation_findings = _generation_sweep(registry, store)
    suppress_slugs: Dict[str, Dict[str, str]] = {}
    for g in generation_findings:
        if g.action == "suppress":
            suppress_slugs.setdefault(g.provider, {})[g.slug] = (
                f"source document names {g.found} ({g.mentions} mentions); "
                f"this entry tracks {g.declared}")
    _write_generation_report(generation_findings)
    _write_scope_report(_scope_sweep(registry, store))

    provider_names = registry.provider_names()
    providers_meta: List[dict] = []
    matrix: Dict[str, Dict[str, dict]] = {}
    status_report: List[tuple] = []  # (provider, dim, old_status, new_status, value, flagged)
    warn_rows: List[tuple] = []      # (provider, group, dim, status, reason, excerpt)

    for provider in registry.providers():
        record = load_extraction(provider)
        if record is None:
            continue  # not yet extracted
        record = apply_overrides(record, load_overrides(provider))

        fields = record["fields"]
        # Deterministic commitment-program enrichment on the capacity dimension.
        if "capacity_reservation" in fields:
            fields["capacity_reservation"] = _enrich_capacity(
                fields["capacity_reservation"], programs.get(provider)
            )

        matrix[provider] = fields
        docs_used = record.get("documents_used", [])
        last_updated = max((d.get("fetched_at", "") for d in docs_used), default="")

        # Fetch provenance: read how each document's CURRENT snapshot was obtained
        # (direct / browser / wayback + capture time) from the snapshot metadata, so
        # the site can show it without re-classifying.
        prov = {}
        for doc in registry.for_provider(provider):
            snap = store.current(provider, doc.slug)
            if snap:
                fm = snap.meta.get("fetch_method", "direct")
                cap = snap.meta.get("capture_timestamp", "")
                prov[doc.slug] = {
                    "fetch_method": fm,
                    "capture_timestamp": cap,
                    "stale": fm == "wayback" and _capture_stale(cap),
                }
                # Consistency: are the extracted values reading the current text?
                # The extraction records which capture it used; if the document has
                # since acquired newer TEXT, the matrix is behind the corpus and can
                # contradict the change feed until the provider is re-extracted.
                used = next((d for d in record.get("documents_used", [])
                             if d.get("slug") == doc.slug), None)
                if used:
                    # Identify the capture the values were read from by fetch time,
                    # which is stable, rather than by content hash, which changes
                    # whenever the corpus is renormalized and would flag every
                    # document rather than the ones actually behind.
                    read = next((s for s in store.history(provider, doc.slug)
                                 if s.fetched_at == used.get("fetched_at")), None)
                    read_date = read.content_date if read else used.get("fetched_at", "")
                    # Recency, not equality: only flag when the document's current
                    # text genuinely post-dates what the values were read from.
                    if read_date and snap.content_date > read_date:
                        stale_extractions.append({
                            "provider": provider,
                            "slug": doc.slug,
                            "document": doc.name,
                            "extracted_at": record.get("extracted_at", ""),
                            "values_read_from_content_date": read_date,
                            "current_content_date": snap.content_date,
                            "current_capture": snap.stamp,
                            "current_is_archived": snap.is_archived,
                        })
        # Documents the provider blocks. Declared in the registry rather than
        # inferred from a failure, so the state is a decision on the record instead
        # of a side effect of the last run's luck.
        for doc in registry.for_provider(provider):
            if doc.capture_state != "access_restricted":
                continue
            for f in fields.values():
                if (f.get("source") or {}).get("slug") != doc.slug:
                    continue
                f["status"] = "access_restricted"
                f["capture_cause"] = doc.capture_cause or ""
                f["value"] = ""
                f["citation"] = ""

        # Captures already in the corpus that fall below the per-doc_type content
        # floor. The fetcher now refuses these outright, but snapshots taken before
        # the guard existed are still here, and a stub extracts as near-silent.
        for doc in registry.for_provider(provider):
            snap = store.current(provider, doc.slug)
            if not snap or not snap.text:
                continue
            enough, size = sufficient_content(snap.text, doc.doc_type)
            if enough:
                continue
            for f in fields.values():
                if (f.get("source") or {}).get("slug") != doc.slug:
                    continue
                f["status"] = "not_retrievable"
                f["capture_cause"] = "insufficient_capture"
                f["value"] = ""
                f["citation"] = ""
                f["suppressed_note"] = (
                    f"capture is {size['chars']} chars, below the {size['threshold']}-char "
                    f"floor for {doc.doc_type}; likely a landing page rather than the document")

        # Values read out of a document that belongs to a superseded generation are
        # withheld. The Llama case is the precedent: a quote-verified, high-confidence
        # value describing Llama 2's policy under a Llama 4 entry. The quote was real
        # and the extraction was correct; the document was the wrong one, which no
        # confidence score can express.
        for f in fields.values():
            src = f.get("source") or {}
            if src.get("slug") in suppress_slugs.get(provider, {}):
                f["status"] = "not_retrievable"
                f["capture_cause"] = "generation_mismatch"
                f["value"] = ""
                f["citation"] = ""
                f["suppressed_note"] = suppress_slugs[provider][src["slug"]]

        has_stale = False
        for f in fields.values():
            src = f.get("source")
            if src and src.get("slug") in prov:
                src.update(prov[src["slug"]])
                has_stale = has_stale or src.get("stale", False)
        for d in docs_used:
            if d.get("slug") in prov:
                d.update(prov[d["slug"]])

        # Grouping/filter metadata comes from the registry (carried on every doc).
        pdocs = registry.for_provider(provider)
        pd = pdocs[0] if pdocs else None
        openness_val = pd.openness if pd else ""
        segment_val = pd.segment if pd else "hyperscaler"
        # `group` is the DIMENSION-SET group; `section` is where the entry renders.
        # They differ for hosted platforms serving open-weight models, which sit
        # under Open Model Providers but take the hosted-platform term set.
        group = segment_group(segment_val, openness_val, provider)
        section = section_of(provider, segment_val, openness_val)
        seg_cfg = segment_config(provider)

        # Derive the honest four-state display status for every field, overwriting
        # the extractor's binary verified/unverified, and flag any cell whose real
        # content the segment map would drop. Raw extraction files are untouched.
        for dim_key, f in fields.items():
            old_status = f.get("status", "")
            new_status = _derive_status(f, dim_key, group, openness_val)
            warn = _warn_reason(f, dim_key, group, openness_val)
            if new_status != old_status:
                status_report.append(
                    (provider, dim_key, old_status, new_status,
                     (f.get("value", "") or "")[:48], bool(warn))
                )
            if warn:
                excerpt = (f.get("citation", "") or "").strip() or (f.get("value", "") or "").strip()
                warn_rows.append((provider, group, dim_key, new_status, warn, excerpt[:70]))
            f["status"] = new_status
            f["display_value"] = display_value(f)

        lic_field = fields.get("model_license") or {}
        # Annotate permissive-licence silence now that statuses are final.
        _bucket = _license_bucket(lic_field.get("value", ""))
        _apply_licence_silence(fields, _bucket)
        if _bucket == "bespoke/community license":
            _apply_bespoke_silence(fields, provider)
        providers_meta.append(
            {
                "provider": provider,
                "provider_name": provider_names.get(provider, provider),
                "segment": pd.segment if pd else "hyperscaler",
                "group": group,
                "section": section,
                "section_badge": seg_cfg.get("badge", ""),
                "section_basis": " ".join((seg_cfg.get("basis") or "").split()),
                "cross_link": seg_cfg.get("cross_link", ""),
                "parent_company": pd.parent_company if pd else "",
                "openness": pd.openness if pd else "",
                "license_type": _license_bucket(lic_field.get("value", "")),
                "extracted_at": record.get("extracted_at", ""),
                "last_updated": last_updated,
                "has_stale_capture": has_stale,
                "model": record.get("model", ""),
                "documents": docs_used,
                "override_dimensions": record.get("override_dimensions", []),
            }
        )

    _write_status_report(status_report)
    _write_stale_extraction_report(stale_extractions)
    _write_warning_report(warn_rows)

    data_current_as_of = max(
        (p.get("last_updated", "") for p in providers_meta), default=""
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_current_as_of": data_current_as_of,
        "last_checked": read_last_checked(),
        "disclaimer": DISCLAIMER,
        "dimensions": [
            {
                "key": d.key,
                "label": d.label,
                "guidance": d.guidance,
                "group": dimension_group(d.key),
            }
            for d in DIMENSIONS
        ],
        "providers": providers_meta,
        "matrix": matrix,
        "change_log": _build_change_log(registry, store),
    }


WARNING_REPORT_PATH = Path("data/segment_map_warnings.txt")


def _write_warning_report(rows: List[tuple]) -> None:
    """Cells the per-segment map affects that carry real content or an explicit
    'not applicable' — surfaced for review rather than silently dropped (Issue 7)."""
    lines = [
        "Segment-map build warnings (Issue 7) — review, do not ignore.",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"{len(rows)} cell(s) flagged. For each: decide whether to keep the content, "
        "move it to another dimension, adjust the applicability map, or drop it.",
        "",
    ]
    for provider, group, dim, status, reason, excerpt in sorted(rows):
        lines.append(f"  [{group:6s}] {provider:15s} {dim:26s} -> {status}")
        lines.append(f"           {reason}")
        if excerpt:
            lines.append(f"           excerpt: {excerpt!r}")
    WARNING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    WARNING_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


STATUS_REPORT_PATH = Path("data/status_migration_report.txt")


def _write_status_report(rows: List[tuple]) -> None:
    """Write a human-readable record of the status derivation (Issue 2): every field
    whose derived status differs from the extractor's, and every ambiguous default
    flagged for review. Regenerated on each build; lives in the private data dir."""
    from collections import Counter

    counts = Counter(r[3] for r in rows)
    ambiguous = [r for r in rows if r[5]]
    lines = [
        "Status migration report (Issue 2) — build-time derivation, no on-disk change.",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Derived status counts (only fields that changed or were flagged):",
    ]
    lines += [f"  {status:16s} {n}" for status, n in sorted(counts.items())]
    lines += [
        "",
        f"AMBIGUOUS (value said 'not applicable' but rule -> no_clause_found): {len(ambiguous)}",
        "  Review these — they may warrant an explicit not_applicable applicability rule.",
    ]
    for provider, dim, _old, new, value, _amb in ambiguous:
        lines.append(f"    {provider:16s} {dim:28s} -> {new}  ({value!r})")
    lines += ["", "All derivations:"]
    for provider, dim, old, new, value, amb in sorted(rows):
        flag = "  [AMBIGUOUS]" if amb else ""
        lines.append(f"  {provider:16s} {dim:28s} {old or '(none)':12s} -> {new:16s} {value!r}{flag}")

    STATUS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


_COSMETIC_HINTS = (
    "no substantive", "only removed navigation", "only navigation", "navigation link",
    "purely cosmetic", "purely administrative", "only formatting", "formatting change",
    "version stamp", "date stamp", "language selector", "no legal", "cosmetic",
)


def _backfill_substantive(explanation: str) -> bool:
    """Conservative fallback for change notes that predate the substantive flag:
    cosmetic only when the AI summary clearly says so, else substantive."""
    e = (explanation or "").lower()
    return not any(h in e for h in _COSMETIC_HINTS)


def _build_change_log(registry: Registry, store: SnapshotStore) -> List[dict]:
    """Reverse-chronological detected document changes across all documents.
    Each entry: provider, document, date detected, short old/new excerpts, and a
    cached plain-English AI description of the change (if one was generated)."""
    from .change_notes import change_key, load_notes

    notes = load_notes()
    dim_label = {d.key: d.label for d in DIMENSIONS}
    entries: List[dict] = []
    non_text_rows: List[dict] = []
    for doc in registry.documents():
        # Walk the document's own timeline, not our retrieval order. Ordered by
        # fetch time, an archive fallback that re-serves older text reads as a
        # change back to that text, and the feed narrates a fetch event as though
        # the provider had rewritten their terms. That is what produced the
        # reverse-direction OpenAI Business Terms entry.
        history = store.lineage(doc.provider, doc.slug)
        for prev, curr in zip(history, history[1:]):
            # Belt and braces: even within the lineage, never report a transition
            # that moves backwards in content date, and never treat an archive
            # fallback superseding newer live text as a terms change. It is a fetch
            # event, and it belongs in the fetch report rather than the feed.
            if curr.content_date < prev.content_date:
                continue
            if curr.is_archived and not prev.is_archived and curr.content_date <= prev.content_date:
                continue
            # If the tracked source URL changed between snapshots, this is a source
            # swap, not a provider edit of the same document. A text diff across two
            # different documents is meaningless as an "edit", so we flag it and
            # withhold the excerpts rather than present a misleading change.
            source_changed = prev.meta.get("url") != curr.meta.get("url")
            # If either snapshot decoded as non-text (binary/mojibake — e.g. an old
            # Llama capture that predates the fetcher's text check), a diff would
            # render as corrupted garbage. Suppress it rather than show it, and do
            # not attach any AI summary (the model can only describe noise).
            non_text = not source_changed and not (
                looks_like_text(prev.text or "")[0] and looks_like_text(curr.text or "")[0]
            )
            # A source swap compares two different documents; the diff would be
            # both meaningless and expensive (char-level on very long text), so we
            # skip it entirely and only record that the source changed.
            suppressed = source_changed or non_text
            d = None if suppressed else diff_text(prev.text, curr.text)
            if not suppressed and not d.has_changes:
                continue
            entry = {
                "provider": doc.provider,
                "provider_name": doc.provider_name,
                "doc_type": doc.doc_type,
                "slug": doc.slug,
                "document": doc.name,
                "url": curr.meta.get("url", doc.url),
                "detected_at": curr.fetched_at,
                "source_changed": source_changed,
                "non_text": non_text,
                "substantive": True,
                "added_lines": 0 if suppressed else d.added_lines,
                "removed_lines": 0 if suppressed else d.removed_lines,
                "blocks": []
                if suppressed
                else [{"old": b.old_focus, "new": b.new_focus} for b in d.blocks[:5]],
                # Identity of the comparison, and the complete set of changed
                # passages in full. The inline redline shows the first five,
                # windowed; the comparison page shows every changed passage whole,
                # which is what "view the full comparison" needs.
                "compare_id": f"{doc.provider}-{doc.slug}-{curr.stamp}",
                "prev_stamp": prev.stamp,
                "curr_stamp": curr.stamp,
                "all_blocks": []
                if suppressed
                else [{"old": b.old, "new": b.new} for b in d.blocks],
                # Per-document switch. Hides the full-text version pages while the
                # redline, hashes and Internet Archive links stay: verification does
                # not depend on us hosting the text.
                "versions_suppressed": bool(getattr(doc, "versions_suppressed", False)),
                # Independent corroboration, looked up around the change's own
                # content date rather than the fetch date.
                "wayback_before": None if suppressed else _wayback(
                    curr.meta.get("url", doc.url), prev.content_date, "before"),
                "wayback_after": None if suppressed else _wayback(
                    curr.meta.get("url", doc.url), curr.content_date, "after"),
            }
            if source_changed:
                # A hand-written curation note takes precedence over the generic
                # wording, because for a curation decision the generic phrasing can
                # be misread as the provider having changed their terms.
                cur_note = _curation_note(doc.provider, doc.slug, curr.meta.get("url", ""))
                if cur_note:
                    entry["note"] = cur_note["note"]
                    entry["curation"] = True
                    entry["substantive"] = bool(cur_note.get("substantive"))
                else:
                    entry["note"] = (
                        "Tracked source document changed; not an edit of the same document."
                    )
            elif non_text:
                entry["note"] = NON_TEXT_MESSAGE
            else:
                note = notes.get(change_key(doc.provider, doc.slug, prev.stamp, curr.stamp))
                if note:
                    entry["ai_explanation"] = note.get("explanation", "")
                    entry["dimensions"] = [
                        {"key": k, "label": dim_label.get(k, k)}
                        for k in note.get("dimensions", [])
                        if k in dim_label
                    ]
                    entry["substantive"] = note.get(
                        "substantive", _backfill_substantive(note.get("explanation", "")))
            # A non-text diff is a fetch defect, not a change to anyone's terms. It
            # tells a reader nothing, so it never reaches the public feed. It is
            # recorded in an internal report instead, and the change re-enters the
            # feed normally once a clean re-fetch produces a readable diff.
            if non_text:
                non_text_rows.append({
                    "provider": doc.provider,
                    "provider_name": doc.provider_name,
                    "document": doc.name,
                    "doc_type": doc.doc_type,
                    "slug": doc.slug,
                    "url": curr.meta.get("url", doc.url),
                    "prev_stamp": prev.stamp,
                    "curr_stamp": curr.stamp,
                    "detected_at": curr.fetched_at,
                    "fetch_method": curr.meta.get("fetch_method", ""),
                    "prev_stats": looks_like_text(prev.text or "")[1],
                    "curr_stats": looks_like_text(curr.text or "")[1],
                })
                continue
            entries.append(entry)
    _write_non_text_report(non_text_rows)
    # Standalone curation events. An entry split moves documents between providers
    # while their URLs stay the same, so no snapshot comparison would ever surface
    # it; without this the reorganization would be invisible in the feed.
    for ev in _curation_events():
        provider_name = next(
            (d.provider_name for d in registry.documents() if d.provider == ev.get("provider")),
            ev.get("provider", ""))
        entries.append({
            "provider": ev.get("provider", ""),
            "provider_name": provider_name,
            "doc_type": ev.get("doc_type", ""),
            "slug": ev.get("doc_type", ""),
            "document": ev.get("document", ""),
            "url": ev.get("url", ""),
            "detected_at": f"{ev.get('date')}T00:00:00+00:00",
            "source_changed": False,
            "non_text": False,
            "substantive": False,
            "curation": True,
            "note": ev.get("note", ""),
            "added_lines": 0, "removed_lines": 0, "blocks": [], "all_blocks": [],
            "compare_id": "", "prev_stamp": "", "curr_stamp": "",
        })

    entries.sort(key=lambda e: e["detected_at"], reverse=True)
    return entries


def _wayback(url, when, direction):
    """Internet Archive corroboration link, or None. Never fails the build."""
    if os.environ.get("CTO_SKIP_WAYBACK"):
        return None
    try:
        from .wayback import nearest_capture
        return nearest_capture(url, when, direction)
    except Exception:  # noqa: BLE001
        return None


_LICENCE_SILENCE_CACHE = None


def _licence_silence():
    """Config explaining why a standard permissive licence is silent on a point."""
    global _LICENCE_SILENCE_CACHE
    if _LICENCE_SILENCE_CACHE is None:
        try:
            _LICENCE_SILENCE_CACHE = yaml.safe_load(
                Path("licence_silence.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            _LICENCE_SILENCE_CACHE = {}
    return _LICENCE_SILENCE_CACHE


def _apply_bespoke_silence(fields: dict, provider: str) -> None:
    """Name the bespoke licence, but keep calling the silence what it is.

    The mirror image of the permissive case. A publisher who wrote its own licence
    chose that licence's scope, so a point it omits is a finding about the terms,
    not a limit of the instrument. The badge stays "silent" and no structural
    reason is offered, because there is none to give: only the licence is named.
    """
    cfg = (_licence_silence().get("bespoke") or {})
    name = (cfg.get("names") or {}).get(provider)
    if not name:
        return
    reason = " ".join((cfg.get("reason") or "").split())
    note = " ".join((cfg.get("note") or "").split())
    for f in fields.values():
        if not f or f.get("status") != "no_clause_found":
            continue
        f["licence_silence"] = {
            "form": name,
            "reason": reason,
            "instrument": note,
            "bespoke": True,
        }


def _apply_licence_silence(fields: dict, licence_bucket: str) -> None:
    """Replace bare 'silent' with the licence name and the specific reason.

    Only for standard OSI forms. A bespoke community licence that is silent on a
    point IS making a choice, and flattening that into the same label as a bare
    MIT file would lose the distinction the open-weight segment exists to show.
    """
    cfg = _licence_silence()
    form = (cfg.get("forms") or {}).get(licence_bucket)
    if not form:
        return
    reasons = cfg.get("reasons") or {}
    # A form whose text contradicts the general reason overrides it. Apache-2.0
    # does contain a termination provision (patent retaliation, section 3), so the
    # general "contains no termination provision" must not be used for it.
    overrides = (cfg.get("overrides") or {}).get(form) or {}
    instrument = (cfg.get("instrument") or {}).get(form, "")
    for key, f in fields.items():
        if not f or f.get("status") != "no_clause_found":
            continue
        reason = overrides.get(key) or reasons.get(key)
        if not reason:
            continue
        reason = " ".join(reason.split())
        f["licence_silence"] = {
            "form": form,
            "reason": reason,
            "instrument": " ".join(instrument.split()),
        }


_CURATION_NOTES_CACHE = None
_CURATION_EVENTS_CACHE = None


def _curation_events():
    """Standalone curation events, not tied to any document diff."""
    global _CURATION_EVENTS_CACHE
    if _CURATION_EVENTS_CACHE is None:
        try:
            raw = yaml.safe_load(Path("curation_notes.yaml").read_text(encoding="utf-8")) or {}
            _CURATION_EVENTS_CACHE = raw.get("events", []) or []
        except (OSError, ValueError):
            _CURATION_EVENTS_CACHE = []
    return _CURATION_EVENTS_CACHE


def _curation_note(provider: str, slug: str, to_url: str):
    """Hand-written change-feed text for a specific Observatory curation decision.

    Matched on provider + slug + the URL being moved to, so a note fires once for
    the transition it describes and not for every later change to that document.
    """
    global _CURATION_NOTES_CACHE
    if _CURATION_NOTES_CACHE is None:
        p = Path("curation_notes.yaml")
        try:
            import yaml
            _CURATION_NOTES_CACHE = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("notes", [])
        except (OSError, ValueError, ImportError):
            _CURATION_NOTES_CACHE = []
    for n in _CURATION_NOTES_CACHE:
        if (n.get("provider") == provider and n.get("slug") == slug
                and n.get("to_url") == to_url):
            return n
    return None


STALE_EXTRACTION_REPORT_PATH = Path("data/stale-extractions.json")


def _write_stale_extraction_report(rows: List[dict]) -> None:
    """Documents whose current text is newer than the text their values were read
    from, so the matrix is lagging the corpus.

    Compares CONTENT recency, not fetch recency. A check on fetch time would fire
    on the opposite case (an archive fallback retrieved after a live capture) and
    would have pointed the wrong way on the OpenAI Business Terms.
    """
    STALE_EXTRACTION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STALE_EXTRACTION_REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "note": ("Extracted values cite a capture older than the document's current "
                 "text. Re-extract the provider to bring the matrix in step; until "
                 "then the matrix can disagree with the change feed."),
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


GENERATION_REPORT_PATH = Path("data/generation-mismatches.json")


def _write_generation_report(findings) -> None:
    """Internal record of every generation mismatch, in both directions.

    Suppressions are visible on the site as withheld values, but the newer-generation
    findings are not visible anywhere else: they mean the registry is behind and a
    curation decision is due.
    """
    GENERATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATION_REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(findings),
        "note": ("Documents whose text names a different model generation than the "
                 "registry entry tracks. 'older' suppresses the values; 'newer' means "
                 "the registry needs updating and is not a data defect."),
        "findings": [{
            "provider": f.provider, "slug": f.slug, "declared": f.declared,
            "found_in_text": f.found, "direction": f.direction,
            "mentions": f.mentions, "action": f.action,
        } for f in findings],
    }, indent=2, ensure_ascii=False), encoding="utf-8")


NON_TEXT_REPORT_PATH = Path("data/non-text-fetches.json")


def _write_non_text_report(rows: List[dict]) -> None:
    """Internal report of captures that decoded as non-text.

    These are withheld from the public change feed (they describe a broken fetch,
    not a change to a provider's terms). The report is the record that they
    happened, and the input to the GitHub issue raised in the private data repo:
    see `python main.py report-fetch-issues`.
    """
    NON_TEXT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    NON_TEXT_REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "note": ("Captures that decoded as non-text (binary, compressed, or wrong "
                 "charset). Withheld from the public change feed; each needs a clean "
                 "re-fetch before its change can be reported."),
        "rows": rows,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def save_dataset(dataset: dict, path: str | Path = "data/dataset.json") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Scope-clause sweep (governing-document rule, mechanical half)
#
# A governing document usually declares its own scope in its opening paragraph.
# When that declaration describes an operated service and the document sits on an
# entry tracking downloadable weights, the two disagree and someone should look.
#
# FLAGS ONLY. Scope language is drafted for the publisher's purposes and is often
# broader or narrower than the artifact at hand, so a disagreement is a prompt,
# never a finding. Nothing here suppresses a value or edits the registry.
# ---------------------------------------------------------------------------

SCOPE_REPORT_PATH = Path("data/scope_flags.json")

_ENTRY_CLASS_BY_SECTION = None


def _entry_class(section: str) -> str:
    global _ENTRY_CLASS_BY_SECTION
    if _ENTRY_CLASS_BY_SECTION is None:
        try:
            cfg = yaml.safe_load(
                Path("entry_classes.yaml").read_text(encoding="utf-8")) or {}
            _ENTRY_CLASS_BY_SECTION = cfg.get("sections") or {}
        except (OSError, ValueError):
            _ENTRY_CLASS_BY_SECTION = {}
    return _ENTRY_CLASS_BY_SECTION.get(section or "", "")


def _scope_sweep(registry, store) -> List[dict]:
    findings = []
    for doc in registry.fetchable():
        # Same resolution the renderer uses, so the class a document is judged
        # against is the class the reader sees it filed under.
        section = section_of(doc.provider, doc.segment, doc.openness)
        cls = _entry_class(section)
        if not cls:
            continue
        snap = store.current(doc.provider, doc.slug)
        if not snap or not snap.text:
            continue
        flag = scope_check(snap.text, cls, doc.doc_type)
        if flag:
            flag.update({"provider": doc.provider, "doc_type": doc.doc_type,
                         "entry_class": cls, "url": doc.url, "name": doc.name})
            findings.append(flag)
    return findings


def _write_scope_report(findings: List[dict]) -> None:
    SCOPE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCOPE_REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(findings),
        "note": ("Documents whose own scope statement describes a different kind of "
                 "thing than the entry they sit on tracks. Flags for review, not "
                 "findings: nothing is suppressed and no status changes. A document "
                 "that declares no scope is not flagged, because absence of evidence "
                 "is not disagreement."),
        "findings": findings,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    if findings:
        print(f"  scope flags: {len(findings)} document(s) disagree with their "
              f"entry class -> {SCOPE_REPORT_PATH}")
