"""Data validation — trustworthy data, not just fresh data.

M1 does INTERNAL validation only: range sanity + monotonic bill checks + the
cost-engine linearity flag. Reconciling the feed against each plan's legally
binding EFL (the Electricity Facts Label PDF) is a later milestone; until then
every plan is efl_verified = False and cannot be the sole #1 recommendation.

Validation never mutates a plan and never raises: it returns a list of issue
strings. The pipeline decides what to do (drop, flag, or keep) so a single bad
record can never take down a whole region's refresh.
"""
from __future__ import annotations

from .cost import build_cost_model
from .models import Plan

# Plausible residential average-rate band ($/kWh). Anything outside is suspicious
# (a feed error, or an advertised teaser that isn't a real all-in rate).
MIN_RATE = 0.03
MAX_RATE = 0.40


def is_usable(plan: Plan) -> bool:
    """Can we reason about this plan at all? A plan is UNUSABLE (and only then
    dropped) if it has no name or fewer than 2 price points. Everything else —
    odd terms, out-of-range rates, and non-monotonic bills — is kept and handled
    downstream, because a non-monotonic bill is a GIMMICK to expose, not a record
    to hide. Dropping gimmicks would defeat the whole point of the site."""
    if not plan.rep or not plan.product:
        return False
    return len(plan.bill_points()) >= 2


def validate_plan(plan: Plan) -> list[str]:
    """Return a list of human-readable data issues (empty == clean)."""
    issues: list[str] = []

    # Required identity/pricing fields.
    if not plan.rep or not plan.product:
        issues.append("missing rep or product name")
    if plan.rate_type is None:
        issues.append("missing rate_type")

    # Need at least two price points to reason about cost.
    points = plan.bill_points()
    if len(points) < 2:
        issues.append(f"only {len(points)} price point(s); need >= 2")

    # Rate sanity at each sample level.
    for kwh, rate in ((500, plan.rate500), (1000, plan.rate1000), (2000, plan.rate2000)):
        if rate is None:
            continue
        if not (MIN_RATE <= rate <= MAX_RATE):
            issues.append(f"rate@{kwh}kWh={rate} outside [{MIN_RATE},{MAX_RATE}]")

    # Bills must be positive and non-decreasing with usage (more power costs more).
    bills = [(k, b) for k, b in points]
    for _, b in bills:
        if b <= 0:
            issues.append(f"non-positive bill {b}")
    for (k1, b1), (k2, b2) in zip(bills, bills[1:]):
        if b2 < b1:
            issues.append(f"bill decreases with usage: {k1}kWh=${b1} -> {k2}kWh=${b2}")

    # Term sanity.
    if plan.term_months is not None and not (1 <= plan.term_months <= 60):
        issues.append(f"term_months={plan.term_months} outside [1,60]")

    return issues


def is_valid(plan: Plan) -> bool:
    return not validate_plan(plan)
