"""Adversarial review of whether each document governs what its entry tracks.

The governing-document rule is a legal judgment, so it cannot be tested. The
mechanical layers around it (doc type versus entry class, scope-clause
comparison) catch category errors and self-contradicting documents. What they
cannot catch is the right kind of document about the wrong thing: a service
agreement on a hosted entry that governs a product this entry does not track
passes every mechanical check cleanly.

This pass exists for that gap. For each document it asks the model to do two
things:

  1. State whether the document governs the entry's tracked artifact.
  2. Argue the strongest case that it does NOT.

The second half is the point. Asking "does this govern?" invites agreement, and a
model asked to confirm will confirm. Requiring the counter-argument means the
best objection is written down even when the conclusion is that the document is
fine, so a reviewer sees the strongest reason to look rather than a reassurance.

THIS PASS NEVER SUPPRESSES OR MODIFIES ANYTHING. It writes a triage report. Every
disposition is the reviewer's. That is deliberate: a model's opinion about which
instrument governs an artifact is not a basis on which to withdraw a published
value, and wiring it to do so would make the site's claims turn on an
unreviewable judgment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

MODEL = "claude-opus-4-8"

# Enough of the document to see what it declares itself to govern, without paying
# for the whole corpus. Scope statements live at the front; definitions and
# schedules at the back rarely change the answer.
_DOC_CHARS = 6000

REPORT_PATH = Path("data/governance_audit.json")


@dataclass
class Finding:
    provider: str
    doc_type: str
    name: str
    url: str
    entry_class: str
    tracked: str
    governs: str            # "yes" | "no" | "partly"
    confidence: str         # "high" | "medium" | "low"
    basis: str              # one sentence: what it governs and why that is this artifact
    strongest_objection: str
    contested: bool         # needs review: not a clean high-confidence yes


_PROMPT = """You are auditing a legal-research registry for a specific defect.

The registry pairs each tracked artifact with the documents that govern it. The \
defect is a document that does not govern the artifact its entry tracks. This has \
happened twice in real data: a consumer platform's privacy policy filed against a \
set of downloadable model weights (running weights you downloaded creates no \
data-processing relationship with the publisher), and a third-party reseller's \
terms of service filed as a model publisher's own model card.

ENTRY
  provider:        {provider}
  entry class:     {entry_class}
  this entry tracks: {tracked}

DOCUMENT
  type:  {doc_type}
  name:  {name}
  url:   {url}

DOCUMENT TEXT (opening {n} characters)
---
{text}
---

Answer in this exact JSON shape and nothing else:

{{
  "governs": "yes" | "no" | "partly",
  "confidence": "high" | "medium" | "low",
  "basis": "<one sentence: what this document governs, and why that is or is not \
the artifact this entry tracks>",
  "strongest_objection": "<the strongest case that this document does NOT govern \
the tracked artifact, stated as forcefully as it can honestly be put, even if you \
concluded it does govern. If the objection is genuinely weak, say so and say why.>"
}}

Judge the document by what it says about its own scope, not by who published it. \
Sharing a publisher is not sufficient: the question is whether this instrument \
binds a reader with respect to this artifact. Answer "partly" where the document \
governs the artifact only in part, or governs it alongside other things."""


def _client():
    from anthropic import Anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=key)


def audit_document(client, *, provider, doc_type, name, url, entry_class,
                   tracked, text) -> Optional[Finding]:
    prompt = _PROMPT.format(
        provider=provider, entry_class=entry_class, tracked=tracked,
        doc_type=doc_type, name=name or "(unnamed)", url=url or "(no url)",
        n=_DOC_CHARS, text=(text or "")[:_DOC_CHARS])

    resp = client.messages.create(
        model=MODEL, max_tokens=1200,
        messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])
    except (ValueError, json.JSONDecodeError):
        # An unparseable answer is itself worth review rather than a silent skip.
        data = {"governs": "partly", "confidence": "low",
                "basis": "the audit response could not be parsed",
                "strongest_objection": raw[:500]}

    governs = str(data.get("governs", "partly")).lower()
    confidence = str(data.get("confidence", "low")).lower()
    return Finding(
        provider=provider, doc_type=doc_type, name=name or "", url=url or "",
        entry_class=entry_class, tracked=tracked,
        governs=governs, confidence=confidence,
        basis=str(data.get("basis", ""))[:500],
        strongest_objection=str(data.get("strongest_objection", ""))[:800],
        # Anything that is not a confident yes goes to the reviewer. The pass is
        # tuned to over-refer: a false referral costs a minute, a missed one
        # publishes a wrong document under a provider's name.
        contested=not (governs == "yes" and confidence == "high"),
    )


def write_report(findings: List[Finding], scanned: int) -> Path:
    contested = [f for f in findings if f.contested]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "scanned": scanned,
        "contested": len(contested),
        "note": ("Adversarial review of the governing-document rule. For each "
                 "document the model states whether it governs the entry's tracked "
                 "artifact and argues the strongest case that it does not. "
                 "TRIAGE ONLY: nothing here suppresses, modifies or withdraws "
                 "anything, and no disposition is made without a human. A model's "
                 "view of which instrument governs an artifact is a prompt to "
                 "look, not a finding."),
        "triage": [asdict(f) for f in contested],
        "clean": [{"provider": f.provider, "doc_type": f.doc_type,
                   "basis": f.basis} for f in findings if not f.contested],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return REPORT_PATH
