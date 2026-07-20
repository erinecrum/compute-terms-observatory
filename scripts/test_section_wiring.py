#!/usr/bin/env python3
"""Guard: every rendered matrix table must be visible to the client-side features.

Run:  python scripts/test_section_wiring.py   (after `python main.py site`)

THE BUG THIS LOCKS OUT
----------------------
Compare mode and group collapse both need the list of matrix table ids. That list
used to be a literal in the JS. When the sections were reorganized and the tables
renamed, the literal still named the old ids, so compare mode could not find any
cell and rendered every card as "not applicable for this provider type" -- a
plausible-looking answer that was entirely wrong. Group collapse broke the same way.

Nothing failed. The page rendered, no error appeared in the console, and the wrong
answer looked like a real one. That is the failure mode worth a test.

The ids are now emitted from the sections that are actually built
(window.CTO_TABLES). These checks fail if that wiring is ever broken again, either
by reintroducing a literal or by adding a section whose table is not in the list.
"""

import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site" / "index.html"
FAILURES = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"\n        {detail}" if not ok and detail else ""))
    if not ok:
        FAILURES.append(label)


def main():
    if not SITE.exists():
        print(f"index.html not found at {SITE}; run `python main.py site` first.")
        return 1
    html = SITE.read_text(encoding="utf-8")

    rendered = set(re.findall(r'<table class="matrix" id="([^"]+)"', html))
    emitted_m = re.search(r"window\.CTO_TABLES=(\[[^\]]*\]);", html)
    emitted = set(re.findall(r'"([^"]+)"', emitted_m.group(1))) if emitted_m else set()

    print(f"Rendered tables: {sorted(rendered)}")
    print(f"Emitted to JS  : {sorted(emitted)}\n")

    check("CTO_TABLES is emitted at all", bool(emitted_m),
          "compare mode and group collapse have no table list to work from")

    missing = rendered - emitted
    check("every rendered table is visible to compare mode", not missing,
          f"invisible to compare mode, will render as 'not applicable': {sorted(missing)}")

    phantom = emitted - rendered
    check("no table is listed that does not exist", not phantom,
          f"listed but never rendered: {sorted(phantom)}")

    # The literals that caused the original bug must not come back.
    literals = re.findall(r"\['tbl-[^\]]*\]", html)
    check("no hardcoded table-id list remains in the JS", not literals,
          f"hardcoded list(s) found: {literals[:2]}")

    # Every section that renders a table should have one, so a new section cannot
    # be added table-less and silently sit outside every client-side feature.
    sections = set(re.findall(r'<section id="([^"]+)" class="msec"', html))
    check("at least one table per rendered section",
          len(rendered) >= len(sections),
          f"{len(sections)} sections but only {len(rendered)} tables")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All section-wiring checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
