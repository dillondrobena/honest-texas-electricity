"""The true-cost engine.

Each plan gives us three (kWh, monthly-bill) points from PowerToChoose. We fit
    bill = base_charge + rate * kWh
to them (ordinary least squares). Two outputs from one function:

  1. base_charge + rate  -> price the plan at ANY usage (not just 500/1000/2000).
  2. the fit residual     -> a poor fit means the bill does NOT scale linearly,
                             i.e. there's a hidden bill credit / tier / usage cliff.
                             The same math that prices the plan screens it.

A clean fixed plan fits a line almost perfectly (base = monthly charge, slope =
energy+delivery rate). A gimmick plan bends between 500 and 2000 kWh.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Plan

# If the worst point deviates from the fitted line by more than this many
# dollars, treat the plan as nonlinear (a hidden kink). $1.25 absorbs rounding
# in the published bill figures (observed max ~$1.07 on clean plans) while still
# catching real bill credits, which bend the line by $40+.
NONLINEAR_ABS_TOLERANCE = 1.25


@dataclass
class CostModel:
    base_charge: float      # fixed $/month (line intercept)
    rate_per_kwh: float     # $/kWh (line slope)
    max_residual: float     # worst absolute $ deviation of a sample point
    is_linear: bool
    n_points: int

    def bill_at(self, usage_kwh: float) -> float:
        """Estimated monthly bill at an arbitrary usage."""
        return self.base_charge + self.rate_per_kwh * usage_kwh


def fit_line(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Ordinary least-squares fit of y = base + rate*x. Returns (base, rate).

    Requires >= 2 distinct x values. Pure stdlib — no numpy dependency."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    if n < 2:
        raise ValueError("need at least 2 points to fit a line")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("all x values identical; cannot fit a line")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    rate = sxy / sxx
    base = mean_y - rate * mean_x
    return base, rate


def build_cost_model(plan: Plan, tolerance: float = NONLINEAR_ABS_TOLERANCE) -> CostModel | None:
    """Fit a cost model to a plan's sample points. Returns None if there aren't
    enough points to fit (a data problem the validator will also flag)."""
    points = plan.bill_points()
    if len(points) < 2:
        return None
    base, rate = fit_line(points)
    max_resid = max(abs((base + rate * x) - y) for x, y in points)
    return CostModel(
        base_charge=base,
        rate_per_kwh=rate,
        max_residual=max_resid,
        is_linear=max_resid <= tolerance,
        n_points=len(points),
    )
