#!/usr/bin/env python3
"""Self-contained checks for the non-text detection heuristic (Issue 1).

Run:  python scripts/test_text_check.py

Verifies that ordinary HTML/text passes `looks_like_text`, and that binary,
compressed, or wrong-charset payloads (which decode into U+FFFD mojibake or
control bytes) are rejected — the exact failure that put corrupted Llama diffs in
the change feed.
"""

import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observatory.textcheck import (  # noqa: E402
    MAX_REPLACEMENT_RATIO,
    looks_like_text,
)

FAILURES = []


def check(label: str, condition: bool) -> None:
    status = "ok  " if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    # --- text that must PASS ---
    html = "<html><body><h1>Terms of Service</h1><p>" + ("Provider terms. " * 200) + "</p></body></html>"
    check("plain HTML is text", looks_like_text(html)[0])

    accented = "Résumé — café, naïve, Zürich, façade. " * 50  # legitimate non-ASCII
    check("accented UTF-8 text is text", looks_like_text(accented)[0])

    empty = ""
    check("empty string is treated as text (length handled elsewhere)", looks_like_text(empty)[0])

    # --- content that must be REJECTED ---
    # 1. Gzip bytes decoded as UTF-8 with errors="replace" (the classic wayback/
    #    compressed-capture failure): produces heavy mojibake.
    gz = gzip.compress(html.encode("utf-8"))
    mojibake = gz.decode("utf-8", "replace")
    is_text, stats = looks_like_text(mojibake)
    check("gzip-as-utf8 mojibake is rejected", not is_text)
    check(f"  replacement_ratio {stats['replacement_ratio']} exceeds {MAX_REPLACEMENT_RATIO}",
          stats["replacement_ratio"] > MAX_REPLACEMENT_RATIO)

    # 2. Arbitrary binary bytes decoded with replace.
    binary = bytes(range(256)) * 40
    check("raw binary blob is rejected", not looks_like_text(binary.decode("utf-8", "replace"))[0])

    # 3. Control-byte heavy content (non-printable ratio).
    control = ("\x00\x01\x02\x03\x04" * 500) + "some text"
    check("control-byte-heavy content is rejected", not looks_like_text(control)[0])

    # 4. A tiny sprinkle of replacement chars in a long clean doc must still PASS
    #    (a single bad character shouldn't nuke an otherwise-fine page).
    almost_clean = html + "�"
    check("one stray replacement char in a long doc still passes", looks_like_text(almost_clean)[0])

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
