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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .differ import diff_text
from .extractor import load_extraction
from .overrides import apply_overrides, load_overrides
from .registry import Registry, load_registry
from .schema import DIMENSIONS, dimension_group, is_applicable, segment_group
from .snapshot import SnapshotStore
from .textcheck import NON_TEXT_MESSAGE, looks_like_text

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

STATUSES = ("quote_verified", "quote_unverified", "no_clause_found", "not_applicable")

# Issue 3: absence is shown with exactly two display labels, regardless of the raw
# vocabulary the model used ("not specified", "none", "no", "n/a", ...).
_ABSENCE_DISPLAY = {"no_clause_found": "silent", "not_applicable": "not applicable"}


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
            snap = store.latest(provider, doc.slug)
            if snap:
                fm = snap.meta.get("fetch_method", "direct")
                cap = snap.meta.get("capture_timestamp", "")
                prov[doc.slug] = {
                    "fetch_method": fm,
                    "capture_timestamp": cap,
                    "stale": fm == "wayback" and _capture_stale(cap),
                }
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
        group = segment_group(segment_val, openness_val)

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
        providers_meta.append(
            {
                "provider": provider,
                "provider_name": provider_names.get(provider, provider),
                "segment": pd.segment if pd else "hyperscaler",
                "group": group,
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
    for doc in registry.documents():
        history = store.history(doc.provider, doc.slug)
        for prev, curr in zip(history, history[1:]):
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
            }
            if source_changed:
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
            entries.append(entry)
    entries.sort(key=lambda e: e["detected_at"], reverse=True)
    return entries


def save_dataset(dataset: dict, path: str | Path = "data/dataset.json") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
