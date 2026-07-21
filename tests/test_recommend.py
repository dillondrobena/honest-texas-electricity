"""Recommendation: cheapest-by-true-cost + the published tie-break ladder."""
from htx.models import Plan
from htx.recommend import rank, tie_group, top_pick


def plan(pid, base, rate, **over):
    # Construct a plan whose 3 points lie on bill = base + rate*kwh.
    def bill(k):
        return base + rate * k
    d = dict(
        plan_id=pid, tdu="ONCOR", rep=pid, product=pid,
        rate500=bill(500) / 500, bill500=bill(500),
        rate1000=bill(1000) / 1000, bill1000=bill(1000),
        rate2000=bill(2000) / 2000, bill2000=bill(2000),
        rate_type="Fixed", fees_credits=None,
    )
    d.update(over)
    return Plan(**d)


def test_ranks_cheapest_first_at_usage():
    cheap = plan("cheap", base=5, rate=0.10)     # @1000 = 105
    pricey = plan("pricey", base=5, rate=0.13)   # @1000 = 135
    ranked = rank([pricey, cheap], 1000)
    assert [r.plan.plan_id for r in ranked] == ["cheap", "pricey"]


def test_usage_changes_the_winner():
    low_base = plan("lowbase", base=0, rate=0.12)    # @500=60,  @2000=240
    high_base = plan("highbase", base=40, rate=0.09)  # @500=85,  @2000=220
    assert rank([low_base, high_base], 500)[0].plan.plan_id == "lowbase"
    assert rank([low_base, high_base], 2000)[0].plan.plan_id == "highbase"


def test_tie_break_prefers_lower_cancel_fee():
    a = plan("a", base=5, rate=0.10, cancel_fee=300, rating=5)
    b = plan("b", base=5, rate=0.10, cancel_fee=20, rating=5)  # same cost, lower fee
    ranked = rank([a, b], 1000)
    assert ranked[0].plan.plan_id == "b"


def test_tie_break_then_prefers_higher_rating():
    a = plan("a", base=5, rate=0.10, cancel_fee=20, rating=2)
    b = plan("b", base=5, rate=0.10, cancel_fee=20, rating=5)  # tie on fee, better rating
    ranked = rank([a, b], 1000)
    assert ranked[0].plan.plan_id == "b"


def test_nonlinear_plan_not_the_top_pick():
    good = plan("good", base=5, rate=0.11)
    # Gimmick: linear-looking rate_type but a bent bill curve, slightly cheaper.
    gimmick = plan("gimmick", base=5, rate=0.10)
    gimmick.bill1000 = 60  # break the line -> nonlinear
    gimmick.rate1000 = 0.06
    ranked = rank([gimmick, good], 1000)
    # gimmick sorts cheaper but is not trustworthy, so top_pick skips it.
    assert top_pick(ranked).plan.plan_id == "good"


def test_require_verified_gates_top_pick():
    p = plan("p", base=5, rate=0.10, efl_verified=False)
    ranked = rank([p], 1000)
    assert top_pick(ranked) is not None
    assert top_pick(ranked, require_verified=True) is None


def test_tie_group_bands_by_percent():
    a = plan("a", base=0, rate=0.10)   # @1000 = 100
    b = plan("b", base=0, rate=0.1005)  # @1000 = 100.5 (within 1%)
    c = plan("c", base=0, rate=0.13)   # @1000 = 130 (outside)
    group = tie_group(rank([a, b, c], 1000))
    assert {r.plan.plan_id for r in group} == {"a", "b"}
