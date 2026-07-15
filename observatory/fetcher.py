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

import io
import re
import time
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .model import Document, FetchResult, sha256_bytes, sha256_text

# We identify honestly as an archival bot (not a spoofed browser) and link back to
# the project, so any site owner can see exactly who we are. We are archivists,
# not scrapers evading anyone.
_UA = (
    "ComputeTermsObservatory/1.0 "
    "(+https://github.com/erinecrum/compute-terms-observatory; public terms archival)"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 45
_RETRIES = 3  # polite exponential back-off on transient network/5xx errors

# robots.txt parsers, cached per host so we read each site's rules once per run.
_robots_cache: dict = {}


def _robots_allows(url: str) -> tuple:
    """Return (allowed, reason). We honor robots.txt: if a host disallows a path
    for us, we do not fetch it and record the refusal as a failure. A missing or
    unreadable robots.txt is treated as 'allowed' (the web default)."""
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    if host not in _robots_cache:
        rp = None
        try:
            r = requests.get(urljoin(host, "/robots.txt"), headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                rp = robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None  # unreadable robots.txt -> treat as allowed
        _robots_cache[host] = rp
    rp = _robots_cache[host]
    if rp is None:
        return True, ""
    return (rp.can_fetch(_UA, url), "disallowed by robots.txt")


def _get_politely(url: str) -> requests.Response:
    """One GET with exponential back-off on transient errors. Callers fetch
    sequentially (one request at a time) so we never hammer a host in parallel."""
    last = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code >= 500:
                resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last = exc
            if attempt < _RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s
    raise last

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


def _lineify(raw_text: str) -> str:
    """Squeeze whitespace and drop blank lines so a single edited clause shows up
    as a single changed line downstream. Shared by the HTML and PDF paths."""
    lines = []
    for line in raw_text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _pdf_text(content: bytes) -> str:
    """Extract text from a PDF document, rendered line-oriented like the HTML path.
    Used for documents published only as PDFs (e.g. the Microsoft Customer
    Agreement), so they diff and extract consistently with HTML sources."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return _lineify("\n".join(pages))


def _docx_text(content: bytes) -> str:
    """Extract text from a DOCX document, including table cells — SLA credit tiers
    are usually laid out in tables, so paragraph text alone would miss them. Used
    for documents published only as DOCX (e.g. the Azure consolidated SLA)."""
    from docx import Document as DocxDocument

    d = DocxDocument(io.BytesIO(content))
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return _lineify("\n".join(parts))


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

    return _lineify(container.get_text("\n"))


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
        slug=doc.slug,
    )
    try:
        allowed, reason = _robots_allows(doc.url)
        if not allowed:
            result.ok = False
            result.error = reason
            return result

        resp = _get_politely(doc.url)
        result.http_status = resp.status_code
        resp.raise_for_status()

        content = resp.content
        content_type = resp.headers.get("content-type", "").lower()
        is_pdf = (
            content[:5] == b"%PDF-"
            or "application/pdf" in content_type
            or doc.url.lower().endswith(".pdf")
        )

        is_docx = doc.url.lower().endswith(".docx") or (
            "wordprocessingml" in content_type
        )
        # Any other zip-based Office binary (xlsx/pptx) we do not support: refuse
        # rather than decode as HTML and store garbage. We never store garbage and
        # never touch prior snapshots.
        is_other_office = (
            content[:4] == b"PK\x03\x04" and not is_docx
        ) or doc.url.lower().endswith((".xlsx", ".pptx"))

        if is_pdf:
            text = _pdf_text(content)
            result.raw_bytes = content
            result.raw_ext = "pdf"
            result.raw_sha256 = sha256_bytes(content)
        elif is_docx:
            text = _docx_text(content)
            result.raw_bytes = content
            result.raw_ext = "docx"
            result.raw_sha256 = sha256_bytes(content)
        elif is_other_office:
            raise RuntimeError(
                "unsupported document format (Office binary other than DOCX/PDF)"
            )
        else:
            raw_html = resp.text
            text = _normalize(raw_html)
            result.raw_html = raw_html
            result.raw_ext = "html"
            result.raw_sha256 = sha256_text(raw_html)

        if len(text) < _MIN_CHARS:
            raise RuntimeError(
                f"content suspiciously short ({len(text)} chars) — likely blocked "
                "or the page layout changed; refusing to snapshot"
            )

        result.text = text
        result.text_sha256 = sha256_text(text)
        result.char_count = len(text)
        result.ok = True
    except Exception as exc:  # noqa: BLE001 — we intentionally capture and report
        result.ok = False
        result.error = f"{type(exc).__name__}: {exc}"
    return result
