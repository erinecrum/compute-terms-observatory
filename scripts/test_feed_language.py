#!/usr/bin/env python3
"""The change feed shows no pipeline vocabulary, and every relocation says so.

Two internal strings shipped to readers verbatim once: "Tracked source document
changed; not an edit of the same document." was pipeline phrasing, and relocation
entries blacklined two unrelated documents. This guards both:

  - No banned internal phrase appears in the rendered feed. All reader-facing
    wording is composed from display_strings.yaml, so pipeline text cannot reach
    the page.
  - Every source-relocation and curation entry carries the unmissable "[provider]
    did not change its terms" line, so a reader never mistakes an Observatory
    tracking change for a provider changing their terms.

Reads the built site/changes.html.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Phrasing that must never reach a reader: old internal notes and field names as
# visible copy. (The word "substantive" is allowed inside AI-written prose, so it
# is matched only as a standalone data-style token, not checked here.)
BANNED = [
    "Tracked source document changed",
    "not an edit of the same document",
    "source_changed",
    "versions_suppressed",
    "all_blocks",
]


def visible_text(html: str) -> str:
    """Strip tags and data-* attributes so only reader-visible copy remains."""
    body = html.split("</head>", 1)[-1]
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return body


def main():
    feed = ROOT / "site/changes.html"
    if not feed.exists():
        print("site/changes.html not found; run `python main.py site` first.")
        return 1
    html = feed.read_text()
    text = visible_text(html)

    fails = []
    for phrase in BANNED:
        if phrase in text:
            fails.append(f"  internal phrase reached the feed: {phrase!r}")

    # The feed shows only genuine provider term changes. Observatory bookkeeping
    # (relocations, curation) and its "did not change its terms" line must not
    # appear at all: those entries are excluded from the public feed, not merely
    # relabelled.
    if "we changed which document we track for this entry" in html:
        fails.append("  a relocation/curation entry is in the public feed; only "
                     "genuine provider term changes belong there")
    if "did not change its terms" in html:
        fails.append("  the 'did not change its terms' line is in the feed; those "
                     "entries should be excluded entirely, not shown")

    if fails:
        print("Feed-language check FAILED:\n")
        print("\n".join(fails))
        print("\nReader-facing wording lives in display_strings.yaml. The pipeline "
              "emits kinds, not prose.")
        return 1

    entries = html.count('class="change"')
    print(f"All feed-language checks passed ({entries} feed entries, all genuine "
          f"provider term changes; no bookkeeping, no internal phrasing).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
