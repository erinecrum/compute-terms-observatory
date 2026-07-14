"""Differ: detect what changed in a document between two snapshots.

Every document here is a page-diff document (normalized text), so there is one
detection mode: compare the previous snapshot's text to the current one. We
produce both a full unified diff (for the audit trail) and the changes localized
into old/new block pairs, each focused on the exact span that moved — a terms
edit is often a single number or clause buried in a long paragraph, and showing
the paragraph head would render OLD and NEW as visually identical.

This mirrors the radar project's diff engine, trimmed to the text case.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChangedBlock:
    """One localized change: the old text and the new text that replaced it.
    Either side may be empty (pure addition or pure deletion). `old_focus` /
    `new_focus` are windowed on the exact differing span for readable excerpts."""

    old: str
    new: str
    old_focus: str = ""
    new_focus: str = ""


@dataclass
class TextDiff:
    has_changes: bool
    added_lines: int = 0
    removed_lines: int = 0
    unified: str = ""
    blocks: List[ChangedBlock] = field(default_factory=list)
    is_first_run: bool = False  # no prior snapshot existed — a baseline, not a change


def _lines(text: Optional[str]) -> List[str]:
    return text.splitlines() if text else []


def focused_excerpt(old: str, new: str, context: int = 90):
    """Return (old_excerpt, new_excerpt) windowed around the FIRST place the two
    strings actually differ, so a reader sees what moved rather than the shared
    paragraph head."""
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            return _window(old, i1, i2, context), _window(new, j1, j2, context)
    return old[: context * 2], new[: context * 2]


def _window(s: str, start: int, end: int, context: int) -> str:
    a = max(0, start - context)
    b = min(len(s), end + context)
    snippet = s[a:b].replace("\n", " ")
    return ("…" if a > 0 else "") + snippet + ("…" if b < len(s) else "")


def diff_text(old: Optional[str], new: Optional[str]) -> TextDiff:
    """Compare two normalized page texts.

    With no prior snapshot we report `is_first_run` and no changes — a baseline,
    not "the whole document was added". That keeps the first sighting of a
    document from flooding the change feed.
    """
    if old is None:
        return TextDiff(has_changes=False, is_first_run=True)
    new = new or ""

    old_lines = _lines(old)
    new_lines = _lines(new)

    unified = "\n".join(difflib.unified_diff(old_lines, new_lines, lineterm="", n=1))

    added = removed = 0
    blocks: List[ChangedBlock] = []
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old_chunk = "\n".join(old_lines[i1:i2]).strip()
        new_chunk = "\n".join(new_lines[j1:j2]).strip()
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
        if old_chunk or new_chunk:
            of, nf = focused_excerpt(old_chunk, new_chunk)
            blocks.append(
                ChangedBlock(old=old_chunk, new=new_chunk, old_focus=of, new_focus=nf)
            )

    return TextDiff(
        has_changes=bool(blocks),
        added_lines=added,
        removed_lines=removed,
        unified=unified,
        blocks=blocks,
    )
