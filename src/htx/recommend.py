"""Recommendation — rank honest plans by true cost at the user's usage.

We do NOT use the curator's arbitrary "top ~50 per region" cut. We rank every
structurally-honest plan by its estimated bill at the user's actual usage.

Tie-break ladder (Codex #6 / decision T2A): when two plans are within a small
cost band (default 1%/mo), "cheapest" is ambiguous, so break ties by a published,
transparent ladder — lower cancel fee, then higher rating, then shorter term,
then higher renewable. Every #1 pick can explain itself.

EFL-verified gate (decision T1A): only EFL-verified plans may be the sole #1
recommendation. Since M1 has no EFL parsing yet, require_verified defaults to
False; when the EFL milestone lands, the app will pass require_verified=True so
the top pick is always backed by the legal document.
"""
from __future__ import annotations

from dataclasses import dataclass

from .cost import CostModel, build_cost_model
from .filter import is_honest
from .models import Plan

TIE_BAND = 0.01  # plans within 1% monthly cost are treated as a tie


@dataclass
class Ranked:
    plan: Plan
    monthly_bill: float
    cost: CostModel
    # True when the cost model is a clean line; a nonlinear honest plan is still
    # shown but flagged, and is not trusted for the top slot.
    trustworthy_price: bool

    def sort_key(self):
        # Lower cost first; then the published tie-break ladder. We negate
        # "higher is better" fields so ascending sort does the right thing.
        p = self.plan
        return (
            round(self.monthly_bill, 2),
            p.cancel_fee if p.cancel_fee is not None else float("inf"),
            -(p.rating if p.rating is not None else -1),
            p.term_months if p.term_months is not None else float("inf"),
            -(p.renewable if p.renewable is not None else -1),
        )


def rank(plans: list[Plan], usage_kwh: float, *, require_verified: bool = False) -> list[Ranked]:
    """Rank the structurally-honest plans for a usage level, cheapest first.

    Plans that aren't honest are dropped here (they belong in the autopsy list,
    produced separately by filter.partition)."""
    ranked: list[Ranked] = []
    for p in plans:
        if not is_honest(p):
            continue
        model = build_cost_model(p)
        if model is None:
            continue  # not enough data to price; validator flags it
        ranked.append(
            Ranked(
                plan=p,
                monthly_bill=model.bill_at(usage_kwh),
                cost=model,
                trustworthy_price=model.is_linear,
            )
        )
    ranked.sort(key=lambda r: r.sort_key())
    return ranked


def top_pick(ranked: list[Ranked], *, require_verified: bool = False) -> Ranked | None:
    """The single honest #1. Must have a trustworthy (linear) price, and — when
    require_verified is on — must be EFL-verified."""
    for r in ranked:
        if not r.trustworthy_price:
            continue
        if require_verified and not r.plan.efl_verified:
            continue
        return r
    return None


def tie_group(ranked: list[Ranked], band: float = TIE_BAND) -> list[Ranked]:
    """The set of plans effectively tied with the cheapest (within `band`)."""
    if not ranked:
        return []
    cheapest = ranked[0].monthly_bill
    if cheapest <= 0:
        return ranked[:1]
    return [r for r in ranked if (r.monthly_bill - cheapest) / cheapest <= band]
