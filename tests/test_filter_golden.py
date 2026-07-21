"""THE fidelity anchor.

Proves our structural filter reproduces the curator's honest judgment against
the real July 2026 Oncor data: every plan he kept passes our rules, with ZERO
false-negatives. This is also the monthly regression guard — if a code change
starts excluding plans the curator would keep, this test fails.
"""
from htx.filter import is_honest, partition


def test_every_curator_kept_plan_passes_our_filter(oncor_all, oncor_filtered):
    """Zero false-negatives: no plan the curator kept is rejected by our rules."""
    kept_ids = {p.plan_id for p in oncor_filtered}
    honest, _ = partition(oncor_all)
    our_honest_ids = {p.plan_id for p in honest}

    missed = kept_ids - our_honest_ids
    assert not missed, (
        f"{len(missed)} curator-kept plans were wrongly excluded by our filter: "
        f"{sorted(missed)[:5]}"
    )


def test_curator_kept_plans_are_individually_honest(oncor_filtered):
    """Each kept plan, evaluated on its own, is honest."""
    not_honest = [p.plan_id for p in oncor_filtered if not is_honest(p)]
    assert not not_honest, f"curator-kept plans our filter flags as gimmicks: {not_honest}"


def test_filter_keeps_more_than_curator_by_design(oncor_all, oncor_filtered):
    """We intentionally keep MORE than the curator's manual ~top-60 cut — we rank
    by true cost instead of applying an arbitrary per-region limit. This test
    documents that decision so a future 'why don't the counts match?' is answered."""
    honest, _ = partition(oncor_all)
    assert len(honest) >= len(oncor_filtered)


def test_rejected_plans_all_have_reasons(oncor_all):
    """Every rejected plan carries at least one reason code for its autopsy."""
    _, rejected = partition(oncor_all)
    assert rejected, "expected some rejected plans in the raw Oncor set"
    assert all(reasons for _, reasons in rejected)
