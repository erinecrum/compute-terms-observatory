"""Core data shapes shared across the pipeline.

The whole pipeline speaks in two types:

* `Document` — one entry from the source registry (a provider's terms page, an
  SLA, an AUP, etc.). This is *what to fetch*, loaded from `registry.yaml`.
* `FetchResult` — the normalized output of fetching one `Document`. This is the
  only shape the snapshot store, differ, and extractor ever see.

Adding a provider means adding registry entries (Documents), never new code —
the fetcher is generic over any public HTML URL.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Document types we recognize. Kept as plain strings (not an enum) so the
# registry can introduce a new type without a code change; these are the
# canonical spellings used for snapshot paths and the comparison schema.
DOC_TYPES = (
    "service_terms",   # general service terms / customer agreement
    "sla",             # service level agreement (compute/GPU prioritized)
    "aup",             # acceptable use policy
    "ai_terms",        # AI-specific or GPU-specific service terms
)


@dataclass
class Document:
    """One registry entry: a single public document to archive and compare."""

    provider: str          # stable slug, e.g. "aws" (used in snapshot paths)
    provider_name: str     # human-readable, e.g. "Amazon Web Services"
    doc_type: str          # one of DOC_TYPES
    name: str              # human-readable document name for citations
    url: str               # public URL (no login-gated content, ever)
    notes: str = ""        # e.g. "compute SLA; GPU instances covered here"

    @property
    def doc_id(self) -> str:
        """Stable identifier used for snapshot directories and dataset keys."""
        return f"{self.provider}/{self.doc_type}"


@dataclass
class FetchResult:
    """Normalized output of fetching one Document. The only shape the rest of
    the pipeline understands."""

    provider: str
    provider_name: str
    doc_type: str
    name: str
    url: str

    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    http_status: Optional[int] = None
    ok: bool = True
    error: str = ""

    # The archival payload: raw HTML exactly as served (the corpus asset) plus a
    # normalized, line-oriented text rendering used for diffing and extraction.
    raw_html: Optional[str] = None
    text: Optional[str] = None

    # Integrity / change-detection fingerprints.
    text_sha256: str = ""   # hash of normalized text — the change signal we diff
    raw_sha256: str = ""     # hash of raw bytes — archival integrity of the source
    char_count: int = 0

    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return f"{self.provider}/{self.doc_type}"


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
