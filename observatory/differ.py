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
import re
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


# Excerpt budgets, in whole words.
#
# _MAX_WORDS is the original tight budget: quoted excerpts from provider documents
# stay well under 15 words. It is still the default everywhere a bare quote is
# shown.
#
# _CONTEXT_WORDS is the redline budget. A 12-word window centred on the changed
# span is often too small to read: it lands mid-clause, so the reader sees that
# something moved but not what it means. The redline therefore gets a larger
# budget and snaps to sentence boundaries where it can.
#
# NOTE: this deliberately relaxes the under-15-words rule for the redline view
# only. Raising _CONTEXT_WORDS reproduces more of each provider's document, so it
# is a copyright-posture decision, not a formatting one. It is a named constant so
# the posture is set in one place and is auditable.
_MAX_WORDS = 12
_CONTEXT_WORDS = 30

_SENT_END = re.compile(r"[.!?][\"')\]]?$")


def focused_excerpt(old: str, new: str, budget: int = _MAX_WORDS):
    """Return (old_excerpt, new_excerpt) centered on the FIRST place the two
    strings differ, each held to `budget` whole words so a reader sees what moved
    without reproducing a long passage."""
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            return _word_window(old, i1, i2, budget), _word_window(new, j1, j2, budget)
    return (_word_window(old, 0, len(old), budget),
            _word_window(new, 0, len(new), budget))


def _word_window(s: str, start: int, end: int, budget: int = _MAX_WORDS) -> str:
    """A short excerpt of `s` around the changed span [start:end], budgeted to
    `budget` whole words and centered on the change, with ellipses marking any
    trimming. Works on whole tokens so numbers like '99.99%' stay intact. Within
    the budget the window is pulled out to sentence boundaries, so the excerpt
    reads as a sentence rather than starting mid-clause."""
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", s)]
    if not tokens:
        return s.strip()

    changed = [i for i, (_, a, b) in enumerate(tokens) if b > start and a < end]
    if not changed:  # change sits at a boundary; anchor on the nearest token
        changed = [min(range(len(tokens)), key=lambda i: abs(tokens[i][1] - start))]
    lo, hi = changed[0], changed[-1]

    span = hi - lo + 1
    if span >= budget:
        return " ".join(w for w, _, _ in tokens[lo : lo + budget]) + "…"

    remaining = budget - span
    lead, trail = remaining // 2, remaining - remaining // 2
    a = max(0, lo - lead)
    b = min(len(tokens), hi + 1 + trail)

    # Pull back to the start of the sentence the change sits in, and forward to
    # its end, as long as the budget allows. Falling back to the plain window when
    # no boundary is in range keeps this from ever exceeding `budget`.
    for i in range(a, lo + 1):
        if i == 0 or _SENT_END.search(tokens[i - 1][0]):
            if hi - i + 1 <= budget:
                a = i
            break
    for j in range(b - 1, hi - 1, -1):
        if _SENT_END.search(tokens[j][0]):
            if j - a + 1 <= budget:
                b = j + 1
            break

    out = " ".join(w for w, _, _ in tokens[a:b])
    if a > 0:
        out = "…" + out
    if b < len(tokens):
        out = out + "…"
    return out


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
            # The redline is the reading surface, so it gets the wider budget.
            of, nf = focused_excerpt(old_chunk, new_chunk, _CONTEXT_WORDS)
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
