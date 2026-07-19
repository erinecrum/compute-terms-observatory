#!/usr/bin/env python3
"""Regression checks for status derivation, guarding one specific false claim.

Run:  python scripts/test_status_derivation.py

THE BUG THIS LOCKS OUT
----------------------
`_derive_status` rebuilds a field's status from its value. A suppressed or
uncaptured field has an EMPTY value, so a naive derivation reads that emptiness as
absence and returns `no_clause_found`, which the site renders as **"silent"**.

"Silent" is a finding about the provider: it asserts that their terms were read and
address nothing on this point. For a document that was never captured, or that was
withheld because it governs a superseded generation, that assertion is false and
is exactly the kind of claim this site exists never to make. It is also invisible:
the cell looks like an ordinary, confident result.

Capture-absence and suppression states are therefore AUTHORITATIVE. They are set by
the pipeline from facts about retrieval, not inferred from content, and derivation
must pass them through untouched. These checks fail loudly if a future refactor
reintroduces the conversion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observatory.dataset import _CAPTURE_ABSENT, _derive_status, display_value  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}\n        got {got!r}, want {want!r}"
          if not ok else f"  PASS  {label}")
    if not ok:
        FAILURES.append(label)


def main():
    print("Capture-absence states survive derivation (the core guarantee)")
    for status in _CAPTURE_ABSENT:
        # The realistic shape: suppression empties the value and citation.
        field = {"status": status, "value": "", "citation": ""}
        check(f"{status}: passes through an applicable dimension",
              _derive_status(field, "termination", "closed", "closed_api"), status)
        check(f"{status}: never becomes 'silent'",
              _derive_status(field, "termination", "closed", "closed_api") != "no_clause_found",
              True)
        # With a cause attached, as the pipeline sets it.
        field_c = {"status": status, "value": "", "citation": "",
                   "capture_cause": "generation_mismatch"}
        check(f"{status}: survives with a capture_cause attached",
              _derive_status(field_c, "liability", "open", "open_weight"), status)

    print("\nDisplay never renders a capture-absence state as 'silent'")
    for status in _CAPTURE_ABSENT:
        shown = display_value({"status": status, "value": ""})
        check(f"{status}: display_value is not 'silent'", shown != "silent", True)
        check(f"{status}: display_value is non-empty", bool(shown), True)

    print("\nOrdinary derivation still works (guard against over-correcting)")
    check("substantive verified value -> quote_verified",
          _derive_status({"status": "verified", "value": "30 days notice"},
                         "termination", "closed", "closed_api"), "quote_verified")
    check("substantive unverified value -> quote_unverified",
          _derive_status({"status": "unverified", "value": "30 days notice"},
                         "termination", "closed", "closed_api"), "quote_unverified")
    check("genuinely absent value -> no_clause_found",
          _derive_status({"status": "unverified", "value": "not specified"},
                         "termination", "closed", "closed_api"), "no_clause_found")
    check("segment-inapplicable dimension -> not_applicable",
          _derive_status({"status": "unverified", "value": "whatever"},
                         "credit_regime", "open", "open_weight"), "not_applicable")

    print("\nA capture-absence state outranks segment inapplicability")
    # Both rules could fire; the capture fact is the one a reader needs, because
    # "not applicable" would imply we decided the dimension cannot arise here.
    check("access_restricted on an inapplicable dimension stays access_restricted",
          _derive_status({"status": "access_restricted", "value": ""},
                         "credit_regime", "open", "open_weight"), "access_restricted")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All status-derivation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
