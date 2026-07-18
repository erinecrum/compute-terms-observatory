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
from .schema import DIMENSION_KEYS, DIMENSIONS
from .snapshot import SnapshotStore
from .textcheck import looks_like_text

MODEL = "claude-sonnet-5"  # light, fast model is enough for short change summaries

_SYSTEM = (
    "You are given the passages that changed between two versions of a cloud "
    "provider's public legal document. Summarize the SUBSTANTIVE changes (clauses, "
    "terms, numbers, or policies added, removed, or reworded) in one to three "
    "neutral, factual sentences. A routine 'Last Updated' date bump usually "
    "accompanies substantive edits: do not describe only the date, and do not call "
    "the whole edit administrative if any substantive clause also changed. Look at "
    "every passage, not just the first. Do not give advice, opinions, or risk "
    "assessments, and do not quote more than a few words. Then tag EVERY provided "
    "provision dimension whose subject matter any changed passage falls within or "
    "concerns (a renamed heading, a new subsection, or a reworded clause all count). "
    "Return an empty dimension list only when every changed passage is purely "
    "cosmetic page furniture: navigation links, formatting, or a date/version stamp. "
    "Also classify the change overall: substantive=true if any clause, term, number, "
    "or policy changed; substantive=false only when the edit is purely cosmetic "
    "(navigation, formatting, or a date/version stamp). When unsure, use true."
)

_TOOL = {
    "name": "record_change",
    "description": "Record the plain-English change description and the provisions it affects.",
    "input_schema": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "One or two neutral sentences on what the edit did.",
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string", "enum": DIMENSION_KEYS},
                "description": "Provision dimensions the change relates to; empty if purely administrative.",
            },
            "substantive": {
                "type": "boolean",
                "description": "true if any clause/term/number/policy changed; false if purely cosmetic.",
            },
        },
        "required": ["explanation", "dimensions", "substantive"],
    },
}


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


def _clip(s: str, n: int = 350) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def _explain(client, provider_name: str, document: str, blocks):
    """Return (explanation, dimension_keys) for one detected change. The model is
    given the fuller changed passages for context; only the site display is held to
    the under-15-words excerpt rule."""
    dims_help = "\n".join(f"- {d.key}: {d.label}" for d in DIMENSIONS)
    excerpts = "\n".join(
        f"- BEFORE: {_clip(b.old)}\n  AFTER:  {_clip(b.new)}" for b in blocks[:12]
    )
    prompt = (
        f"Provider: {provider_name}\nDocument: {document}\n\n"
        f"Provision dimensions:\n{dims_help}\n\n"
        f"The following passages changed (before/after excerpts):\n{excerpts}\n\n"
        "Describe what this change did and tag the provisions it affects."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=_SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_change"},
        messages=[{"role": "user", "content": prompt}],
    )
    for b in resp.content:
        if getattr(b, "type", None) == "tool_use":
            inp = b.input
            dims = [d for d in inp.get("dimensions", []) if d in DIMENSION_KEYS]
            return inp.get("explanation", "").strip(), dims, bool(inp.get("substantive", True))
    return "", [], True


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
            # Skip non-text snapshots (binary/mojibake): the model can only describe
            # noise, and the change feed suppresses the diff anyway.
            if not (looks_like_text(prev.text or "")[0] and looks_like_text(curr.text or "")[0]):
                continue
            key = change_key(doc.provider, doc.slug, prev.stamp, curr.stamp)
            # Regenerate if absent or if it predates the substantive-classification field.
            if key in notes and "substantive" in notes[key]:
                continue
            d = diff_text(prev.text, curr.text)
            if not d.has_changes:
                continue
            if client is None:
                client = _client()
            try:
                text, dims, substantive = _explain(client, doc.provider_name, doc.name, d.blocks)
            except Exception as exc:  # noqa: BLE001 — record nothing rather than fail the run
                print(f"  change note failed for {key}: {type(exc).__name__}: {exc}")
                continue
            notes[key] = {"explanation": text, "dimensions": dims,
                          "substantive": substantive, "model": MODEL}
            generated += 1

    if generated:
        save_notes(notes)
    return generated
