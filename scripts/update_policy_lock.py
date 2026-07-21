#!/usr/bin/env python3
"""Refresh policies/policies.lock.json after a reviewed policy edit.

Refuses to update when a policy's body changed but no new dated change-history
entry was added, so the only way to change these pages is to record the change.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_lock import LOCK_PATH, current_state, POLICY_FILES  # noqa: E402


def main():
    cur = current_state()
    old = {}
    if LOCK_PATH.exists():
        old = json.loads(LOCK_PATH.read_text())
    errors = []
    for name in POLICY_FILES:
        c, o = cur[name], old.get(name)
        if not o:
            continue  # first time
        if c["body_sha256"] != o["body_sha256"] and len(c["entries"]) <= len(o["entries"]):
            errors.append(f"  {name}: body changed but no new dated change-history "
                          f"entry was added ({len(o['entries'])} -> {len(c['entries'])}).")
        if "[DATE]" in "".join(c["entries"]) or not c["entries"]:
            errors.append(f"  {name}: change history is empty or has an unfilled [DATE].")
    if errors:
        print("Refusing to update the policy lock:\n" + "\n".join(errors))
        print("\nAppend a dated entry to the page's change history describing the edit, "
              "then run this again.")
        return 1
    LOCK_PATH.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    print(f"policies.lock.json updated ({', '.join(POLICY_FILES)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
