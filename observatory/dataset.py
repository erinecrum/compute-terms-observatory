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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .differ import diff_text
from .extractor import load_extraction
from .overrides import apply_overrides, load_overrides
from .registry import Registry, load_registry
from .schema import DIMENSIONS
from .snapshot import SnapshotStore

DISCLAIMER = (
    "This is an informational comparison of published documents, not legal advice. "
    "It describes what public documents say, with citations. Provider documents "
    "change and automated extraction can be wrong or stale — always review the "
    "current source documents yourself."
)


def load_commitment_programs(path: str | Path = "commitment_programs.yaml") -> Dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {prog["provider"]: prog for prog in raw.get("programs", [])}


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
        providers_meta.append(
            {
                "provider": provider,
                "provider_name": provider_names.get(provider, provider),
                "extracted_at": record.get("extracted_at", ""),
                "model": record.get("model", ""),
                "documents": record.get("documents_used", []),
                "human_verified_dimensions": record.get("human_verified_dimensions", []),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "dimensions": [{"key": d.key, "label": d.label, "guidance": d.guidance} for d in DIMENSIONS],
        "providers": providers_meta,
        "matrix": matrix,
        "change_log": _build_change_log(registry, store),
    }


def _build_change_log(registry: Registry, store: SnapshotStore) -> List[dict]:
    """Reverse-chronological detected document changes across all documents.
    Each entry: provider, document, date detected, short old/new excerpts."""
    entries: List[dict] = []
    for doc in registry.documents():
        history = store.history(doc.provider, doc.slug)
        for prev, curr in zip(history, history[1:]):
            d = diff_text(prev.text, curr.text)
            if not d.has_changes:
                continue
            entries.append(
                {
                    "provider": doc.provider,
                    "provider_name": doc.provider_name,
                    "doc_type": doc.doc_type,
                    "slug": doc.slug,
                    "document": doc.name,
                    "url": doc.url,
                    "detected_at": curr.fetched_at,
                    "added_lines": d.added_lines,
                    "removed_lines": d.removed_lines,
                    "blocks": [
                        {"old": b.old_focus, "new": b.new_focus} for b in d.blocks[:5]
                    ],
                }
            )
    entries.sort(key=lambda e: e["detected_at"], reverse=True)
    return entries


def save_dataset(dataset: dict, path: str | Path = "data/dataset.json") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
