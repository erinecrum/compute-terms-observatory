#!/usr/bin/env python3
"""The contact address must never appear un-encoded in generated HTML.

It is entity-encoded in the site generator so naive regex email scrapers do not
harvest it. This check fails the build if the literal string appears in any
generated page, so a future template cannot reintroduce it plain. The encoding is
cheap friction, not protection: any scraper that parses the DOM still sees the
address (noted in FOLLOWUPS), and the real spam defence is Workspace filtering.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PLAIN = "contact@termsobservatory.org"


def main():
    pages = sorted(SITE.glob("*.html"))
    if not pages:
        print("No built pages found; run `python main.py site` first.")
        return 1
    hits = [p.name for p in pages if PLAIN in p.read_text(encoding="utf-8")]
    if hits:
        print(f"Plain-contact check FAILED: the un-encoded address {PLAIN!r} appears "
              f"in {len(hits)} generated page(s):\n  " + "\n  ".join(hits))
        print("\nThe address is entity-encoded in _shell via _encode_contact. If a "
              "page reintroduced it plain, route that rendering through the shell "
              "or encode it there.")
        return 1
    print(f"All plain-contact checks passed ({len(pages)} pages; the contact address "
          f"is entity-encoded everywhere).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
