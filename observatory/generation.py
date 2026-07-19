"""Detect when an archived document belongs to a different model generation than
the registry entry that points at it.

The Llama case is why this exists: the registry tracked Llama 4, the only readable
capture was the Llama 2 Acceptable Use Policy, and the site published a
high-confidence quote-verified value describing a superseded generation's policy.
Nothing in the pipeline noticed, because every layer was individually correct.

Two design decisions follow from that failure:

1. **Text-based, not keyed to the registry's `generation` field.** That field
   exists on a handful of documents (model licenses), and the Llama mismatch was
   on an acceptable-use policy, which has none. A check keyed to the field would
   have missed the exact case that motivated it. This reads the archived text.

2. **Bidirectional.** A document can be older than the registry label (Llama:
   suppress, the values describe a superseded artifact) or newer (Qwen: the
   registry is behind and should be updated, but the values are not wrong about
   the newer generation). Older and newer are different problems with different
   remedies, so they are reported separately rather than collapsed into "mismatch".

A generic license that names no generation (a bare MIT or Apache-2.0 file) cannot
be checked this way and is not flagged: for those the binding between document and
generation is the repository path, not the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Families whose releases carry a generation number in the document text. The
# pattern captures the number so two references can be ordered.
_FAMILIES = {
    "llama": r"Llama[\s-]*(\d+(?:\.\d+)?)",
    "gemma": r"Gemma[\s-]*(\d+(?:\.\d+)?)",
    "qwen": r"Qwen[\s-]*(\d+(?:\.\d+)?)",
    "glm": r"GLM[\s-]*(\d+(?:\.\d+)?)",
    "minimax": r"MiniMax[\s-]*M(\d+(?:\.\d+)?)",
    "deepseek": r"DeepSeek[\s-]*[RV](\d+(?:\.\d+)?)",
    "kimi": r"Kimi[\s-]*K(\d+(?:\.\d+)?)",
}

# A generation is only credited when the document names it at least this often, so
# a passing mention of an older release in a changelog does not trip the check.
MIN_MENTIONS = 3


@dataclass
class GenerationFinding:
    provider: str
    slug: str
    declared: str
    found: str
    direction: str        # "older" | "newer"
    mentions: int
    action: str           # "suppress" | "flag_registry_update"


def _family_of(label: str) -> Optional[str]:
    low = (label or "").lower()
    return next((f for f in _FAMILIES if f in low), None)


def _number_in(label: str, family: str) -> Optional[float]:
    m = re.search(_FAMILIES[family], label or "", re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


def check(provider: str, slug: str, declared: str, text: str) -> Optional[GenerationFinding]:
    """Compare the generation a document names against the one the registry declares.

    Returns None when there is nothing to say: no family recognized, no generation
    named in the text (a generic license), or the document names the declared
    generation.
    """
    family = _family_of(declared)
    if not family or not text:
        return None
    declared_num = _number_in(declared, family)
    if declared_num is None:
        return None

    counts: dict = {}
    for m in re.finditer(_FAMILIES[family], text, re.I):
        try:
            counts[float(m.group(1))] = counts.get(float(m.group(1)), 0) + 1
        except (TypeError, ValueError):
            continue
    if not counts:
        return None  # generic license: binding is the repo path, not the text
    if declared_num in counts:
        return None  # the document names the generation we track

    # The dominant generation in the text is the one the document is about.
    found_num, mentions = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    if mentions < MIN_MENTIONS:
        return None

    older = found_num < declared_num
    return GenerationFinding(
        provider=provider, slug=slug, declared=declared,
        found=f"{family} {found_num:g}", direction="older" if older else "newer",
        mentions=mentions,
        # Older: the values describe a superseded artifact, so they must not be
        # published. Newer: the values are accurate about a generation we have not
        # caught up to, so the registry is what needs fixing, not the data.
        action="suppress" if older else "flag_registry_update",
    )


def sweep(registry, store) -> List[GenerationFinding]:
    """Run the check across every registered document that has a capture."""
    declared_by_provider = {}
    for d in registry.documents():
        if getattr(d, "generation", None):
            declared_by_provider.setdefault(d.provider, d.generation)

    out: List[GenerationFinding] = []
    for d in registry.documents():
        declared = getattr(d, "generation", None) or declared_by_provider.get(d.provider)
        if not declared:
            continue
        snap = store.latest(d.provider, d.slug)
        if not snap or not snap.text:
            continue
        finding = check(d.provider, d.slug, declared, snap.text)
        if finding:
            out.append(finding)
    return out
