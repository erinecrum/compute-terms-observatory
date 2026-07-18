"""Human-verified override layer.

The extraction JSON is the raw model output — it is regenerated wholesale every
time we re-extract. Corrections must therefore live somewhere the re-run cannot
clobber. They live in `overrides/<provider>.yaml`, keyed by dimension, and are
layered on top of the raw extraction when the dataset is built. Because they sit
in their own files, they survive re-extraction by construction.

An override marks the field `human_verified: true` and records who/why via a
note, so the site can show that a value was checked by a human rather than only
produced by the model.

Override file shape:

    overrides:
      governing_law_disputes:
        value: "Governing law: Washington State; venue King County; no arbitration"
        citation: "GOVERNING LAW"                 # optional
        citation_document: customer_agreement     # optional: slug of the cited doc
        confidence: high                            # optional; defaults to 'high'
        note: "Verified by counsel 2026-07-14 against the AWS Customer Agreement."
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml


def overrides_dir() -> Path:
    return Path("overrides")


def load_overrides(provider: str) -> Dict[str, dict]:
    path = overrides_dir() / f"{provider}.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("overrides", {}) or {}


def _source_for_slug(record: dict, slug: Optional[str]) -> Optional[dict]:
    if not slug:
        return None
    for d in record.get("documents_used", []):
        if d.get("slug") == slug:
            return {
                "slug": d["slug"],
                "doc_type": d["doc_type"],
                "name": d["name"],
                "url": d["url"],
                "fetched_at": d["fetched_at"],
                "text_sha256": d["text_sha256"],
            }
    return None


def apply_overrides(record: dict, overrides: Dict[str, dict]) -> dict:
    """Return a copy of the extraction record with human overrides layered in.
    Non-destructive: the raw extraction file on disk is untouched."""
    if not overrides:
        return record

    merged = {**record, "fields": {k: dict(v) for k, v in record["fields"].items()}}
    applied = []
    for dim, ov in overrides.items():
        if dim not in merged["fields"]:
            continue  # unknown dimension key — ignore rather than fabricate a row
        field = merged["fields"][dim]
        field["value"] = ov.get("value", field["value"])
        field["citation"] = ov.get("citation", field.get("citation", ""))
        field["confidence"] = ov.get("confidence", "high")
        cited_slug = ov.get("citation_document")
        if cited_slug:
            field["citation_document"] = cited_slug
            src = _source_for_slug(record, cited_slug)
            if src:
                field["source"] = src
        field["human_verified"] = True
        field["status"] = "verified"  # a human override is authoritative
        field["override_note"] = ov.get("note", "")
        applied.append(dim)

    merged["human_verified_dimensions"] = applied
    return merged
