"""Shared helpers for policy change-history enforcement.

The Terms and Privacy pages must never change silently: any edit to their
substantive text requires a new dated entry in that page's change-history list.
This is enforced with a lock file recording, per policy, a hash of the body (the
text above the change history) and the list of dated entries. The build fails if
a body hash no longer matches the lock, and the lock cannot be refreshed for a
changed body unless a new dated entry was added.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_DIR = ROOT / "policies"
LOCK_PATH = POLICY_DIR / "policies.lock.json"
POLICY_FILES = ["terms-of-use.md", "privacy-policy.md"]

_HISTORY_MARKER = "*Change history:*"
_ENTRY = re.compile(r"^\s*-\s*(.+?):", re.M)


def split_policy(md: str):
    """(body, [dated entry labels]). The body is everything before the change
    history; entries are the '- <date>: ...' lines after the marker."""
    idx = md.find(_HISTORY_MARKER)
    if idx == -1:
        return md, []
    body = md[:idx]
    # Trim a trailing horizontal rule that precedes the history.
    body = re.sub(r"\n-{3,}\s*$", "\n", body.rstrip()) + "\n"
    entries = _ENTRY.findall(md[idx:])
    return body, [e.strip() for e in entries]


def body_hash(body: str) -> str:
    # Normalise whitespace so a reflow that changes no words does not trip it,
    # while any wording change does.
    norm = re.sub(r"\s+", " ", body).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def current_state():
    out = {}
    for name in POLICY_FILES:
        md = (POLICY_DIR / name).read_text(encoding="utf-8")
        body, entries = split_policy(md)
        out[name] = {"body_sha256": body_hash(body), "entries": entries}
    return out
