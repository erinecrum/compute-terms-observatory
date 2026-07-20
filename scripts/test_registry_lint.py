#!/usr/bin/env python3
"""Mechanical half of the governing-document rule.

The rule -- every document must govern the entry's tracked artifact -- is a legal
judgment and cannot be tested. Two parts of it are mechanical, and this checks
those, so that judgment is spent only where judgment is needed.

  1. DOC TYPE vs ENTRY CLASS. A DPA on a set of downloadable weights is a category
     error on its face: running weights you downloaded creates no data-processing
     relationship with the publisher, so there is nothing for a DPA to govern. No
     reading of the document changes that. entry_classes.yaml holds the permitted
     types per class and, for the reviewer's benefit, why each exclusion holds.

  2. GOVERNS LINE PRESENT. Every fetchable document must carry a one-sentence
     `governs` field stating what it governs and why that is this entry's tracked
     artifact. The field is where the judgment lives; requiring it means the
     judgment is made explicitly and once, rather than assumed.

Neither check can catch the right type of document about the wrong thing. That is
what the scope check and the audit pass are for.

Exits non-zero on failure.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Only documents the pipeline actually fetches carry these obligations. An entry
# recording that no such document exists ("not_published") governs nothing by
# definition and is exempt.
FETCHABLE = {"verified", "unverified"}

# Set once the backfill is reviewed. Until then the requirement is reported as a
# summary line rather than a failure, because failing the build on 110 documents
# that have not yet been through review would just force the check to be disabled.
REQUIRE_GOVERNS = False


def entry_class(cfg, section):
    return (cfg.get("sections") or {}).get(section)


def main():
    cfg = yaml.safe_load((ROOT / "entry_classes.yaml").read_text(encoding="utf-8"))
    classes = cfg.get("classes") or {}

    # The display section is the authoritative classification. Read it from the
    # built dataset when present, falling back to the segment map, so the lint
    # works on a fresh checkout with no dataset.
    sections = {}
    dataset = ROOT / "data/dataset.json"
    if dataset.exists():
        import json
        for p in json.loads(dataset.read_text()).get("providers", []):
            sections[p["provider"]] = p.get("section")

    registry = yaml.safe_load((ROOT / "registry.yaml").read_text(encoding="utf-8"))

    failures, missing_governs, checked = [], [], 0

    for prov in registry.get("providers", []):
        name = prov.get("provider")
        section = sections.get(name)
        cls = entry_class(cfg, section) if section else None

        for doc in prov.get("documents", []):
            if doc.get("status") not in FETCHABLE:
                continue
            checked += 1
            dt = doc.get("doc_type")

            if cls:
                spec = classes.get(cls) or {}
                permitted = set(spec.get("permitted") or [])
                if dt not in permitted:
                    why = (spec.get("excluded_because") or {}).get(dt, "")
                    failures.append(
                        f"  {name} ({cls}) / {dt}: this entry tracks "
                        f"{spec.get('tracks', cls)}, which a {dt} cannot govern"
                        + (f" -- {why}" if why else "")
                        + f"\n      {doc.get('name') or doc.get('url')}")

            if not (doc.get("governs") or "").strip():
                missing_governs.append(f"{name}/{dt}")

    if failures:
        print("Registry lint FAILED (document type cannot govern this entry):\n")
        print("\n".join(failures))
        print("\nEither the document belongs on a different entry, or this entry "
              "is classified wrongly. Do not add the type to entry_classes.yaml "
              "to make this pass unless the exclusion reasoning is actually wrong.")
        return 1

    if missing_governs:
        line = (f"{len(missing_governs)} of {checked} fetchable documents have no "
                f"`governs` line")
        if REQUIRE_GOVERNS:
            print(f"Registry lint FAILED: {line}.\n")
            for m in missing_governs[:40]:
                print(f"  {m}")
            if len(missing_governs) > 40:
                print(f"  ... and {len(missing_governs) - 40} more")
            print("\nEvery fetchable document must state what it governs and why "
                  "that is this entry's tracked artifact.")
            return 1
        print(f"Registry lint passed ({checked} documents). "
              f"NOTE: {line}; the requirement is staged, not yet enforced.")
        return 0

    print(f"All registry lint checks passed ({checked} fetchable documents, "
          f"all carrying a governs line).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
