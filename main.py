"""Compute Contract Terms Observatory — command-line runner.

Subcommands (more added as the build progresses):

    python main.py fetch                 # fetch + snapshot every registry document
    python main.py fetch --provider aws --provider azure   # only these providers

The fetch layer needs no API key: it archives public documents and records new
versions. Extraction (which does need a key) comes in a later build step.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from observatory.differ import diff_text
from observatory.fetcher import fetch_document
from observatory.registry import load_registry
from observatory.snapshot import SnapshotStore


def cmd_fetch(providers: List[str]) -> int:
    registry = load_registry("registry.yaml")
    store = SnapshotStore("snapshots")

    docs = registry.documents()
    if providers:
        wanted = set(providers)
        docs = [d for d in docs if d.provider in wanted]
        if not docs:
            print(f"No registry documents match providers: {', '.join(providers)}")
            return 1

    saved = unchanged = failed = 0
    print(f"Fetching {len(docs)} document(s)...\n")
    for doc in docs:
        result = fetch_document(doc)
        if not result.ok:
            failed += 1
            print(f"  ✗ FAIL  {doc.doc_id:32}  {result.error}")
            continue
        path = store.save_if_changed(result)
        if path is None:
            unchanged += 1
            print(f"  ·  same  {doc.doc_id:32}  {result.char_count:>7,} chars")
        else:
            saved += 1
            print(f"  ✓ SNAP  {doc.doc_id:32}  {result.char_count:>7,} chars  -> {path}")

    print(
        f"\nDone. {saved} new snapshot(s), {unchanged} unchanged, {failed} failed."
    )
    return 0 if failed == 0 else 2


def cmd_changes(providers: List[str]) -> int:
    """Report, for every document, the change between its two most recent
    snapshots. A document with a single snapshot is a baseline (nothing to
    report). This is the raw material for the change feed."""
    registry = load_registry("registry.yaml")
    store = SnapshotStore("snapshots")

    docs = registry.documents()
    if providers:
        wanted = set(providers)
        docs = [d for d in docs if d.provider in wanted]

    changed = baseline = 0
    for doc in docs:
        history = store.history(doc.provider, doc.doc_type)
        if len(history) < 2:
            baseline += 1
            print(f"  ·  base  {doc.doc_id:32}  {len(history)} snapshot(s) — baseline, nothing to report")
            continue
        prev, curr = history[-2], history[-1]
        d = diff_text(prev.text, curr.text)
        if not d.has_changes:
            baseline += 1
            continue
        changed += 1
        print(
            f"  ✎ CHG   {doc.doc_id:32}  +{d.added_lines}/-{d.removed_lines} lines, "
            f"{len(d.blocks)} block(s)  [{prev.stamp} → {curr.stamp}]"
        )
        for i, b in enumerate(d.blocks[:3], 1):
            print(f"        block {i}: OLD “{b.old_focus}”")
            print(f"                 NEW “{b.new_focus}”")

    print(f"\n{changed} document(s) with detected changes, {baseline} baseline/unchanged.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="observatory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="fetch and snapshot registry documents")
    p_fetch.add_argument(
        "--provider",
        action="append",
        default=[],
        help="limit to this provider slug (repeatable)",
    )

    p_changes = sub.add_parser(
        "changes", help="report changes between the two latest snapshots per document"
    )
    p_changes.add_argument("--provider", action="append", default=[])

    args = parser.parse_args()
    if args.command == "fetch":
        return cmd_fetch(args.provider)
    if args.command == "changes":
        return cmd_changes(args.provider)
    parser.error(f"unknown command {args.command!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
