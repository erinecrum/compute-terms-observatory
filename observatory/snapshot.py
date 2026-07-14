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


class SnapshotStore:
    def __init__(self, root: str | Path = "snapshots"):
        self.root = Path(root)

    def _dir(self, provider: str, doc_type: str) -> Path:
        return self.root / provider / doc_type

    def _stamps(self, provider: str, doc_type: str) -> List[str]:
        d = self._dir(provider, doc_type)
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.json"))

    def latest(self, provider: str, doc_type: str) -> Optional[Snapshot]:
        stamps = self._stamps(provider, doc_type)
        if not stamps:
            return None
        return self._load(provider, doc_type, stamps[-1])

    def history(self, provider: str, doc_type: str) -> List[Snapshot]:
        """All snapshots oldest→newest (for a document's change history page)."""
        return [
            self._load(provider, doc_type, s)
            for s in self._stamps(provider, doc_type)
        ]

    def _load(self, provider: str, doc_type: str, stamp: str) -> Snapshot:
        d = self._dir(provider, doc_type)
        meta = json.loads((d / f"{stamp}.json").read_text(encoding="utf-8"))
        text_path = d / f"{stamp}.txt"
        text = text_path.read_text(encoding="utf-8") if text_path.exists() else None
        return Snapshot(meta=meta, text=text, stamp=stamp, path=d / stamp)

    def save(self, result: FetchResult) -> Path:
        """Persist a FetchResult as a new, timestamped snapshot. Append-only —
        never touches existing files. Filename is the fetch time (UTC,
        filesystem-safe) so ordering is chronological and stable."""
        d = self._dir(result.provider, result.doc_type)
        d.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

        meta = asdict(result)
        raw_html = meta.pop("raw_html", None)
        text = meta.pop("text", None)

        (d / f"{stamp}.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if text is not None:
            (d / f"{stamp}.txt").write_text(text, encoding="utf-8")
        if raw_html is not None:
            (d / f"{stamp}.html").write_text(raw_html, encoding="utf-8")

        return d / f"{stamp}.json"

    def save_if_changed(self, result: FetchResult) -> Optional[Path]:
        """Save only when the normalized text differs from the latest snapshot
        (or there is no prior snapshot). Returns the new path, or None if the
        document was unchanged. This is what keeps the corpus append-only *and*
        free of weekly duplicates."""
        if not result.ok or result.text is None:
            return None
        prev = self.latest(result.provider, result.doc_type)
        if prev is not None and prev.text_sha256 == result.text_sha256:
            return None
        return self.save(result)
