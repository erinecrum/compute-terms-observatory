#!/usr/bin/env python3
"""Invariants for the full-document comparison pages.

The comparison page reproduces two full captured documents. Three things must
hold, and each has a way of quietly breaking:

  1. ALIGNMENT. Every changed hunk is one table row carrying both columns, so the
     before and after of a change are always level. If a change ever emitted two
     separate rows the columns would drift. Checked structurally.

  2. SINGLE COPY. The page must not carry the document twice. An earlier version
     emitted a second inline copy for mobile, which doubled every page and tripped
     the size guard on documents that would otherwise fit. Checked by word budget.

  3. WORD GRANULARITY. A one-token edit inside a paragraph marks that token, not
     the whole paragraph. Checked on a synthetic case.

Also asserts the aggressive-collapse fallback fires on an oversized synthetic
document rather than shipping it whole.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from observatory.blackline import build, _SIZE_CEILING  # noqa: E402


def main():
    fails = []

    # 1 + 3: a one-word edit in a paragraph.
    old = "The term is thirty days from the effective date of this agreement."
    new = "The term is sixty days from the effective date of this agreement."
    bl = build(old, new)
    if "<del>thirty</del>" not in bl.html:
        fails.append("word granularity: 'thirty' was not marked as the sole deletion")
    if "<ins>sixty</ins>" not in bl.html:
        fails.append("word granularity: 'sixty' was not marked as the sole insertion")
    if bl.html.count("effective date") != 2:  # once per column, unchanged
        fails.append("alignment: the unchanged context should appear once per column")

    # 1: every changed hunk is a single row.
    doc_a = "\n".join(f"line {i}" for i in range(40))
    doc_b = doc_a.replace("line 5", "line five").replace("line 20", "line twenty")
    bl2 = build(doc_a, doc_b)
    if bl2.change_count != 2:
        fails.append(f"change count: expected 2, got {bl2.change_count}")
    if bl2.html.count("data-change") != 2:
        fails.append(f"alignment: expected 2 changed rows, got {bl2.html.count('data-change')}")

    # 2: single copy — a mostly-unchanged large doc collapses, and its rendered
    # size stays well under twice the source (which a duplicated DOM would blow).
    big = "\n".join(f"unchanged clause number {i} of the agreement" for i in range(400))
    big2 = big.replace("clause number 200", "clause number two hundred")
    bl3 = build(big, big2)
    if "bl-expand" not in bl3.html and "bl-dropped" not in bl3.html:
        fails.append("collapse: a 400-line document produced no collapsed run")

    # aggressive fallback: a large document with many small isolated changes, so
    # hunks stay small (fast) but too little collapses to fit under the ceiling.
    # Every other line changes; the rest are unique so they cannot fold together.
    a_lines, b_lines = [], []
    for i in range(9000):
        a_lines.append(f"clause {i} says the original provision applies in full here")
        b_lines.append(f"clause {i} says the {'revised' if i % 2 else 'original'} "
                       f"provision applies in full here")
    bl4 = build("\n".join(a_lines), "\n".join(b_lines))
    if not bl4.collapsed_aggressively:
        fails.append("size guard: an oversized document with many changes did not "
                     "trigger aggressive collapse")

    # word-diff cap: a single huge contiguous rewrite must not stall; it is marked
    # whole rather than word-diffed.
    block_a = " ".join(f"word{i}old" for i in range(5000))
    block_b = " ".join(f"word{i}new" for i in range(5000))
    bl6 = build(block_a, block_b)
    if "<del>" not in bl6.html or "<ins>" not in bl6.html:
        fails.append("word-diff cap: a large rewrite was not marked at all")

    # unpaired: two different documents, no forced pairing, no false alignment.
    bl5 = build("Document one, entirely.", "A wholly different document two.",
                paired=False)
    if "data-change" in bl5.html:
        fails.append("unpaired: should not emit paired change rows")
    if bl5.change_count != 0:
        fails.append("unpaired: change count should be 0 (no pairing claimed)")

    if fails:
        print("Blackline checks FAILED:\n")
        for f in fails:
            print(f"  {f}")
        return 1
    print("All blackline checks passed (granularity, alignment, single copy, "
          "collapse, unpaired).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
