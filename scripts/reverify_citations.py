#!/usr/bin/env python3
"""Re-verify stored citations against the archived text, no model calls.

Fixes two causes of false "unverified" without re-extraction:
  - typographic mismatch (the model quoted with straight quotes, the capture uses
    curly ones) now folds to ASCII before matching;
  - elided citations ("A ... B") are verified span by span, each contiguous piece
    checked in the source, rather than as one string that appears nowhere.

Only ever RAISES confidence: a value already verified stays verified; an
unverified one is promoted only when its spans genuinely appear in the source.
Values whose quote still does not match are left unverified and honest.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from observatory.extractor import (_quote_verifies, _citation_spans,  # noqa: E402
                                    extractions_dir, load_extraction, save_extraction,
                                    _gather_sources)
from observatory.registry import load_registry  # noqa: E402
from observatory.snapshot import SnapshotStore  # noqa: E402


def main():
    only = sys.argv[1:] or None
    reg = load_registry()
    store = SnapshotStore("snapshots")
    grand = {"checked": 0, "promoted": 0, "still_unverified": 0}
    per_provider = {}

    for path in sorted(extractions_dir().glob("*.json")):
        provider = path.stem
        if only and provider not in only:
            continue
        rec = load_extraction(provider)
        if not rec:
            continue
        srcs = {s.slug: s for s in _gather_sources(provider, reg, store)}
        before = sum(1 for f in rec["fields"].values() if f.get("status") == "verified")
        promoted = still = 0
        for f in rec["fields"].values():
            cite = f.get("citation", "")
            cited = f.get("citation_document", "none")
            src = srcs.get(cited)
            f["citations"] = _citation_spans(cite)
            if not cite or src is None:
                continue
            grand["checked"] += 1
            ok = _quote_verifies(cite, src.text)
            if ok and f.get("status") != "verified":
                f["status"] = "verified"
                promoted += 1
            elif not ok and f.get("status") != "verified":
                still += 1
        after = sum(1 for f in rec["fields"].values() if f.get("status") == "verified")
        if promoted:
            save_extraction(rec)
        per_provider[provider] = (before, after, promoted)
        grand["promoted"] += promoted
        grand["still_unverified"] += still

    print(f"{'provider':22} verified before -> after  (promoted)")
    for p, (b, a, pr) in sorted(per_provider.items(), key=lambda kv: -kv[1][2]):
        mark = "  <-- " if pr else "      "
        print(f"  {p:20} {b:3} -> {a:3}{mark}{'+' + str(pr) if pr else ''}")
    print(f"\ntotal citations checked {grand['checked']}, promoted {grand['promoted']}, "
          f"still unverified {grand['still_unverified']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
