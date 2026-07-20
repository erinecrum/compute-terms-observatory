"""Read each document's own statement of what it governs, and compare it to the
entry it sits on.

Most legal documents declare their own scope in the opening paragraph: "These
Terms govern your access to and use of the ... website, dashboard and APIs."
That sentence is the document telling you what it is. When it describes a hosted
service and it is sitting on an entry that tracks downloadable weights, something
is wrong -- either the document does not belong there, or the entry is
misclassified.

This is exactly what would have caught minimax-m2.com. Its first paragraph reads
"govern access to and use of the MiniMax-M2 website, dashboard, chat interface,
APIs", on an entry tracking a downloadable model. No name matching required; the
document says what it is.

FLAGS ONLY. Nothing here suppresses a value, changes a status, or edits the
registry. Scope language is written by lawyers for their own purposes and is
routinely broader or narrower than the thing at hand; a flag is a prompt to look,
never a finding. The output goes to the build report.
"""

from __future__ import annotations

import re

# How far into a document to look. Scope statements live in the opening; reading
# further picks up incidental mentions of every other product the company sells.
_HEAD_CHARS = 2500

# The sentence that declares scope. Deliberately narrow: we want the document's
# own "this governs X" statement, not any sentence containing "services".
_SCOPE_PATTERNS = (
    r"(?:these|this)\s+(?:terms|agreement|policy|licen[cs]e|addendum)[^.]{0,80}?"
    r"\b(?:govern|appl(?:y|ies)|cover)\w*\b[^.]{0,300}\.",
    r"\bgovern(?:s)?\s+(?:your\s+)?(?:access\s+to\s+and\s+use\s+of|use\s+of)[^.]{0,300}\.",
)

# Vocabulary that marks a scope statement as describing an operated service. A
# document that speaks of accounts, dashboards and APIs is describing something a
# user connects to.
_SERVICE_WORDS = (
    "website", "web site", "dashboard", "platform", "api", "apis", "console",
    "account", "subscription", "hosted", "online service", "our services",
    "chat interface", "portal", "sign up", "register",
)

# Vocabulary that marks a scope statement as describing a distributed artifact.
_ARTIFACT_WORDS = (
    "software", "model weights", "the weights", "source code", "copy of the",
    "derivative works", "redistribut", "this licen", "the work",
)


def scope_sentence(text: str) -> str:
    """The document's own statement of what it governs, if it makes one."""
    head = " ".join((text or "")[:_HEAD_CHARS].split())
    for pattern in _SCOPE_PATTERNS:
        m = re.search(pattern, head, re.I)
        if m:
            return m.group(0).strip()
    return ""


def _hits(sentence: str, words) -> list:
    low = sentence.lower()
    return sorted({w for w in words if w in low})


def classify_scope(sentence: str) -> str:
    """'service', 'artifact', 'both' or '' from the scope sentence alone."""
    if not sentence:
        return ""
    svc, art = _hits(sentence, _SERVICE_WORDS), _hits(sentence, _ARTIFACT_WORDS)
    if svc and art:
        return "both"
    if svc:
        return "service"
    if art:
        return "artifact"
    return ""


# What each entry class expects a governing document's scope to describe. "hosted"
# and "infrastructure" both operate a service; only weights entries do not.
_EXPECTED = {"weights": "artifact", "hosted": "service", "infrastructure": "service"}


def check(text: str, entry_class: str, doc_type: str) -> dict | None:
    """Compare a document's self-declared scope to the entry it sits on.

    Returns a flag dict when they disagree, else None. A document that declares
    no scope, or declares both, is not flagged: the check reports disagreement,
    not absence of evidence.
    """
    expected = _EXPECTED.get(entry_class)
    if not expected:
        return None
    sentence = scope_sentence(text)
    found = classify_scope(sentence)
    if not found or found == "both" or found == expected:
        return None
    # A model card is descriptive documentation rather than a governing
    # instrument, and routinely describes the publisher's hosted API alongside
    # the weights. Flagging every one of those is noise that would bury the
    # signal this check exists for.
    if doc_type == "ai_documentation":
        return None
    return {
        "expected": expected,
        "found": found,
        "scope_sentence": sentence[:300],
        "service_words": _hits(sentence, _SERVICE_WORDS),
        "artifact_words": _hits(sentence, _ARTIFACT_WORDS),
    }
