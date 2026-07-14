"""Generic fetcher: retrieve one public document and normalize it.

One function fetches any registry `Document`. There are no per-provider classes:
providers differ only by URL, and the normalizer is deliberately generic so a
new provider needs no code.

Normalization mirrors the radar project: isolate the main content, strip
non-content noise (scripts, nav, footers) that would create phantom diffs, and
render the text one logical block per line so a single edited clause shows up as
a single changed line downstream.

We keep BOTH the raw HTML (the archival corpus — sacred, never discarded) and the
normalized text (the change signal we diff and the input we extract from).
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from .model import Document, FetchResult, sha256_text

# A normal browser UA. Many providers serve a stripped or blocked response to an
# empty UA; this gets the real page. We identify politely in a comment-free way
# consistent with the radar project.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 45

# Preferred content containers, tried in order, with a whole-body fallback so a
# template tweak never blanks a snapshot.
_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role=main]",
    "#main-content",
    "#content",
    ".content",
    "#aws-page-content-main",
]

# Elements that are never legal content but often sit inside the main container.
_NOISE = "script, style, noscript, svg, nav, header, footer, form, iframe"

# Below this many characters we assume we were blocked or the layout broke, and
# refuse to record the snapshot — a near-empty snapshot would read as "the
# provider deleted its entire terms document" on the next diff.
_MIN_CHARS = 200


def _normalize(html: str) -> str:
    """Extract the document text and render it line-oriented for clean diffing."""
    soup = BeautifulSoup(html, "html.parser")

    container = None
    for sel in _CONTENT_SELECTORS:
        container = soup.select_one(sel)
        if container is not None:
            break
    if container is None:
        container = soup.body or soup  # last resort: whole document

    for tag in container.select(_NOISE):
        tag.decompose()

    raw = container.get_text("\n")
    lines = []
    for line in raw.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def fetch_document(doc: Document) -> FetchResult:
    """Fetch and normalize one document. On any failure returns a FetchResult
    with ok=False and an error message rather than raising, so a single broken
    URL doesn't abort a whole-registry run — the runner reports it and moves on.
    """
    result = FetchResult(
        provider=doc.provider,
        provider_name=doc.provider_name,
        doc_type=doc.doc_type,
        name=doc.name,
        url=doc.url,
    )
    try:
        resp = requests.get(doc.url, headers=_HEADERS, timeout=_TIMEOUT)
        result.http_status = resp.status_code
        resp.raise_for_status()

        raw_html = resp.text
        text = _normalize(raw_html)
        if len(text) < _MIN_CHARS:
            raise RuntimeError(
                f"content suspiciously short ({len(text)} chars) — likely blocked "
                "or the page layout changed; refusing to snapshot"
            )

        result.raw_html = raw_html
        result.text = text
        result.text_sha256 = sha256_text(text)
        result.raw_sha256 = sha256_text(raw_html)
        result.char_count = len(text)
        result.ok = True
    except Exception as exc:  # noqa: BLE001 — we intentionally capture and report
        result.ok = False
        result.error = f"{type(exc).__name__}: {exc}"
    return result
