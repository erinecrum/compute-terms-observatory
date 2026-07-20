"""Does the capture mention the thing it is supposed to be about?

The class of defect this catches: a capture that is a real page, fetched cleanly,
of adequate length, from the right domain -- and the wrong page. Qwen's
ai_documentation was captured from the Hugging Face org landing page: 2,889
characters of activity feed, HTTP 200, correct host, correct org namespace. Every
provenance and floor check passed, because every one of them was satisfied. It
simply was not the model card.

The cheap fingerprint is that a model card or a licence for a tracked model will
mention that model somewhere. An org activity feed does not. This costs one
substring search and would have caught it.

DELIBERATELY NARROW. Applies only to ai_documentation and model_license, the two
types bound to a specific named artifact. A service agreement has no reason to
name a model, and demanding one would produce noise. Flags to the build report;
never suppresses. Publishers do rename things, and a licence file can be a bare
MIT text that names nothing -- which is why the generation check exists and why
this one only flags.
"""

from __future__ import annotations

import re

# Only these two types are bound to a named artifact.
_APPLIES_TO = {"ai_documentation", "model_license"}

# A bare permissive licence names no model by design. Recognising them avoids
# flagging every MIT and Apache file in the corpus for saying nothing specific.
_GENERIC_LICENCE = re.compile(
    r"\bMIT License\b|\bApache License\b|\bBSD\b|\bGNU GENERAL PUBLIC\b", re.I)


def _tokens(name: str) -> list:
    """Identifying fragments of a model or family name, longest first.

    "Qwen3-235B-A22B" yields the whole string plus "Qwen3" and "Qwen", so a card
    for a sibling checkpoint in the same family still matches. Pure version
    numbers are dropped: "3" matching is meaningless.
    """
    name = (name or "").strip()
    if not name:
        return []
    out = {name}
    for part in re.split(r"[\s/_-]+", name):
        if len(part) >= 3 and not part.isdigit():
            out.add(part)
    # "Qwen3" -> "Qwen", "GLM-5.2" -> "GLM": the family without the version.
    for part in list(out):
        stem = re.match(r"^([A-Za-z][A-Za-z]+)", part)
        if stem and len(stem.group(1)) >= 3:
            out.add(stem.group(1))
    return sorted(out, key=len, reverse=True)


def check(text: str, doc_type: str, *, model_name: str, generation: str = "",
          provider_name: str = "") -> dict | None:
    """Flag when a capture never names the artifact it is supposed to document.

    Returns a flag dict, or None when it matches, does not apply, or cannot be
    judged.
    """
    if doc_type not in _APPLIES_TO or not text:
        return None

    head = text[:40000]

    # Where the entry declares a generation, require THAT, not a family fragment.
    #
    # This is the whole lesson of the Qwen miss. The bad capture was the Hugging
    # Face org landing page, which is wall-to-wall "Qwen": Qwen3.6-27B,
    # Qwen3.5-0.8B, Qwen/AgentWorldBench. A family-name check matched happily and
    # saw nothing wrong. The one string the org feed did NOT contain was the
    # specific checkpoint the entry tracks. Precision is the entire value here;
    # a looser match reproduces the defect it is meant to catch.
    if generation:
        # Publishers punctuate inconsistently: Qwen3-235B-A22B, Qwen3 235B A22B.
        loose = r"[\s_-]*".join(re.escape(p) for p in re.split(r"[\s_-]+", generation.strip()) if p)
        if loose and re.search(loose, head, re.I):
            return None
        candidates = [generation]
    else:
        candidates = [c for c in dict.fromkeys(
            _tokens(model_name) + _tokens(provider_name)) if len(c) >= 3]
        if not candidates:
            return None
        for token in candidates:
            if re.search(re.escape(token), head, re.I):
                return None

    # A bare standard licence naming nothing is expected, not a defect.
    if doc_type == "model_license" and _GENERIC_LICENCE.search(text[:2000]):
        return None

    return {
        "reason": "capture never names the tracked model or family",
        "looked_for": candidates[:6],
        "chars": len(text),
        "excerpt": " ".join(text[:220].split()),
    }
