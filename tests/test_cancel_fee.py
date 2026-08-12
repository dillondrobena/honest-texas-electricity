"""Cancel-fee parsing: flat vs per-remaining-month (a real user-reported bug)."""
from htx.models import Plan, parse_cancel_fee


def test_flat_fee_parses_as_flat():
    assert parse_cancel_fee("100.0") == (100.0, False)
    assert parse_cancel_fee("$150") == (150.0, False)
    assert parse_cancel_fee(75) == (75.0, False)


def test_per_month_fee_detected_english():
    for raw in ("20 per remaining month", "20/remaining month.", "20/month remaining",
                "$20/month remaining", "20.00 per month left in term"):
        amt, per = parse_cancel_fee(raw)
        assert (amt, per) == (20.0, True), raw


def test_per_month_fee_detected_spanish():
    for raw in ("20 por cada mes restante", "20 por mes restante", "15 por mes restante"):
        _amt, per = parse_cancel_fee(raw)
        assert per is True, raw


def test_none_and_missing():
    assert parse_cancel_fee(None) == (None, False)
    assert parse_cancel_fee("no fee text") == (None, False)


def _plan(fee, per_month, term):
    return Plan(
        plan_id="x", tdu="ONCOR", rep="A", product="P",
        rate500=0.12, bill500=60, rate1000=0.118, bill1000=118,
        rate2000=0.116, bill2000=232, rate_type="Fixed", fees_credits=None,
        term_months=term, cancel_fee=fee, cancel_fee_per_month=per_month,
    )


def test_effective_cancel_fee_worst_case():
    # A "$20 per remaining month" fee on a 12-month plan is up to $240, not $20 —
    # so it must NOT sort below a flat $100 fee.
    per_month = _plan(20.0, True, 12)
    flat = _plan(100.0, False, 12)
    assert per_month.effective_cancel_fee() == 240.0
    assert flat.effective_cancel_fee() == 100.0
    assert per_month.effective_cancel_fee() > flat.effective_cancel_fee()


def test_effective_flat_is_unchanged():
    assert _plan(50.0, False, 24).effective_cancel_fee() == 50.0


def test_effective_none_when_no_fee():
    assert _plan(None, False, 12).effective_cancel_fee() is None
