"""Turn an absence status into a sentence that says what was reviewed.

No cell displays a bare status word. "Silent" reads as a judgment about the
provider, "not applicable" as a gap in our coverage, "not retrievable" as
something broken. In each case the accurate statement is narrower and checkable:
which documents were reviewed, and why no term is reported.

Sentences are ASSEMBLED, never free-drafted per cell: a template from
absence_language.yaml plus that cell's own facts. Editing the wording is a config
change; nothing here writes prose.

Every state yields both a full sentence (drawer, provider pages, exports) and a
compact clause (dense matrix cells). The compact form is shortened, but it is
still a clause and never a code word.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

_CFG = None

# How many document names to name before collapsing to "and N others".
_NAME_LIMIT = 1


def _cfg() -> dict:
    global _CFG
    if _CFG is None:
        try:
            _CFG = yaml.safe_load(
                Path("absence_language.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            _CFG = {}
    return _CFG


def _fill(text: str, **facts) -> str:
    try:
        return " ".join(str(text).format(**facts).split())
    except (KeyError, IndexError):
        return " ".join(str(text).split())


def documents_phrase(names: list) -> str:
    """'the Anthropic Commercial Terms of Service and 4 other governing documents'."""
    names = [n for n in (names or []) if n]
    if not names:
        return "the registered documents"
    if len(names) <= _NAME_LIMIT:
        return names[0] if len(names) == 1 else " and ".join(names)
    rest = len(names) - _NAME_LIMIT
    plural = "s" if rest != 1 else ""
    return (f"{names[0]} and {rest} other governing document{plural}")


def entry_class_name(entry_class: str) -> str:
    return (_cfg().get("entry_class_names") or {}).get(
        entry_class, "this kind of entry")


def sentence(field: dict, *, documents: list = None, entry_class: str = "",
             reason: str = "", generation: str = "") -> Optional[dict]:
    """Full and compact renderings for an absence cell, or None if it has a value.

    `documents` are the governing documents reviewed for this entry; `reason` is
    the applicability reason from the segment map; `generation` is what a
    superseded capture actually describes.
    """
    status = (field or {}).get("status", "")
    templates = _cfg().get("templates") or {}
    spec = templates.get(status)
    if not spec:
        return None

    facts = {
        "documents": documents_phrase(documents),
        "document": (documents or ["the registered document"])[0]
        if documents else "the registered document",
        "entry_class": entry_class_name(entry_class),
        "reason": reason or spec.get("fallback_reason", ""),
        "generation": generation or "another generation",
        "mechanism": field.get("capture_mechanism", ""),
        "n_documents": len(documents or []),
    }

    if status == "no_clause_found":
        # Language in the area but no clear term is not silence, and says so.
        if field.get("citation") and spec.get("ambiguous"):
            spec = spec["ambiguous"]
        elif len(documents or []) == 1 and spec.get("compact_one"):
            spec = dict(spec, compact=spec["compact_one"])
    elif status == "access_restricted":
        if not facts["mechanism"] and spec.get("no_mechanism"):
            spec = spec["no_mechanism"]
    elif status == "not_retrievable":
        cause = field.get("capture_cause") or ""
        spec = (spec.get("causes") or {}).get(cause) or spec.get("default") or {}

    full, compact = spec.get("full", ""), spec.get("compact", "")
    if not full:
        return None
    return {
        "full": _fill(full, **facts),
        "compact": _fill(compact or full, **facts),
        "documents_reviewed": list(documents or []),
    }
