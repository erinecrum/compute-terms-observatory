#!/usr/bin/env python3
"""No generated page may load a resource from a third-party origin.

The privacy policy states the site makes no requests to any third-party domain.
The CSP (default-src 'none') enforces this in the browser, but a policy claim
that rests only on a runtime header is one stray <script src> or @font-face url()
away from being false in the HTML while still "passing" until someone loads the
page. This checks the generated HTML directly, so a commit that references an
external origin in any resource-loading context fails the build.

RESOURCE-LOADING contexts only. An <a href="https://aws.amazon.com/..."> is a link
the reader may click, not an automatic request, and the site is full of them
(every value cites its source). Those are not flagged. What is flagged: script
src, fetching <link> (stylesheet, preload, prefetch, preconnect, dns-prefetch,
icon, manifest), img/iframe/source/embed/object, SVG <use>, and url() inside a
<style> block, when they point at an absolute non-self origin.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

SELF_HOSTS = {"termsobservatory.org", "www.termsobservatory.org"}
FETCHING_REL = {"stylesheet", "preload", "prefetch", "preconnect", "dns-prefetch",
                "icon", "apple-touch-icon", "manifest", "prerender", "modulepreload"}


def is_external(url: str) -> bool:
    """True only for an absolute URL to a host that is not self. Relative paths and
    data:/about: URIs make no third-party request and are allowed."""
    url = url.strip()
    if not url or url.startswith(("data:", "about:", "#", "mailto:", "/", "./", "../")):
        return False
    p = urlparse(url)
    if p.scheme in ("http", "https") and p.netloc:
        return p.netloc.lower() not in SELF_HOSTS
    if url.startswith("//"):  # protocol-relative
        return urlparse("https:" + url).netloc.lower() not in SELF_HOSTS
    return False


def scan(html: str):
    hits = []
    # script src / img / iframe / source / embed / object data / video / audio
    for m in re.finditer(r'<(?:script|img|iframe|source|embed|video|audio)\b[^>]*?\b(?:src|data)\s*=\s*["\']([^"\']+)["\']', html, re.I):
        if is_external(m.group(1)):
            hits.append(("resource src", m.group(1)))
    # srcset (may hold several URLs)
    for m in re.finditer(r'\bsrcset\s*=\s*["\']([^"\']+)["\']', html, re.I):
        for part in m.group(1).split(","):
            url = part.strip().split(" ")[0]
            if is_external(url):
                hits.append(("srcset", url))
    # SVG <use href> / xlink:href
    for m in re.finditer(r'<use\b[^>]*?\b(?:xlink:href|href)\s*=\s*["\']([^"\']+)["\']', html, re.I):
        if is_external(m.group(1)):
            hits.append(("svg use", m.group(1)))
    # fetching <link> elements: check rel and href together
    for m in re.finditer(r'<link\b[^>]*>', html, re.I):
        tag = m.group(0)
        rel = re.search(r'\brel\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        href = re.search(r'\bhref\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if rel and href and is_external(href.group(1)):
            if set(rel.group(1).lower().split()) & FETCHING_REL:
                hits.append((f"link rel={rel.group(1)}", href.group(1)))
    # url(...) inside <style> blocks (fonts, backgrounds)
    for style in re.findall(r'<style\b[^>]*>(.*?)</style>', html, re.S | re.I):
        for m in re.finditer(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)', style, re.I):
            if is_external(m.group(1)):
                hits.append(("css url()", m.group(1)))
    return hits


def main():
    pages = sorted(SITE.glob("*.html"))
    if not pages:
        print("No built pages found; run `python main.py site` first.")
        return 1
    failures = []
    for page in pages:
        for ctx, url in scan(page.read_text(encoding="utf-8")):
            failures.append(f"  {page.name}: {ctx} -> {url}")
    if failures:
        print("External-request check FAILED (a page loads a third-party resource):\n")
        print("\n".join(failures[:40]))
        print("\nThe site must make no third-party requests. Inline the resource, "
              "self-host it, or embed it as a data: URI.")
        return 1
    print(f"All external-request checks passed ({len(pages)} pages; no page loads a "
          f"resource from any origin other than the site itself).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
