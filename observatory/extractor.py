"""Extraction layer: a Claude API pass that reads a provider's archived documents
and returns the 10-dimension term schema as structured JSON.

Design principle 4 (everything traceable) is enforced here: every extracted field
is stitched to the exact document it was cited from — its public URL, fetch date,
and text version hash — so no value floats free of its source. Values the model
cannot support are returned as "not specified"/"unclear" with low confidence; the
model is instructed never to guess.

The model is pinned to Opus 4.8 and forced through a tool schema so the output is
always schema-conformant JSON (one record per dimension).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .registry import Registry
from .schema import DIMENSION_KEYS, DIMENSIONS
from .snapshot import SnapshotStore

MODEL = "claude-opus-4-8"

# Per-provider input budget. Opus handles a large context; this caps cost and
# keeps the rare oversized corpus (e.g. Crusoe's whole legal center) in bounds.
# Documents are included in relevance order; an overflowing document is truncated
# and the truncation is recorded so the reviewing attorney knows the input was
# incomplete rather than being misled by a confident "not specified".
MAX_TOTAL_CHARS = 600_000

# Order in which a provider's documents are packed into the corpus.
_DOC_PRIORITY = ["sla", "service_terms", "ai_terms", "aup"]

CONFIDENCE_LEVELS = ["high", "medium", "low"]


def _clip_citation(s: str, max_words: int = 14) -> str:
    """Hard rule: quoted excerpts stay under 15 words. Clip an over-long citation
    rather than reproduce a long passage."""
    words = s.split()
    return s if len(words) <= max_words else " ".join(words[:max_words]) + "…"


@dataclass
class DocSource:
    slug: str
    doc_type: str
    name: str
    url: str
    fetched_at: str
    text_sha256: str
    text: str
    included_chars: int
    truncated: bool


def _gather_sources(provider: str, registry: Registry, store: SnapshotStore) -> List[DocSource]:
    """Latest snapshot per document for a provider, packed to the char budget in
    relevance order (by doc_type), with truncation recorded honestly. Keyed by
    slug so a provider can have multiple documents of one doc_type."""
    def priority(doc):
        return (
            _DOC_PRIORITY.index(doc.doc_type)
            if doc.doc_type in _DOC_PRIORITY
            else len(_DOC_PRIORITY)
        )

    # Only fetchable documents feed extraction. Gap entries (not_published /
    # within_service_terms) have no URL; skipping them also prevents an orphaned
    # snapshot under a reused slug from leaking into a provider's extraction.
    ordered = sorted(
        [d for d in registry.for_provider(provider) if d.is_fetchable], key=priority
    )

    sources: List[DocSource] = []
    remaining = MAX_TOTAL_CHARS
    for doc in ordered:
        snap = store.latest(provider, doc.slug)
        if snap is None or not snap.text:
            continue
        full = snap.text
        if len(full) <= remaining:
            included, truncated = full, False
        else:
            included, truncated = full[:remaining], True
        sources.append(
            DocSource(
                slug=doc.slug,
                doc_type=doc.doc_type,
                name=doc.name,
                url=doc.url,
                fetched_at=snap.fetched_at,
                text_sha256=snap.text_sha256,
                text=included,
                included_chars=len(included),
                truncated=truncated,
            )
        )
        remaining -= len(included)
        if remaining <= 0:
            break
    return sources


def _corpus(sources: List[DocSource]) -> str:
    parts = []
    for s in sources:
        header = (
            f"\n===== DOCUMENT: {s.name} "
            f"(id={s.slug}; doc_type={s.doc_type}; url={s.url}"
            f"{'; TRUNCATED' if s.truncated else ''}) =====\n"
        )
        parts.append(header + s.text)
    return "\n".join(parts)


def _tool_schema(available_slugs: List[str]) -> dict:
    return {
        "name": "record_extraction",
        "description": "Record the extracted term schema, one entry per dimension.",
        "input_schema": {
            "type": "object",
            "properties": {
                "extractions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string", "enum": DIMENSION_KEYS},
                            "value": {
                                "type": "string",
                                "description": "Categorical or short structured text. "
                                "Use 'not specified' or 'unclear' if unsupported.",
                            },
                            "confidence": {"type": "string", "enum": CONFIDENCE_LEVELS},
                            "citation": {
                                "type": "string",
                                "description": "Section heading or a quoted anchor "
                                "UNDER 15 words. Empty if not found.",
                            },
                            "citation_document": {
                                "type": "string",
                                "enum": available_slugs + ["none"],
                                "description": "Which document (by id) the citation is from.",
                            },
                        },
                        "required": [
                            "dimension",
                            "value",
                            "confidence",
                            "citation",
                            "citation_document",
                        ],
                    },
                }
            },
            "required": ["extractions"],
        },
    }


_SYSTEM = (
    "You are a careful legal-document analyst building an informational comparison "
    "of PUBLISHED cloud/GPU compute provider terms. You describe only what the "
    "documents say. You never give advice, never rate providers, and never guess. "
    "If a document does not support a value, return 'not specified' or 'unclear' "
    "with low confidence and an empty citation. Every citation must be a real "
    "section heading or a quoted anchor UNDER 15 words taken from the provided "
    "text, and citation_document must be the document it came from."
)


def _prompt(provider_name: str, sources: List[DocSource]) -> str:
    lines = [
        f"Provider: {provider_name}",
        "",
        "Extract EACH of the following dimensions (return exactly one entry per "
        "dimension, using the dimension key):",
        "",
    ]
    for d in DIMENSIONS:
        lines.append(f"- {d.key} ({d.label}): {d.guidance}")
    truncated = [s.doc_type for s in sources if s.truncated]
    if truncated:
        lines += [
            "",
            f"NOTE: these documents were truncated for length and may be "
            f"incomplete: {', '.join(truncated)}. If a dimension's answer would "
            f"depend on text that may lie beyond the truncation, prefer 'unclear'.",
        ]
    lines += ["", "The provider's documents follow.", _corpus(sources)]
    return "\n".join(lines)


def _client():
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return Anthropic()


def extract_provider(
    provider: str, registry: Registry, store: SnapshotStore
) -> dict:
    """Run the schema extraction for one provider and return a provenance-stitched
    record. Does not write to disk (the caller decides where)."""
    provider_name = registry.provider_names().get(provider, provider)
    sources = _gather_sources(provider, registry, store)
    if not sources:
        raise RuntimeError(f"{provider}: no snapshot text available to extract from")

    available_slugs = [s.slug for s in sources]
    source_index: Dict[str, DocSource] = {s.slug: s for s in sources}

    client = _client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=_SYSTEM,
        tools=[_tool_schema(available_slugs)],
        tool_choice={"type": "tool", "name": "record_extraction"},
        messages=[{"role": "user", "content": _prompt(provider_name, sources)}],
    )

    tool_input = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            tool_input = block.input
            break
    if tool_input is None:
        raise RuntimeError(f"{provider}: model did not return a tool_use block")

    by_dim = {e["dimension"]: e for e in tool_input.get("extractions", [])}

    fields = {}
    for key in DIMENSION_KEYS:
        e = by_dim.get(key)
        if e is None:
            # Model omitted a dimension — record it explicitly rather than silently.
            fields[key] = {
                "value": "not specified",
                "confidence": "low",
                "citation": "",
                "citation_document": "none",
                "source": None,
                "human_verified": False,
            }
            continue
        cited = e.get("citation_document", "none")
        src = source_index.get(cited)
        fields[key] = {
            "value": e.get("value", "").strip(),
            "confidence": e.get("confidence", "low"),
            "citation": _clip_citation(e.get("citation", "").strip()),
            "citation_document": cited,
            # Provenance: the exact source this value is anchored to.
            "source": None
            if src is None
            else {
                "slug": src.slug,
                "doc_type": src.doc_type,
                "name": src.name,
                "url": src.url,
                "fetched_at": src.fetched_at,
                "text_sha256": src.text_sha256,
            },
            "human_verified": False,
        }

    return {
        "provider": provider,
        "provider_name": provider_name,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "documents_used": [
            {
                "slug": s.slug,
                "doc_type": s.doc_type,
                "name": s.name,
                "url": s.url,
                "fetched_at": s.fetched_at,
                "text_sha256": s.text_sha256,
                "included_chars": s.included_chars,
                "truncated": s.truncated,
            }
            for s in sources
        ],
        "fields": fields,
    }


def extractions_dir() -> Path:
    return Path("data/extractions")


def save_extraction(record: dict) -> Path:
    d = extractions_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{record['provider']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_extraction(provider: str) -> Optional[dict]:
    path = extractions_dir() / f"{provider}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
