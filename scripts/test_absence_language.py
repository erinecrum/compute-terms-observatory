#!/usr/bin/env python3
"""No user-facing surface may display a bare status word.

"Silent" reads as a judgment about the provider. "Not applicable" reads as a gap
in our coverage. "Not retrievable" reads as something broken. Each is a code word
standing in for a finding the reader cannot see, so every absence renders as a
sentence saying what was reviewed and why no term is reported.

This guards the property, not the wording: the sentences live in
absence_language.yaml and are meant to be edited. What must not come back is a
cell that shows only a status word.

Checks the built dataset (which every surface reads) and the rendered HTML.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BARE = {"silent", "not applicable", "not specified", "n/a", "na",
        "not retrievable", "access restricted by provider", "unspecified"}

ABSENCE = {"no_clause_found", "not_applicable", "access_restricted", "not_retrievable"}


def main():
    fails = []

    data = json.loads((ROOT / "data/dataset.json").read_text())
    checked = 0
    for provider, fields in data.get("matrix", {}).items():
        for dim, f in (fields or {}).items():
            if not f or f.get("status") not in ABSENCE:
                continue
            checked += 1
            shown = (f.get("display_value") or "").strip()
            if shown.lower() in BARE:
                fails.append(f"  {provider}/{dim}: display_value is the bare word {shown!r}")
            if not f.get("absence_full"):
                fails.append(f"  {provider}/{dim}: no absence sentence was built")
            elif len(f["absence_full"].split()) < 5:
                fails.append(f"  {provider}/{dim}: absence sentence is not a sentence: "
                             f"{f['absence_full']!r}")

    index = ROOT / "site/index.html"
    if index.exists():
        html = index.read_text()
        # Status badges and the status aria-labels must never carry the internal
        # enum vocabulary; they route through display_strings now. (The word may
        # still appear inside a model-written VALUE, e.g. "silent on benchmarking",
        # which is substantive content, not a status label, so only badges and
        # status labels are checked.)
        badges = re.findall(r'<span class="badge[^"]*">([^<]*)</span>', html)
        labels = re.findall(r'aria-label="Status: ([^"]*)"', html)
        for text in badges + labels:
            for word in ("silent", "unverified"):
                if re.search(rf"\b{word}\b", text, re.I):
                    fails.append(f"  a status badge/label renders the internal word "
                                 f"{word!r}: {text!r}")

    if fails:
        print("Absence-language check FAILED:\n")
        print("\n".join(fails[:30]))
        print("\nEvery absence must render as a sentence saying what was reviewed. "
              "Edit absence_language.yaml to change the wording; do not reintroduce "
              "a bare status word.")
        return 1

    print(f"All absence-language checks passed ({checked} absence cells, "
          f"none showing a bare status word).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
