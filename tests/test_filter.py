"""Unit tests for each structural filter rule."""
import pytest

from htx.filter import is_honest, structural_reasons
from htx.models import Plan, ReasonCode


def make(**over) -> Plan:
    base = dict(
        plan_id="x", tdu="ONCOR", rep="Acme", product="Basic 12",
        rate500=0.12, bill500=60, rate1000=0.118, bill1000=118,
        rate2000=0.116, bill2000=232, rate_type="Fixed", fees_credits=None,
        prepaid=False, time_of_use=False, term_months=12,
    )
    base.update(over)
    return Plan(**base)


def test_clean_fixed_plan_is_honest():
    assert is_honest(make())
    assert structural_reasons(make()) == []


def test_variable_rate_rejected():
    assert structural_reasons(make(rate_type="Variable")) == [ReasonCode.VARIABLE_RATE]


def test_bill_credit_rejected():
    assert structural_reasons(make(fees_credits="$100 bill credit")) == [ReasonCode.BILL_CREDIT]


def test_empty_fees_credits_is_honest():
    # Empty string / whitespace must NOT count as a bill credit.
    assert is_honest(make(fees_credits=""))
    assert is_honest(make(fees_credits=None))


def test_prepaid_rejected():
    assert structural_reasons(make(prepaid=True)) == [ReasonCode.PREPAID]


def test_time_of_use_rejected():
    assert structural_reasons(make(time_of_use=True)) == [ReasonCode.TIME_OF_USE]


def test_multiple_gimmicks_all_reported():
    reasons = structural_reasons(make(rate_type="Variable", prepaid=True, time_of_use=True))
    assert set(reasons) == {ReasonCode.VARIABLE_RATE, ReasonCode.PREPAID, ReasonCode.TIME_OF_USE}


def test_rate_type_case_insensitive():
    assert is_honest(make(rate_type="fixed"))
    assert is_honest(make(rate_type="FIXED"))
