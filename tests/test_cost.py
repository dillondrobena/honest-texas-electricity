"""Cost engine: line fit prices the plan AND detects gimmicks."""
import math

import pytest

from htx.cost import build_cost_model, fit_line
from htx.models import Plan


def make(bill500, bill1000, bill2000, **over) -> Plan:
    base = dict(
        plan_id="x", tdu="ONCOR", rep="Acme", product="P",
        rate500=bill500 / 500, bill500=bill500,
        rate1000=bill1000 / 1000, bill1000=bill1000,
        rate2000=bill2000 / 2000, bill2000=bill2000,
        rate_type="Fixed", fees_credits=None,
    )
    base.update(over)
    return Plan(**base)


def test_fit_recovers_base_and_rate():
    # bill = 4 + 0.114*kwh  ->  (500,61) (1000,118) (2000,232)
    base, rate = fit_line([(500, 61), (1000, 118), (2000, 232)])
    assert base == pytest.approx(4.0, abs=1e-6)
    assert rate == pytest.approx(0.114, abs=1e-6)


def test_clean_plan_is_linear_and_prices_anywhere():
    m = build_cost_model(make(61, 118, 232))
    assert m.is_linear
    assert m.bill_at(1300) == pytest.approx(4 + 0.114 * 1300, abs=0.01)


def test_bill_credit_kink_is_nonlinear():
    # A $100 credit that only applies at/above 1000 kWh bends the line hard:
    # 500 -> 65 (no credit), 1000 -> 18 (credit), 2000 -> 130 (credit).
    m = build_cost_model(make(65, 18, 130))
    assert not m.is_linear
    assert m.max_residual > 1.0


def test_two_points_still_fits():
    p = make(61, 118, 232)
    p.bill2000 = None
    p.rate2000 = None
    m = build_cost_model(p)
    assert m is not None and m.n_points == 2


def test_insufficient_points_returns_none():
    p = make(61, 118, 232)
    p.bill1000 = p.rate1000 = p.bill2000 = p.rate2000 = None
    assert build_cost_model(p) is None


def test_identical_x_raises():
    with pytest.raises(ValueError):
        fit_line([(1000, 100), (1000, 120)])
