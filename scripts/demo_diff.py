"""Demonstrate the differ on real legal text — a SIMULATED upstream change.

We take the real AWS Compute SLA snapshot, make an in-memory copy with two
commitment percentages edited (as if AWS quietly weakened the SLA), and run the
differ. This proves the engine isolates the exact changed clause without touching
the real corpus. Run: python scripts/demo_diff.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from observatory.differ import diff_text
from observatory.snapshot import SnapshotStore


def main() -> int:
    store = SnapshotStore("snapshots")
    latest = store.latest("aws", "sla")
    if latest is None or not latest.text:
        print("No aws/sla snapshot found — run `python main.py fetch --provider aws` first.")
        return 1

    original = latest.text
    # Simulate a quiet downgrade of the two headline commitments.
    edited = original.replace("99.99%", "99.9%").replace("99.5%", "99.0%")

    if edited == original:
        print("Expected commitment percentages not found in the snapshot; "
              "the SLA page wording may have changed. Demo inconclusive.")
        return 1

    print("Simulated edit: 99.99% → 99.9%  and  99.5% → 99.0%  in the AWS Compute SLA.\n")

    d = diff_text(original, edited)
    print(f"has_changes = {d.has_changes}")
    print(f"lines: +{d.added_lines} / -{d.removed_lines}, {len(d.blocks)} localized block(s)\n")
    for i, b in enumerate(d.blocks, 1):
        print(f"Block {i}:")
        print(f"  OLD: “{b.old_focus}”")
        print(f"  NEW: “{b.new_focus}”\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
