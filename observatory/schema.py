"""The term schema — the legally significant dimensions we extract.

This is the single source of truth for extraction criteria AND for the site's
matrix rows, so the two can never drift. Each dimension carries a stable key, a
human label, and guidance telling the extractor exactly what to look for and how
to shape the value (categorical or short structured text — never an essay).

Every extracted field returns: value, confidence, citation (a section heading or
a quoted anchor under 15 words), and which document the citation came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    guidance: str


DIMENSIONS: List[Dimension] = [
    Dimension(
        key="capacity_reservation",
        label="Capacity & reservation terms",
        guidance=(
            "Existence and nature of reserved or committed-capacity terms in the "
            "PUBLIC documents: reserved instances, committed-use/savings plans, "
            "take-or-pay, use-it-or-lose-it, cancellation rights. Where the "
            "meaningful commitment terms are negotiated privately (enterprise "
            "commitment vehicles), say so explicitly with 'negotiated, not "
            "published'. Do not infer terms that are not in the documents."
        ),
    ),
    Dimension(
        key="data_use_ai_training",
        label="Data use & AI training",
        guidance=(
            "What the terms say about the provider's rights to use customer data, "
            "and specifically any language about training or improving the "
            "provider's AI/ML models on customer content. State the default "
            "position (trains by default / opt-out / opt-in / never), whether it "
            "varies by tier, any default retention period for inputs/outputs, and "
            "whether zero-data-retention (ZDR) is available (no / enterprise-only / "
            "yes)."
        ),
    ),
    Dimension(
        key="suspension_rights",
        label="Suspension rights",
        guidance=(
            "The grounds on which the provider may suspend the service (e.g. AUP "
            "breach, non-payment, security risk, legal process) and whether prior "
            "notice is required or suspension can be immediate."
        ),
    ),
    Dimension(
        key="termination",
        label="Termination",
        guidance=(
            "Termination for convenience rights (which side, and any notice period), "
            "and the effect on data retrieval after termination — the post-"
            "termination window during which the customer can still retrieve data."
        ),
    ),
    Dimension(
        key="unilateral_modification",
        label="Unilateral modification",
        guidance=(
            "Whether and how the provider may unilaterally change the terms, and any "
            "notice commitment before changes take effect (e.g. 30/90 days' notice, "
            "or 'effective on posting')."
        ),
    ),
    Dimension(
        key="governing_law_disputes",
        label="Governing law & disputes",
        guidance=(
            "Governing law, the forum/venue, whether disputes go to binding "
            "arbitration (yes/no), and whether there is a class-action waiver "
            "(yes/no). Keep each element short."
        ),
    ),
    Dimension(
        key="liability",
        label="Liability caps & carveouts",
        guidance=(
            "The general limitation-of-liability cap (e.g. 12 months' fees, fees "
            "paid, a fixed amount), notable carveouts excluded from the cap "
            "(indemnity, confidentiality, data breach, IP), and whether "
            "consequential/indirect damages are waived."
        ),
    ),
    Dimension(
        key="output_indemnity",
        label="Output IP indemnification",
        guidance=(
            "Whether the provider offers IP indemnification for model outputs "
            "(no / paid-tiers-only / enterprise-only / yes), any cap on it "
            "(excluded / general cap / supercap / uncapped / unknown), and the "
            "conditions attached (e.g. safety features on, no fine-tuning, no known "
            "infringement)."
        ),
    ),
    Dimension(
        key="deprecation",
        label="Model deprecation & version pinning",
        guidance=(
            "Model deprecation and version pinning: whether there is a public "
            "commitment (none / informal / documented policy / contractual), the "
            "minimum notice before a model is retired (days), and whether version "
            "pinning is available (no / enterprise-only / yes)."
        ),
    ),
    Dimension(
        key="benchmarking_restrictions",
        label="Benchmarking & eval restrictions",
        guidance=(
            "Whether publishing benchmarks or evaluations of the service or model "
            "is unrestricted, consent-required, prohibited, or silent."
        ),
    ),
    Dimension(
        key="competitive_training",
        label="No-compete-training clauses",
        guidance=(
            "Whether the terms restrict using the provider's outputs to train other "
            "models: none / competing-models-only / any-model-training / silent."
        ),
    ),
    Dimension(
        key="model_license",
        label="Model license",
        guidance=(
            "For a model-weights license document, the license as NAMED in the "
            "document: e.g. MIT, Apache 2.0, a bespoke/community license (give its "
            "name), or a modified permissive license. This value attaches to the "
            "specific license document and model generation it came from; never "
            "assert it family-wide. Value = 'not applicable' for closed/API-only "
            "offerings with no weights license."
        ),
    ),
    Dimension(
        key="capacity_remedies",
        label="Capacity delivery remedies",
        guidance=(
            "For committed or reserved capacity, the delivery commitment (firm / "
            "best-efforts / silent) and the remedy if capacity is not delivered "
            "(credits / termination right / refund / none / negotiated). Mainly "
            "relevant to neocloud/GPU providers."
        ),
    ),
    Dimension(
        key="hardware_substitution",
        label="Hardware substitution rights",
        guidance=(
            "Whether the provider may substitute the hardware/GPU model delivered: "
            "unilateral / equivalent-or-better / consent-required / silent. Mainly "
            "relevant to neocloud/GPU providers."
        ),
    ),
    Dimension(
        key="assignment_financing",
        label="Assignment & financing clauses",
        guidance=(
            "The provider's assignment rights (unrestricted / affiliates-and-"
            "financing / consent-required / silent) and whether there is lender "
            "step-in / financing language (yes/no). Mainly relevant to neocloud/GPU "
            "providers."
        ),
    ),
    # SLA-specific dimensions are grouped at the bottom of the matrix.
    Dimension(
        key="availability_definition",
        label="Availability definition",
        guidance=(
            "How uptime/availability is defined and the commitment percentage(s). "
            "Categorize the basis as one of: instance-level, region-level, "
            "cluster/throughput-based, API-error-rate-based, or other. Include the "
            "commitment percentage(s) (e.g. 99.99% region, 99.5% instance). If the "
            "provider publishes no uptime commitment, value = 'no SLA / uptime not "
            "committed'."
        ),
    ),
    Dimension(
        key="credit_regime",
        label="Credit regime",
        guidance=(
            "Service-credit structure: the tier mapping (uptime threshold -> credit "
            "percentage), the maximum credit, and whether credits are stated to be "
            "the sole and exclusive remedy. Give the tiers compactly."
        ),
    ),
    Dimension(
        key="claim_mechanics",
        label="Claim mechanics",
        guidance=(
            "Whether the customer must file a claim to receive credits, the claim "
            "window and how it is measured (e.g. within 30 days / end of billing "
            "cycle), and what evidence the customer must supply."
        ),
    ),
    Dimension(
        key="sla_exclusions",
        label="SLA exclusions",
        guidance=(
            "Notable exclusions from the SLA as a short categorical checklist plus a "
            "brief note. Look for: force majeure, customer fault/misuse, scheduled or "
            "emergency maintenance, beta/preview services, single-AZ deployments, "
            "throttling, external network/ISP issues. List the ones present."
        ),
    ),
]

DIMENSION_KEYS = [d.key for d in DIMENSIONS]


def dimension(key: str) -> Dimension:
    for d in DIMENSIONS:
        if d.key == key:
            return d
    raise KeyError(key)


# ---------------------------------------------------------------------------
# Per-segment dimension sets (single source of truth)
#
# Each matrix table renders only the dimensions applicable to its segment. A
# dimension is removed from a segment ONLY when it is structurally inapplicable —
# the entry type cannot meaningfully have it (the precondition does not exist),
# not merely that today's providers are silent. Collective silence is a finding
# and stays. Reviewed and approved 2026-07-18.
# ---------------------------------------------------------------------------

SEGMENT_GROUPS = ("cloud", "closed", "open")
SEGMENT_GROUP_LABEL = {
    "cloud": "Cloud Infrastructure",
    "closed": "Closed API",
    "open": "Open Weight",
}

# Dimensions removed from each group's table, with the one-line rationale that
# appears in the methodology.
SEGMENT_REMOVED = {
    "cloud": {
        "model_license": "infrastructure providers distribute no model weights, so "
        "the license under which weights are distributed has no referent",
    },
    "closed": {
        "hardware_substitution": "a closed API allocates tokens/throughput, not GPUs; "
        "there is no hardware to substitute",
        "model_license": "closed-API providers distribute no model weights, so the "
        "license under which weights are distributed has no referent (references to "
        "IP ownership or usage restrictions belong to other dimensions)",
    },
    "open": {
        "availability_definition": "an availability definition describes a service's "
        "uptime commitment; an open-weight license distributes weights with no service "
        "attached, so the precondition does not exist",
        "credit_regime": "SLA service credits presuppose a service level to breach; a "
        "downloadable license has no service",
        "claim_mechanics": "there is no SLA to claim credits against",
        "sla_exclusions": "there is no SLA whose scope could be excluded",
        "capacity_reservation": "no hosted capacity is provisioned to reserve",
        "capacity_remedies": "there is no capacity delivery obligation to remedy",
        "hardware_substitution": "no hardware is allocated, so none can be substituted",
    },
}


def segment_group(segment: str, openness: str) -> str:
    """Map a provider's (segment, openness) to its matrix table group."""
    if segment in ("hyperscaler", "neocloud"):
        return "cloud"
    if openness == "open_weight":
        return "open"
    return "closed"


def is_applicable(group: str, dim_key: str) -> bool:
    return dim_key not in SEGMENT_REMOVED.get(group, {})


def applicable_dimensions(group: str) -> List[Dimension]:
    return [d for d in DIMENSIONS if is_applicable(group, d.key)]
