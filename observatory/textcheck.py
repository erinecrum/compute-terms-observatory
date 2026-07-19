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

# ---------------------------------------------------------------------------
# Minimum meaningful content, by document type.
#
# `looks_like_text` catches captures that are not text. This catches captures that
# ARE text but are not the document: a trust-centre landing page, a teaser
# paragraph with a "Learn more" link, a cookie-consent shell.
#
# The failure such a capture causes is the same one the status-derivation guard
# exists to prevent. A 234-character stub extracts as near-silent, and the matrix
# then asserts the provider's terms say nothing on a dimension, on the basis of a
# document nobody ever read. That is worse than an honest gap, because it looks
# like coverage.
#
# Thresholds are per doc_type because the floor differs by genre: a sub-processor
# list can legitimately be a short table, while a DPA or a set of service terms
# running to a few hundred characters is certainly a stub. They are deliberately
# conservative, set to catch obvious stubs rather than to judge completeness.
# ---------------------------------------------------------------------------

MIN_CONTENT_CHARS = {
    "service_terms": 2000,
    "dpa": 2000,
    "model_license": 1000,
    "privacy_policy": 2500,
    "aup": 1000,
    "sla": 1000,
    "ai_terms": 1000,
    "subprocessor_list": 400,      # legitimately short: often just a table
    "transparency_report": 1500,
    "ai_documentation": 500,
    "deprecation": 500,
}
DEFAULT_MIN_CONTENT_CHARS = 500


def min_content_chars(doc_type: str) -> int:
    return MIN_CONTENT_CHARS.get(doc_type or "", DEFAULT_MIN_CONTENT_CHARS)


def sufficient_content(text: str, doc_type: str) -> Tuple[bool, Dict[str, float]]:
    """Return (is_sufficient, stats) for a decoded capture of a given doc_type.

    Separate from `looks_like_text` on purpose: "this is not text" and "this is
    text, but it is not the document" are different failures with different fixes,
    and collapsing them would hide which one occurred.
    """
    n = len(text or "")
    threshold = min_content_chars(doc_type)
    return n >= threshold, {"chars": n, "threshold": threshold}


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
