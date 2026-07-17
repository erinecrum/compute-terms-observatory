"""Plain-English AI descriptions of detected document changes, for the change feed.

For each detected change (a document whose text differs from its prior snapshot),
we ask Claude to describe, in one or two neutral sentences, what the edit did. The
descriptions are cached in data/change_notes.json keyed by the snapshot pair, so
they are generated once (during the pipeline `run`, which has the API key) and
simply read back when the site is built (which stays key-free).

Every description is clearly an AI summary and is shown with a "verify against the
source" note; it never gives advice and never quotes more than a few words.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from .differ import diff_text
from .registry import Registry
from .snapshot import SnapshotStore

MODEL = "claude-sonnet-5"  # light, fast model is enough for short change summaries

_SYSTEM = (
    "You describe, in plain English, what changed between two versions of a cloud "
    "provider's public legal document. Reply with one or two neutral, factual "
    "sentences stating what the edit did (e.g. a number, a clause, or a policy that "
    "was added, removed, or reworded). Do not give advice, opinions, or risk "
    "assessments. Do not quote more than a few words from the document."
)


def notes_path() -> Path:
    return Path("data/change_notes.json")


def load_notes() -> Dict[str, dict]:
    p = notes_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_notes(notes: Dict[str, dict]) -> Path:
    p = notes_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def change_key(provider: str, slug: str, prev_stamp: str, curr_stamp: str) -> str:
    return f"{provider}/{slug}/{prev_stamp}->{curr_stamp}"


def _client():
    from anthropic import Anthropic

    return Anthropic()


def _explain(client, provider_name: str, document: str, blocks) -> str:
    excerpts = "\n".join(
        f"- BEFORE: {b.old_focus}\n  AFTER:  {b.new_focus}" for b in blocks[:8]
    )
    prompt = (
        f"Provider: {provider_name}\nDocument: {document}\n\n"
        f"The following passages changed (before/after excerpts):\n{excerpts}\n\n"
        "Describe what this change did."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def generate_missing(registry: Registry, store: SnapshotStore) -> int:
    """Generate and cache AI descriptions for any detected change that does not yet
    have one. Returns the number newly generated. No-ops (returns 0) if there is no
    API key, so the pipeline still completes without descriptions."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return 0

    notes = load_notes()
    client = None
    generated = 0
    for doc in registry.documents():
        history = store.history(doc.provider, doc.slug)
        for prev, curr in zip(history, history[1:]):
            # Skip source swaps (different URL) — a text diff across two different
            # documents is not a meaningful "edit" to describe.
            if prev.meta.get("url") != curr.meta.get("url"):
                continue
            key = change_key(doc.provider, doc.slug, prev.stamp, curr.stamp)
            if key in notes:
                continue
            d = diff_text(prev.text, curr.text)
            if not d.has_changes:
                continue
            if client is None:
                client = _client()
            try:
                text = _explain(client, doc.provider_name, doc.name, d.blocks)
            except Exception as exc:  # noqa: BLE001 — record nothing rather than fail the run
                print(f"  change note failed for {key}: {type(exc).__name__}: {exc}")
                continue
            notes[key] = {"explanation": text, "model": MODEL}
            generated += 1

    if generated:
        save_notes(notes)
    return generated
