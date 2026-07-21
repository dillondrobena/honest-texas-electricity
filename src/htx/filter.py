"""The editorial filter — the heart of the product.

These four STRUCTURAL rules reproduce the volunteer curator's honest-plan
judgment. Verified against the July 2026 PowerToChoose data: every one of the
325 plans he kept passes these rules (zero false-negatives). See
tests/test_filter_golden.py for the fidelity anchor.

Design note (fidelity, not correctness): these rules agree with the curator's
kept set. They intentionally keep MORE plans than he did, because he also
applied a manual "cheapest ~50-60 per region" cut that was a spreadsheet-space
constraint. We don't replicate that arbitrary cut — instead we rank every
structurally-honest plan by true cost at the user's usage (see recommend.py).

    ┌─────────────────── 1,652 raw plans ───────────────────┐
    │  EXCLUDE if ANY:                                        │
    │    • rate_type != Fixed        -> VARIABLE_RATE         │
    │    • fees_credits present       -> BILL_CREDIT          │
    │    • prepaid                    -> PREPAID              │
    │    • time_of_use                -> TIME_OF_USE          │
    └───────────────────────┬────────────────────────────────┘
                            │ keep the rest  (structurally honest)
                            ▼
              rank by true cost at the user's usage
"""
from __future__ import annotations

from .models import Plan, ReasonCode


def structural_reasons(plan: Plan) -> list[ReasonCode]:
    """Return every reason this plan is a gimmick. Empty list == honest.

    A plan can trip multiple rules (e.g. a prepaid time-of-use plan), so we
    return all of them for a complete, honest autopsy verdict."""
    reasons: list[ReasonCode] = []

    # Rule 1: must be a fixed rate. Variable/indexed rates can change with no cap.
    if (plan.rate_type or "").strip().lower() != "fixed":
        reasons.append(ReasonCode.VARIABLE_RATE)

    # Rule 2: no bill credits / usage fees. A non-empty Fees/Credits field means
    # the advertised price is gated on hitting a specific usage — the #1 trap.
    if plan.fees_credits:
        reasons.append(ReasonCode.BILL_CREDIT)

    # Rule 3: no prepaid products.
    if plan.prepaid:
        reasons.append(ReasonCode.PREPAID)

    # Rule 4: no time-of-use plans. "Free nights" etc. spike the daytime rate.
    if plan.time_of_use:
        reasons.append(ReasonCode.TIME_OF_USE)

    return reasons


def is_honest(plan: Plan) -> bool:
    """True if the plan passes every structural rule."""
    return not structural_reasons(plan)


def partition(plans: list[Plan]) -> tuple[list[Plan], list[tuple[Plan, list[ReasonCode]]]]:
    """Split plans into (honest, rejected-with-reasons)."""
    honest: list[Plan] = []
    rejected: list[tuple[Plan, list[ReasonCode]]] = []
    for p in plans:
        reasons = structural_reasons(p)
        if reasons:
            rejected.append((p, reasons))
        else:
            honest.append(p)
    return honest, rejected
