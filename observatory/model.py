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
    "service_terms",   # general service / API / customer agreement terms
    "sla",             # service level agreement (compute/GPU prioritized)
    "aup",             # acceptable use / usage policy
    "ai_terms",        # AI-specific or GPU-specific service terms
    "model_license",   # open-weight model license (per generation)
    "deprecation",     # model deprecation / version-pinning policy
)

# Provider segments (the two top-level site sections + their subgroups).
SEGMENTS = ("hyperscaler", "neocloud", "model_provider")
# Openness applies to model_provider family entries only.
OPENNESS = ("closed_api", "open_weight")
# Fetch tiers, tried in order of preference per source.
FETCH_METHODS = ("direct", "browser", "wayback")


@dataclass
class Document:
    """One registry entry: a single public document to archive and compare."""

    provider: str          # stable slug; for model families this is the family
                           # slug, e.g. "aws", "claude", "gpt-oss" (snapshot path)
    provider_name: str     # human-readable, e.g. "Amazon Web Services", "Claude"
    doc_type: str          # one of DOC_TYPES — the schema/comparison category
    name: str              # human-readable document name for citations
    url: str = ""          # public URL (empty when the document has no standalone URL)
    slug: str = ""         # storage key, unique per provider; defaults to doc_type
    notes: str = ""        # e.g. "compute SLA; GPU instances covered here"
    # Site grouping / entry metadata (carried on every doc of a provider):
    segment: str = "hyperscaler"   # one of SEGMENTS
    parent_company: str = ""       # for model families, e.g. "Anthropic", "Google"
    openness: str = ""             # for model families: closed_api | open_weight
    generation: str = ""           # model generation a license/doc pins to, e.g. "GLM-5.2"
    # Fetch tier for THIS source: direct (default), browser (Playwright), or
    # wayback (Internet Archive fallback). See observatory/fetcher.py.
    fetch_method: str = "direct"
    # Honest coverage status. Only 'verified' documents are fetched; the rest
    # record a gap so we never guess a URL:
    #   verified            — confirmed to resolve to the right document (has url)
    #   unverified          — url present but not yet confirmed this pass
    #   not_published       — no such public document/commitment exists (no url)
    #   within_service_terms— content is only a section of the provider's Terms
    #                         (no separate URL); extracted from service_terms
    status: str = "verified"

    def __post_init__(self):
        # A provider can have several documents of one doc_type (e.g. two SLAs, or
        # Service Terms + a master Customer Agreement). The slug disambiguates
        # them in storage; doc_type stays the comparison category.
        if not self.slug:
            self.slug = self.doc_type

    @property
    def is_fetchable(self) -> bool:
        return bool(self.url) and self.status in ("verified", "unverified")

    @property
    def doc_id(self) -> str:
        """Stable identifier used for snapshot directories and dataset keys."""
        return f"{self.provider}/{self.slug}"


@dataclass
class FetchResult:
    """Normalized output of fetching one Document. The only shape the rest of
    the pipeline understands."""

    provider: str
    provider_name: str
    doc_type: str
    name: str
    url: str
    slug: str = ""  # storage key (defaults to doc_type); set from the Document

    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    http_status: Optional[int] = None
    ok: bool = True
    error: str = ""
    # Which fetch tier actually produced this snapshot, and for the wayback tier
    # the Internet Archive capture time (so the version is dated by CAPTURE, not
    # by our fetch time).
    fetch_method: str = "direct"
    capture_timestamp: str = ""  # wayback capture time (UTC ISO), else ""

    # The archival payload: the raw document exactly as served (the corpus asset)
    # plus a normalized, line-oriented text rendering used for diffing/extraction.
    # HTML sources populate raw_html; binary sources (PDF) populate raw_bytes.
    raw_html: Optional[str] = None
    raw_bytes: Optional[bytes] = None
    raw_ext: str = "html"    # archival file extension: "html" | "pdf"
    text: Optional[str] = None

    # Integrity / change-detection fingerprints.
    text_sha256: str = ""   # hash of normalized text — the change signal we diff
    raw_sha256: str = ""     # hash of the raw document — archival integrity
    char_count: int = 0

    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return f"{self.provider}/{self.slug or self.doc_type}"


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
