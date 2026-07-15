"""The v1 term schema — the 10 legally significant dimensions we extract.

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
            "position (e.g. 'does not train on customer data' vs. 'may use to "
            "improve services') and any opt-in/opt-out."
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
]

DIMENSION_KEYS = [d.key for d in DIMENSIONS]


def dimension(key: str) -> Dimension:
    for d in DIMENSIONS:
        if d.key == key:
            return d
    raise KeyError(key)
