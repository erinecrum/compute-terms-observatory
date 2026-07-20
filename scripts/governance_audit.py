#!/usr/bin/env python3
"""Run the adversarial governing-document audit over the registry.

    python scripts/governance_audit.py                  # every fetchable document
    python scripts/governance_audit.py --provider glm   # one entry
    python scripts/governance_audit.py --limit 5        # a sample

Writes data/governance_audit.json. Never modifies the registry, the corpus, the
dataset or the site: the output is a triage list for a person to work through.

Exit code is 0 even when documents are contested. A contested document is a
prompt to look, not a build failure, and making it one would create pressure to
tune the audit until it stops objecting.
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from observatory.governance import audit_document, write_report, _client  # noqa: E402
from observatory.registry import load_registry  # noqa: E402
from observatory.schema import section_of  # noqa: E402
from observatory.snapshot import SnapshotStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", action="append", help="limit to these providers")
    ap.add_argument("--limit", type=int, help="stop after N documents")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be audited, make no API calls")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "entry_classes.yaml").read_text(encoding="utf-8"))
    sections, classes = cfg.get("sections") or {}, cfg.get("classes") or {}

    registry = load_registry()
    store = SnapshotStore()

    queue = []
    for doc in registry.fetchable():
        if args.provider and doc.provider not in args.provider:
            continue
        cls = sections.get(section_of(doc.provider, doc.segment, doc.openness) or "")
        if not cls:
            continue
        snap = store.current(doc.provider, doc.slug)
        if not snap or not snap.text:
            continue
        queue.append((doc, cls, snap.text))
        if args.limit and len(queue) >= args.limit:
            break

    if args.dry_run:
        print(f"{len(queue)} document(s) would be audited:")
        for doc, cls, _ in queue:
            print(f"  {doc.provider:20} {doc.doc_type:20} ({cls})")
        return 0

    client = _client()
    findings = []
    for i, (doc, cls, text) in enumerate(queue, 1):
        tracked = (classes.get(cls) or {}).get("tracks", cls)
        print(f"  [{i}/{len(queue)}] {doc.provider}/{doc.doc_type} ...", flush=True)
        f = audit_document(
            client, provider=doc.provider, doc_type=doc.doc_type, name=doc.name,
            url=doc.url, entry_class=cls, tracked=tracked, text=text)
        if f:
            findings.append(f)
            if f.contested:
                print(f"        CONTESTED governs={f.governs} "
                      f"confidence={f.confidence}: {f.basis[:110]}")

    path = write_report(findings, scanned=len(queue))
    contested = sum(1 for f in findings if f.contested)
    print(f"\n{len(findings)} audited, {contested} for review -> {path}")
    if contested:
        print("Contested documents are candidates, not defects. Each needs a human "
              "disposition; nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
