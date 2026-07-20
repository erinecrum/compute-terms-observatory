#!/usr/bin/env python3
"""Every registry document must come from a host its provider controls.

The defect this exists to prevent: minimax/ai_documentation pointed at
minimax-m2.com, a third-party operator's Terms of Service, filed and published as
MiniMax's model card. It survived every existing check because it was plausible.

So this check is not a heuristic. It compares each URL's host against an explicit
per-provider allowlist in provider_domains.yaml, which a person maintains. A new
host fails until someone adds it deliberately, and that edit is the review.

On distribution platforms (huggingface.co and friends) the host is meaningless on
its own, so the first path segment -- the publishing org -- is what gets matched.

Exits non-zero on failure.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent


def norm_host(host):
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def key_for(url, platform_hosts):
    """The allowlist key a URL must match: 'host' or 'host/org'."""
    parsed = urlparse(url)
    host = norm_host(parsed.netloc)
    if host in platform_hosts:
        org = parsed.path.strip("/").split("/")[0]
        return f"{host}/{org}", True
    return host, False


def main():
    cfg = yaml.safe_load((ROOT / "provider_domains.yaml").read_text(encoding="utf-8"))
    allow = cfg.get("providers") or {}
    platform_hosts = {norm_host(h) for h in (cfg.get("platform_hosts") or [])}

    registry = yaml.safe_load((ROOT / "registry.yaml").read_text(encoding="utf-8"))

    failures, checked = [], 0
    seen_providers = set()

    for prov in registry.get("providers", []):
        name = prov.get("provider")
        entry = allow.get(name)
        docs = [d for d in prov.get("documents", []) if d.get("url")]
        if docs:
            seen_providers.add(name)
        if docs and entry is None:
            failures.append(
                f"  {name}: has {len(docs)} document URL(s) but no entry in "
                f"provider_domains.yaml. Add one after checking the hosts are "
                f"the provider's own.")
            continue

        permitted = {norm_host(h) if "/" not in h else h.lower()
                     for h in ((entry or {}).get("hosts") or [])}

        for doc in docs:
            checked += 1
            key, is_platform = key_for(doc["url"], platform_hosts)
            if key.lower() not in permitted:
                where = "org namespace" if is_platform else "host"
                failures.append(
                    f"  {name} / {doc.get('doc_type')}: {where} {key!r} is not "
                    f"listed for this provider.\n"
                    f"      {doc['url']}\n"
                    f"      Permitted: {sorted(permitted) or '(none)'}")

    # A stale allowlist is its own risk: an entry left behind after a source is
    # removed silently re-permits that host for any future edit.
    for name in sorted(set(allow) - seen_providers):
        failures.append(
            f"  {name}: listed in provider_domains.yaml but has no document URLs "
            f"in registry.yaml. Remove the stale entry.")

    if failures:
        print("Provider-domain check FAILED:\n")
        print("\n".join(failures))
        print("\nA document must come from a host its provider controls. If this "
              "host is genuinely the provider's, add it to provider_domains.yaml; "
              "if it is not, the document does not belong in the registry.")
        return 1

    print(f"All provider-domain checks passed ({checked} document URLs across "
          f"{len(seen_providers)} providers).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
