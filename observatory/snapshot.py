"""Snapshot store: the archival corpus. This is the product's core asset.

Archival discipline (design principle 1): every distinct version of every
document is preserved forever, timestamped, append-only. Nothing is overwritten
or discarded. Storing snapshots as plain files (not a database) is deliberate:

* A lawyer — or opposing counsel, or a court — can open any snapshot directly and
  see exactly what a provider's terms said on a given date.
* When GitHub Actions commits snapshots weekly, `git diff` becomes a legally
  legible change history for free.

Layout (nested so a human can browse the corpus by provider):

    snapshots/<provider>/<doc_type>/<UTC-timestamp>.html   # raw HTML, as served
    snapshots/<provider>/<doc_type>/<UTC-timestamp>.txt    # normalized text
    snapshots/<provider>/<doc_type>/<UTC-timestamp>.json   # metadata + hashes

We save a new snapshot only when the normalized text hash differs from the most
recent one (or on first sight). That keeps each stored version meaningful — a
real change, not a weekly duplicate — while never mutating what came before.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .model import FetchResult


class Snapshot:
    """A previously stored snapshot, loaded back from disk."""

    def __init__(self, meta: Dict[str, Any], text: Optional[str], stamp: str, path: Path):
        self.meta = meta
        self.text = text
        self.stamp = stamp
        self.path = path

    @property
    def fetched_at(self) -> str:
        return self.meta.get("fetched_at", "")

    @property
    def text_sha256(self) -> str:
        return self.meta.get("text_sha256", "")

    @property
    def content_date(self) -> str:
        """When the TEXT dates from, as opposed to when we fetched it.

        For a live fetch those coincide. For an Internet Archive fallback they do
        not: a capture pulled today can carry text from years ago. Ordering by
        fetch time therefore lets an archive fallback silently supersede newer live
        text, which is exactly what happened to the OpenAI Business Terms: a
        browser fetch pulled the Services Agreement effective 2026-01-01, and a
        later run fell back to the archive and re-served the 2023 text, which then
        became "latest" for both the matrix and the change feed.
        """
        cap = (self.meta.get("capture_timestamp") or "").strip()
        if self.meta.get("fetch_method") == "wayback" and cap:
            return cap
        return self.fetched_at

    @property
    def is_archived(self) -> bool:
        return self.meta.get("fetch_method") == "wayback"


class SnapshotStore:
    def __init__(self, root: str | Path = "snapshots"):
        self.root = Path(root)

    def _dir(self, provider: str, slug: str) -> Path:
        return self.root / provider / slug

    def _stamps(self, provider: str, slug: str) -> List[str]:
        d = self._dir(provider, slug)
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))

    def latest(self, provider: str, slug: str) -> Optional[Snapshot]:
        """The most recently FETCHED snapshot. Retained for callers that genuinely
        mean "the last thing we pulled"; anything that means "the current text of
        this document" wants `current` instead."""
        stamps = self._stamps(provider, slug)
        if not stamps:
            return None
        return self._load(provider, slug, stamps[-1])

    def current(self, provider: str, slug: str) -> Optional[Snapshot]:
        """The snapshot holding the most recent TEXT, by content date.

        This is the extraction and display source. An archive fallback can never
        displace newer live text here, because the ordering is on when the document
        dates from rather than when we happened to retrieve it. Ties fall back to
        fetch order, so repeated live fetches behave exactly as before.
        """
        snaps = self.history(provider, slug)
        if not snaps:
            return None
        return max(enumerate(snaps), key=lambda pair: (pair[1].content_date, pair[0]))[1]

    def lineage(self, provider: str, slug: str) -> List[Snapshot]:
        """Snapshots ordered by CONTENT date, for change detection.

        The feed compares consecutive pairs, so it must walk the document's own
        timeline. Ordered by fetch time, an archive fallback re-serving older text
        appears as a change back to that older text, and the feed narrates a fetch
        event as if the provider had rewritten their terms.
        """
        snaps = self.history(provider, slug)
        return [s for _, s in sorted(enumerate(snaps), key=lambda p: (p[1].content_date, p[0]))]

    def history(self, provider: str, slug: str) -> List[Snapshot]:
        """All snapshots oldest→newest by fetch time (the raw archival order)."""
        return [
            self._load(provider, slug, s)
            for s in self._stamps(provider, slug)
        ]

    def _load(self, provider: str, slug: str, stamp: str) -> Snapshot:
        d = self._dir(provider, slug)
        meta = json.loads((d / f"{stamp}.json").read_text(encoding="utf-8"))
        text_path = d / f"{stamp}.txt"
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else None
        return Snapshot(meta=meta, text=text, stamp=stamp, path=d / stamp)

    def save(self, result: FetchResult) -> Path:
        """Persist a FetchResult as a new, timestamped snapshot. Append-only —
        never touches existing files. Filename is the fetch time (UTC,
        filesystem-safe) so ordering is chronological and stable."""
        d = self._dir(result.provider, result.slug or result.doc_type)
        d.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

        meta = asdict(result)
        raw_html = meta.pop("raw_html", None)
        raw_bytes = meta.pop("raw_bytes", None)
        text = meta.pop("text", None)
        raw_ext = meta.get("raw_ext", "html")

        (d / f"{stamp}.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if text is not None:
            (d / f"{stamp}.txt").write_text(text, encoding="utf-8")
        # Archive the raw document under its native extension: HTML as text,
        # PDF (or any binary) as bytes. The raw corpus is the sacred asset.
        if raw_bytes is not None:
            (d / f"{stamp}.{raw_ext}").write_bytes(raw_bytes)
        elif raw_html is not None:
            (d / f"{stamp}.html").write_text(raw_html, encoding="utf-8")

        return d / f"{stamp}.json"

    def save_if_changed(self, result: FetchResult) -> Optional[Path]:
        """Save only when the normalized text differs from the latest snapshot
        (or there is no prior snapshot). Returns the new path, or None if the
        document was unchanged. This is what keeps the corpus append-only *and*
        free of weekly duplicates."""
        if not result.ok or result.text is None:
            return None
        prev = self.latest(result.provider, result.slug or result.doc_type)
        if prev is not None and prev.text_sha256 == result.text_sha256:
            return None
        return self.save(result)
