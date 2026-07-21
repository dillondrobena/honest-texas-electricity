"""Multi-region (Milestone 2): the pipeline works for all six TDUs."""
import pytest

from htx import pipeline
from htx.models import REGION_META, SLUG_BY_TDU, normalize_tdu


def test_all_six_regions_produce_a_usable_result(all_plans):
    for region in REGION_META:
        result = pipeline.run(all_plans, region["tdu"], generated_at="2026-07-20T00:00:00Z")
        c = result.data["counts"]
        assert c["total"] > 0, f"{region['label']} had no plans"
        assert c["honest"] > 0, f"{region['label']} had no honest plans"
        assert c["rejected"] > 0, f"{region['label']} exposed no gimmicks"
        assert result.data["rankings"]["1000"]["top_pick_id"] is not None


def test_region_slugs_and_tdus_are_unique():
    slugs = [r["slug"] for r in REGION_META]
    tdus = [r["tdu"] for r in REGION_META]
    assert len(slugs) == len(set(slugs))
    assert len(tdus) == len(set(tdus))
    assert len(SLUG_BY_TDU) == len(REGION_META)


def test_every_region_tdu_is_canonical():
    # Each region's tdu must be a fixed point of normalize_tdu (already canonical).
    for region in REGION_META:
        assert normalize_tdu(region["tdu"]) == region["tdu"]


def test_regions_partition_the_plans_without_overlap(all_plans):
    # No plan should count toward two regions (tdu is exclusive).
    seen = set()
    for region in REGION_META:
        result = pipeline.run(all_plans, region["tdu"], generated_at="t")
        ids = set(result.data["honest_plans"].keys())
        assert not (ids & seen), f"{region['label']} overlaps another region"
        seen |= ids
