"""Detect whether a captured payload is readable text or binary/mojibake garbage.

A source can return non-text content that still *looks* long enough to snapshot:
gzip that wasn't decompressed, a binary blob served with an HTML content-type, or a
page decoded under the wrong charset. Decoding such bytes with errors="replace"
yields a string full of U+FFFD replacement characters (and stray control bytes)
that passes a naive length check, gets stored, and then renders as corrupted
"changes" in the change feed (the Llama 4 license entry did exactly this).

This module is the single, inspectable heuristic used in two places:
  1. the fetcher refuses to snapshot a capture that fails the check, and
  2. the change-feed builder suppresses a diff between snapshots that fail it,
     and skips AI summarization of the garbage.

The thresholds are named constants, not magic numbers, so the rule is auditable.
"""

from __future__ import annotations

from typing import Dict, Tuple

# A well-formed HTML/text document has essentially no U+FFFD replacement characters.
# Anything above this fraction means the bytes did not decode as the claimed text.
MAX_REPLACEMENT_RATIO = 0.02  # 2%

# Real text has almost no C0 control characters other than tab/newline/carriage
# return. A high share signals binary content (compressed or otherwise non-text).
MAX_NONPRINT_RATIO = 0.15  # 15%

# The exact message shown in the change feed when a diff is suppressed, and recorded
# so the reason is traceable rather than silent.
NON_TEXT_MESSAGE = "Source returned non-text content. Diff suppressed pending re-fetch."

_ALLOWED_CONTROL = {"\t", "\n", "\r"}


def looks_like_text(s: str) -> Tuple[bool, Dict[str, float]]:
    """Return (is_text, stats) for a decoded string.

    `is_text` is False when the string carries too many Unicode replacement
    characters (a decode failure) or too many non-printable control bytes (binary
    content). `stats` reports the measured ratios for diagnostics. An empty string
    is treated as text here — emptiness/shortness is handled separately by the
    fetcher's minimum-length check, not by this function.
    """
    n = len(s)
    if n == 0:
        return True, {"replacement_ratio": 0.0, "nonprint_ratio": 0.0}

    replacement = s.count("�")
    nonprint = sum(
        1 for ch in s if ord(ch) < 0x20 and ch not in _ALLOWED_CONTROL
    )
    repl_ratio = replacement / n
    nonprint_ratio = nonprint / n
    stats = {
        "replacement_ratio": round(repl_ratio, 4),
        "nonprint_ratio": round(nonprint_ratio, 4),
    }
    is_text = repl_ratio <= MAX_REPLACEMENT_RATIO and nonprint_ratio <= MAX_NONPRINT_RATIO
    return is_text, stats
