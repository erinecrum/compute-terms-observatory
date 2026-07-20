#!/usr/bin/env python3
"""Enforce the four-corners rule on licence_silence.yaml.

These lines are published as statements about what a licence document says. The
failure mode is subtle: a sentence can read as a factual description of an
instrument while actually asserting something about a company's operations, or
quietly assuming the reader self-hosts, or stating a legal conclusion the text
does not support. All three shipped in the first draft and survived a manual
read.

Two checks:

  A. WORDING. Each reason must describe the instrument. Operational verbs about
     the licensor, access-mode assumptions, and unsupported legal conclusions are
     rejected by pattern.

  B. TEXT. Each "contains no ..." claim is probed against the actual licence text
     of every provider carrying that form. A hit means the claim is falsified by
     the document and an override is required. This is what caught Apache-2.0's
     patent-retaliation termination clause and its section 9 indemnity.

Run after any edit to licence_silence.yaml. Exits non-zero on failure.
"""

import glob
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# --- Check A: wording -------------------------------------------------------

# Verbs that describe a licensor's conduct rather than a document's contents.
# "MIT engages no sub-processors" is a claim about a company, not about MIT.
# Note the verb forms: "transfer" and "process" are also nouns that appear
# legitimately ("contains no data transfer provision"), so only the inflected
# verb forms are banned. The explicit "licensor" ban catches the rest.
OPERATIONAL = re.compile(
    r"\blicensor\b|"
    r"\b(?:holds?|receives?|engages?|retains?|collects?|stores?)\b|"
    r"\b(?:transfers|transferring|processes|processing|discloses|disclosing)\b",
    re.I,
)

# Phrasings that presume the reader self-hosts. Whether access is self-hosted or
# hosted is segment-level; these lines may not assume it.
ACCESS_ASSUMPTION = re.compile(
    r"\byou run yourself\b|\bself-?hosted?\b|\bhosted processing\b|"
    r"\ba copy you\b|\bno service\b|\binvolves no\b",
    re.I,
)

# "Perpetual" and "irrevocable" are permitted only as quoted licence text.
CONCLUSION = re.compile(r"\b(perpetual|irrevocable)\b", re.I)


def check_wording(reasons, overrides, bespoke):
    bad = []
    lines = [("reasons", k, v) for k, v in reasons.items()]
    for form, ov in overrides.items():
        lines += [(f"overrides.{form}", k, v) for k, v in ov.items()]
    # The bespoke prose is published the same way and is held to the same rule.
    for key in ("reason", "note"):
        if bespoke.get(key):
            lines.append(("bespoke", key, bespoke[key]))

    for where, key, text in lines:
        t = " ".join(str(text).split())
        if OPERATIONAL.search(t):
            bad.append((where, key, f"operational claim: {OPERATIONAL.search(t).group(0)!r}"))
        if ACCESS_ASSUMPTION.search(t):
            bad.append((where, key, f"assumes access mode: {ACCESS_ASSUMPTION.search(t).group(0)!r}"))
        for m in CONCLUSION.finditer(t):
            # Permitted only inside quotation marks, i.e. quoted from the licence.
            quoted = re.findall(r'"([^"]*)"', t)
            if not any(m.group(0).lower() in q.lower() for q in quoted):
                bad.append((where, key,
                            f"legal conclusion {m.group(0)!r} not quoted from the licence text"))
    return bad


# --- Check B: against the licence text --------------------------------------

# Terms whose presence in a licence would falsify the corresponding "contains
# no ..." claim. Deliberately over-inclusive: a hit demands an override or a
# documented false positive, not silence.
PROBES = {
    "termination": r"\bterminat",
    "suspension_rights": r"\bsuspend",
    "governing_law_disputes": r"governing law|jurisdiction|\bvenue\b|\bforum\b",
    "output_indemnity": r"\bindemnif",
    "assignment_financing": r"\bassign(?:ment|s|ed)?\b|change of control",
    "data_use_ai_training": r"personal data|training data",
    "content_retention_review": r"\bretention\b|human review",
    "data_residency": r"\bresidenc",
    "data_transfer_mechanism": r"standard contractual|cross-border",
    "subprocessor_transparency": r"sub-?processor",
    "government_access": r"law enforcement|government request",
    "prohibited_high_risk_uses": r"acceptable use|prohibited use",
    "appeal_redress": r"\bappeal\b|\bredress\b",
    "capacity_reservation": r"capacity",
    "availability_definition": r"\bavailability\b|\buptime\b",
}

# Matches that look like hits but are not, with the reason. Anything here is a
# deliberate, reviewed exception rather than an oversight.
FALSE_POSITIVES = {
    # "more than 20 million US dollars ... in monthly revenue" -- "revenue"
    # contains "venue". Not a forum clause.
    ("Modified MIT", "governing_law_disputes"): "revenue",
}


def licence_text(provider):
    files = sorted(glob.glob(str(ROOT / f"snapshots/{provider}/model_license/*.txt")))
    if not files:
        return ""
    return " ".join(Path(files[-1]).read_text(errors="ignore").split())


def providers_by_form(cfg):
    """Map each configured form to the providers currently carrying it."""
    try:
        data = json.loads((ROOT / "data/dataset.json").read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for meta in data.get("providers", []):
        form = (cfg.get("forms") or {}).get(meta.get("license_type", ""))
        if form:
            out.setdefault(form, []).append(meta["provider"])
    return out


def check_text(cfg):
    reasons = cfg.get("reasons") or {}
    overrides = cfg.get("overrides") or {}
    bad = []
    for form, provs in sorted(providers_by_form(cfg).items()):
        for provider in provs:
            text = licence_text(provider)
            if not text:
                continue
            for dim, probe in PROBES.items():
                if dim not in reasons:
                    continue
                # An override IS the acknowledgement that the clause exists.
                if dim in (overrides.get(form) or {}):
                    continue
                hits = {m.group(0).lower() for m in re.finditer(probe, text, re.I)}
                fp = FALSE_POSITIVES.get((form, dim))
                if fp:
                    hits = {h for h in hits
                            if not re.search(probe, fp, re.I)
                            or not any(fp.lower().find(h) >= 0 for h in hits)}
                    hits = {h for h in hits if fp.lower().find(h) < 0}
                if hits:
                    bad.append((form, provider, dim,
                                f"licence text contains {sorted(hits)}, "
                                f"but the reason claims {reasons[dim]!r}"))
    return bad


def main():
    cfg = yaml.safe_load((ROOT / "licence_silence.yaml").read_text(encoding="utf-8"))
    reasons = cfg.get("reasons") or {}
    overrides = cfg.get("overrides") or {}

    failures = []

    bespoke = cfg.get("bespoke") or {}
    for where, key, why in check_wording(reasons, overrides, bespoke):
        failures.append(f"  {where}.{key}: {why}")

    for form, provider, dim, why in check_text(cfg):
        failures.append(f"  {form} ({provider}) / {dim}: {why}")

    if failures:
        print("licence_silence.yaml FAILED the four-corners check:\n")
        print("\n".join(failures))
        print("\nEither reword the line to describe only the licence text, or add an "
              "override under the form naming the clause that exists.")
        return 1

    n = (len(reasons) + sum(len(v) for v in overrides.values())
         + sum(1 for k in ("reason", "note") if bespoke.get(k)))
    print(f"All licence-silence checks passed ({n} reason lines, "
          f"wording + licence text).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
