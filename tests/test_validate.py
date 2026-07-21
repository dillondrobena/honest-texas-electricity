"""Validation: range sanity, monotonic bills, never raises."""
from htx.models import Plan
from htx.validate import is_valid, validate_plan


def make(**over) -> Plan:
    base = dict(
        plan_id="x", tdu="ONCOR", rep="Acme", product="P",
        rate500=0.12, bill500=60, rate1000=0.118, bill1000=118,
        rate2000=0.116, bill2000=232, rate_type="Fixed", fees_credits=None,
        term_months=12,
    )
    base.update(over)
    return Plan(**base)


def test_clean_plan_valid():
    assert is_valid(make())


def test_absurd_rate_flagged():
    issues = validate_plan(make(rate1000=0.95))
    assert any("outside" in i for i in issues)


def test_bill_decreasing_flagged():
    issues = validate_plan(make(bill2000=50))  # cheaper at 2000 than 1000: impossible
    assert any("decreases" in i for i in issues)


def test_missing_rate_type_flagged():
    assert any("rate_type" in i for i in validate_plan(make(rate_type=None)))


def test_bad_term_flagged():
    assert any("term" in i for i in validate_plan(make(term_months=999)))


def test_validate_never_raises_on_empty_plan():
    # A near-empty plan should return issues, not blow up (non-blocking contract).
    p = Plan(plan_id="e", tdu="ONCOR", rep="", product="",
             rate500=None, bill500=None, rate1000=None, bill1000=None,
             rate2000=None, bill2000=None, rate_type=None, fees_credits=None)
    issues = validate_plan(p)
    assert issues  # it's invalid, but we got a list back, not an exception
