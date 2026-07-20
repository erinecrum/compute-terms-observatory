"""Full-document side-by-side blackline, generated at build time.

The inline redline in the change feed is a preview: a window onto the first
changed span, sized for scanning. This builds the evidence behind it — both
complete captured documents, laid out like a legal blackline, deleted text struck
through on the left and inserted text underlined on the right.

Structure. One table, one row per aligned diff hunk. Both cells of a row sit in
the same table row, so a changed block on the left is always level with its
replacement on the right without any measuring or scripting. That single
structure is restyled for narrow screens and print rather than duplicated, so a
294,000-character document is not shipped twice.

Granularity. Line-level alignment (difflib on lines) decides what pairs with
what; within a paired changed hunk a word-level diff marks the exact words that
moved, so a one-number edit in a long paragraph shows as one number, not a whole
changed paragraph.

Cost. The unchanged bulk of a provider's document is theirs; it is already public
on the two per-version pages, so reproducing it here adds no exposure, but it does
add bytes. Long unchanged runs collapse under an expander (the text stays in the
DOM, hidden). Above a size ceiling the far-from-change unchanged runs are dropped
from the DOM entirely and replaced by a non-expanding stub, because past a point
collapsing hidden text still ships the bytes. Which documents hit that ceiling is
reported to the build.

No client-side diffing: everything here runs at build time and emits static HTML.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from html import escape
from typing import List, Optional, Tuple

# Unchanged runs longer than this collapse under an expander. Short runs stay open
# so the reader keeps their bearings between nearby changes.
_COLLAPSE_OVER = 6
# When collapsing, keep this many lines of context on each side of the change.
_CONTEXT_LINES = 3

# Rendered-size ceiling (characters of emitted HTML). Past this, unchanged runs
# beyond the context window are dropped from the DOM rather than merely hidden.
# 600 KB keeps the heaviest page openable on a phone.
_SIZE_CEILING = 600_000

_WORD = re.compile(r"\w+|\s+|[^\w\s]")


@dataclass
class Hunk:
    kind: str            # "equal" | "replace" | "insert" | "delete"
    old: List[str] = field(default_factory=list)
    new: List[str] = field(default_factory=list)


@dataclass
class Blackline:
    html: str
    change_count: int
    collapsed_aggressively: bool  # unchanged runs dropped from DOM, not just hidden


def _hunks(old_text: str, new_text: str) -> List[Hunk]:
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    out: List[Hunk] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(Hunk("equal", old_lines[i1:i2], new_lines[j1:j2]))
        elif tag == "replace":
            out.append(Hunk("replace", old_lines[i1:i2], new_lines[j1:j2]))
        elif tag == "delete":
            out.append(Hunk("delete", old_lines[i1:i2], []))
        elif tag == "insert":
            out.append(Hunk("insert", [], new_lines[j1:j2]))
    return out


# Above this combined token count a hunk is marked whole (all-old struck, all-new
# inserted) instead of word-diffed. Word diffing is O(n*m); a large contiguous
# rewrite (a whole section replaced) would otherwise stall the build. At this size
# the word-level detail is unreadable anyway, so marking the block is both faster
# and clearer.
_WORD_DIFF_TOKEN_CAP = 6000


def _word_markup(old: str, new: str) -> Tuple[str, str]:
    """Old side with deletions struck, new side with insertions underlined, the
    unchanged words plain on both. Diffing on whole tokens keeps '99.99%' intact."""
    a = _WORD.findall(old)
    b = _WORD.findall(new)
    if len(a) + len(b) > _WORD_DIFF_TOKEN_CAP:
        # Too large to word-diff affordably: mark the whole block.
        lo = f"<del>{escape(old)}</del>" if old.strip() else escape(old)
        ro = f"<ins>{escape(new)}</ins>" if new.strip() else escape(new)
        return lo, ro
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    left, right = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        seg_old = escape("".join(a[i1:i2]))
        seg_new = escape("".join(b[j1:j2]))
        if tag == "equal":
            left.append(seg_old)
            right.append(seg_new)
        else:
            if seg_old.strip():
                left.append(f"<del>{seg_old}</del>")
            elif seg_old:
                left.append(seg_old)
            if seg_new.strip():
                right.append(f"<ins>{seg_new}</ins>")
            elif seg_new:
                right.append(seg_new)
    return "".join(left), "".join(right)


def _equal_row(lines: List[str]) -> str:
    body = escape("\n".join(lines))
    return (f'<tr class="bl-eq"><td class="bl-l"><pre>{body}</pre></td>'
            f'<td class="bl-r"><pre>{body}</pre></td></tr>')


def _collapsed_row(n: int, lines: List[str], drop: bool) -> str:
    """An expander standing in for a long unchanged run. When `drop` is set the
    text is NOT included (a hard stub for oversized pages); otherwise it is present
    but hidden and revealed on click."""
    label = f"Show {n} unchanged paragraph{'s' if n != 1 else ''}"
    if drop:
        return (f'<tr class="bl-fold bl-dropped"><td colspan="2">'
                f'<span class="bl-foldlbl">{n} unchanged paragraph'
                f'{"s" if n != 1 else ""} not shown &middot; '
                f'read them in the source document</span></td></tr>')
    body = escape("\n".join(lines))
    return (f'<tr class="bl-fold"><td colspan="2">'
            f'<button type="button" class="bl-expand">{label}</button>'
            f'<pre class="bl-hidden" hidden>{body}</pre></td></tr>')


def _changed_rows(h: Hunk) -> Tuple[str, int]:
    """Row(s) for a changed hunk, and how many change markers it carries."""
    if h.kind == "insert":
        old_cell = '<td class="bl-l bl-empty"></td>'
        body = escape("\n".join(h.new))
        new_cell = f'<td class="bl-r"><pre><ins>{body}</ins></pre></td>'
        return f'<tr class="bl-chg" data-change>{old_cell}{new_cell}</tr>', 1
    if h.kind == "delete":
        body = escape("\n".join(h.old))
        old_cell = f'<td class="bl-l"><pre><del>{body}</del></pre></td>'
        new_cell = '<td class="bl-r bl-empty"></td>'
        return f'<tr class="bl-chg" data-change>{old_cell}{new_cell}</tr>', 1
    # replace: word-diff the two runs against each other
    left, right = _word_markup("\n".join(h.old), "\n".join(h.new))
    return (f'<tr class="bl-chg" data-change>'
            f'<td class="bl-l"><pre>{left}</pre></td>'
            f'<td class="bl-r"><pre>{right}</pre></td></tr>', 1)


def build(old_text: str, new_text: str, *, paired: bool = True) -> Blackline:
    """Render the full blackline for one change.

    One table is emitted, never a second copy for mobile: narrow screens and print
    restructure the same table with CSS (the unchanged left cell hides, changed
    rows stack old-above-new). That single-copy rule is what keeps a 294,000-char
    document from tripping the size ceiling merely by existing twice.

    `paired=False` (source-change / curation entries) shows both documents side by
    side with their internal changes marked but forces NO alignment between the two
    unrelated structures: pairing lines across different documents would invent a
    correspondence that is not there.
    """
    if not paired:
        return _unpaired(old_text, new_text)

    hunks = _hunks(old_text, new_text)
    change_count = sum(1 for h in hunks if h.kind != "equal")
    n_h = len(hunks)

    def render(drop_distant: bool) -> str:
        rows = []
        for idx, h in enumerate(hunks):
            if h.kind == "equal":
                run = h.old
                if len(run) > _COLLAPSE_OVER:
                    head = run[:_CONTEXT_LINES] if idx > 0 else []
                    tail = run[-_CONTEXT_LINES:] if idx < n_h - 1 else []
                    mid = run[len(head):len(run) - len(tail)] if (head or tail) else run
                    if head:
                        rows.append(_equal_row(head))
                    rows.append(_collapsed_row(len(mid), mid, drop_distant))
                    if tail:
                        rows.append(_equal_row(tail))
                else:
                    rows.append(_equal_row(run))
            else:
                row, _ = _changed_rows(h)
                rows.append(row)
        return ('<table class="bl-split"><thead><tr>'
                '<th class="bl-l">Before</th><th class="bl-r">After</th>'
                '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')

    html = render(drop_distant=False)
    aggressive = False
    if len(html) > _SIZE_CEILING:
        html = render(drop_distant=True)
        aggressive = True
    return Blackline(html=html, change_count=change_count,
                     collapsed_aggressively=aggressive)


def _unpaired(old_text: str, new_text: str) -> Blackline:
    """Two different documents side by side, each whole, no cross-alignment.
    Changes within are not block-paired because there is no shared structure to
    pair against; the point is to let a reader see both, not to redline one into
    the other."""
    left = escape(old_text or "")
    right = escape(new_text or "")
    split = ('<table class="bl-split bl-unpaired"><thead><tr>'
             '<th class="bl-l">Earlier document</th>'
             '<th class="bl-r">Current document</th></tr></thead><tbody>'
             f'<tr><td class="bl-l"><pre>{left}</pre></td>'
             f'<td class="bl-r"><pre>{right}</pre></td></tr></tbody></table>')
    return Blackline(html=split, change_count=0, collapsed_aggressively=False)
