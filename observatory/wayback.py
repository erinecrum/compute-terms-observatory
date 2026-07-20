"""Look up whether the Internet Archive holds a capture near a given date.

This is corroboration, not a source. A reader who does not want to take the
Observatory's word for what a document said can compare our capture against an
independent third party's. Nothing here is fetched into the corpus and nothing is
extracted from: the only call is to the availability API, which answers "is there a
capture near this timestamp" and returns its URL.

If no capture exists reasonably near the change, no link is emitted. A link to a
capture months away from the change would look like corroboration while
corroborating nothing, which is worse than an absent link.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

# A capture further from the change than this is not evidence about the change.
MAX_DISTANCE_DAYS = 45
_TIMEOUT = 15
_UA = ("ComputeTermsObservatory/1.0 "
       "(+https://github.com/erinecrum/compute-terms-observatory; availability check)")

_CACHE: dict = {}


def _parse(ts: str) -> Optional[datetime]:
    for fmt in ("%Y%m%d%H%M%S",):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    try:
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def nearest_capture(url: str, when: str, direction: str) -> Optional[str]:
    """URL of the closest Internet Archive capture before/after `when`, or None.

    `direction` is "before" or "after". Returns None when the archive holds nothing,
    when the nearest capture is further away than MAX_DISTANCE_DAYS, or when the
    lookup fails for any reason: corroboration is a bonus, never a build dependency.
    """
    target = _parse(when)
    if not url or not target:
        return None
    stamp = target.strftime("%Y%m%d%H%M%S")
    key = (url, stamp, direction)
    if key in _CACHE:
        return _CACHE[key]

    api = (f"http://archive.org/wayback/available?url={quote(url, safe='')}"
           f"&timestamp={stamp}")
    result = None
    try:
        req = Request(api, headers={"User-Agent": _UA})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        snap = ((data.get("archived_snapshots") or {}).get("closest") or {})
        if snap.get("available") and snap.get("timestamp") and snap.get("url"):
            got = _parse(snap["timestamp"])
            if got:
                delta = got - target
                right_side = delta <= timedelta(0) if direction == "before" else delta >= timedelta(0)
                if right_side and abs(delta) <= timedelta(days=MAX_DISTANCE_DAYS):
                    result = snap["url"]
    except Exception:  # noqa: BLE001 - availability is best-effort by design
        result = None

    _CACHE[key] = result
    return result
