#!/usr/bin/env python3
"""The Terms and Privacy pages may not change silently.

Fails the build if a policy's body no longer matches policies.lock.json, or if a
change history is empty or still contains an unfilled [DATE]. A legitimate edit
adds a dated change-history entry and refreshes the lock via
scripts/update_policy_lock.py; without both, the build breaks.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_lock import LOCK_PATH, current_state, POLICY_FILES  # noqa: E402


def main():
    if not LOCK_PATH.exists():
        print("policies.lock.json is missing; run scripts/update_policy_lock.py.")
        return 1
    lock = json.loads(LOCK_PATH.read_text())
    cur = current_state()
    fails = []
    for name in POLICY_FILES:
        c = cur[name]
        rec = lock.get(name)
        if not rec:
            fails.append(f"  {name}: not recorded in the lock.")
            continue
        if not c["entries"] or "[DATE]" in "".join(c["entries"]):
            fails.append(f"  {name}: change history is empty or has an unfilled [DATE].")
        if c["body_sha256"] != rec["body_sha256"]:
            fails.append(f"  {name}: body changed since the lock. Append a dated "
                         f"change-history entry and run scripts/update_policy_lock.py.")
        if c["entries"] != rec["entries"]:
            fails.append(f"  {name}: change-history entries differ from the lock; "
                         f"run scripts/update_policy_lock.py.")
    if fails:
        print("Policy-integrity check FAILED:\n" + "\n".join(fails))
        return 1
    print(f"All policy-integrity checks passed ({len(POLICY_FILES)} pages match the "
          f"lock; change histories dated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
