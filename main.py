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

from dotenv import load_dotenv

from observatory.dataset import build_dataset, save_dataset
from observatory.differ import diff_text
from observatory.extractor import extract_provider, save_extraction
from observatory.fetcher import fetch_document
from observatory.registry import load_registry
from observatory.site import render_site
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
        history = store.history(doc.provider, doc.slug)
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


def cmd_extract(providers: List[str]) -> int:
    """Run the Claude API schema extraction for the given providers (or all).
    Needs ANTHROPIC_API_KEY (loaded from .env)."""
    load_dotenv()
    registry = load_registry("registry.yaml")
    store = SnapshotStore("snapshots")

    targets = providers or registry.providers()
    print(f"Extracting {len(targets)} provider(s) with Opus 4.8...\n")
    failed = 0
    for provider in targets:
        try:
            record = extract_provider(provider, registry, store)
            path = save_extraction(record)
            trunc = [d["doc_type"] for d in record["documents_used"] if d["truncated"]]
            low = sum(1 for f in record["fields"].values() if f["confidence"] == "low")
            note = f"  (truncated: {', '.join(trunc)})" if trunc else ""
            print(f"  ✓ {provider:12}  {len(record['fields'])} dims, {low} low-confidence  -> {path}{note}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {provider:12}  {type(exc).__name__}: {exc}")
    print(f"\nDone. {len(targets) - failed} extracted, {failed} failed.")
    return 0 if failed == 0 else 2


def cmd_run(skip_extract: bool) -> int:
    """Full pipeline: fetch every document, snapshot what changed, re-extract only
    the providers whose documents changed, then rebuild the dataset and site.
    This is the weekly-run entry point and the 'one command locally' path."""
    load_dotenv()
    registry = load_registry("registry.yaml")
    store = SnapshotStore("snapshots")

    changed_providers = set()
    fetch_failed = extract_failed = 0
    print("1/4 Fetching + snapshotting changed documents...")
    for doc in registry.documents():
        result = fetch_document(doc)
        if not result.ok:
            fetch_failed += 1
            print(f"     ✗ {doc.doc_id}: {result.error}")
            continue
        if store.save_if_changed(result) is not None:
            changed_providers.add(doc.provider)
            print(f"     ✎ changed: {doc.doc_id}")
    print(f"     {len(changed_providers)} provider(s) changed, {fetch_failed} fetch failure(s).")

    if changed_providers and not skip_extract:
        print(f"2/4 Re-extracting changed providers: {', '.join(sorted(changed_providers))}")
        for provider in sorted(changed_providers):
            try:
                save_extraction(extract_provider(provider, registry, store))
                print(f"     ✓ {provider}")
            except Exception as exc:  # noqa: BLE001
                extract_failed += 1
                print(f"     ✗ {provider}: {type(exc).__name__}: {exc}")
    else:
        print("2/4 No changed providers to re-extract (or extraction skipped).")

    print("3/4 Building dataset...")
    dataset = build_dataset(registry)
    save_dataset(dataset)
    print("4/4 Rendering site...")
    render_site(dataset)
    print("Done.")
    # Transient page-fetch failures don't fail the run (partial corpus update is
    # still useful); an extraction (API) failure does, so it's visible in CI.
    return 0 if extract_failed == 0 else 2


def cmd_build() -> int:
    """Assemble the comparison dataset from extractions + overrides + programs."""
    dataset = build_dataset()
    path = save_dataset(dataset)
    n_prov = len(dataset["providers"])
    n_dim = len(dataset["dimensions"])
    n_chg = len(dataset["change_log"])
    print(f"Built dataset -> {path}  ({n_prov} providers, {n_dim} dimensions, {n_chg} change-log entries)")
    return 0


def cmd_site() -> int:
    """Build the dataset, then render the static site."""
    dataset = build_dataset()
    save_dataset(dataset)
    written = render_site(dataset)
    for p in written:
        print(f"  wrote {p}")
    print(f"\nSite rendered. Open {written[0]} in a browser.")
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

    p_extract = sub.add_parser(
        "extract", help="run the Claude API schema extraction (needs ANTHROPIC_API_KEY)"
    )
    p_extract.add_argument("--provider", action="append", default=[])

    sub.add_parser("build", help="assemble the comparison dataset (data/dataset.json)")
    sub.add_parser("site", help="build the dataset and render the static site into site/")
    p_run = sub.add_parser("run", help="full pipeline: fetch -> re-extract changed -> build -> site")
    p_run.add_argument("--skip-extract", action="store_true",
                       help="skip the Claude API step (rebuild dataset/site only)")

    args = parser.parse_args()
    if args.command == "fetch":
        return cmd_fetch(args.provider)
    if args.command == "changes":
        return cmd_changes(args.provider)
    if args.command == "extract":
        return cmd_extract(args.provider)
    if args.command == "build":
        return cmd_build()
    if args.command == "site":
        return cmd_site()
    if args.command == "run":
        return cmd_run(args.skip_extract)
    parser.error(f"unknown command {args.command!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
