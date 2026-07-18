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
from .schema import DIMENSIONS
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
        lic_field = fields.get("model_license") or {}
        providers_meta.append(
            {
                "provider": provider,
                "provider_name": provider_names.get(provider, provider),
                "segment": pd.segment if pd else "hyperscaler",
                "parent_company": pd.parent_company if pd else "",
                "openness": pd.openness if pd else "",
                "license_type": _license_bucket(lic_field.get("value", "")),
                "extracted_at": record.get("extracted_at", ""),
                "last_updated": last_updated,
                "has_stale_capture": has_stale,
                "model": record.get("model", ""),
                "documents": docs_used,
                "human_verified_dimensions": record.get("human_verified_dimensions", []),
            }
        )

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
                "group": "Service level (SLA) terms"
                if d.key in _SLA_DIMS
                else "General contract terms",
            }
            for d in DIMENSIONS
        ],
        "providers": providers_meta,
        "matrix": matrix,
        "change_log": _build_change_log(registry, store),
    }


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
            entries.append(entry)
    entries.sort(key=lambda e: e["detected_at"], reverse=True)
    return entries


def save_dataset(dataset: dict, path: str | Path = "data/dataset.json") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
