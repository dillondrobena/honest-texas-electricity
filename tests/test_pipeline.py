"""End-to-end pipeline over the real Oncor fixture."""
import json

from htx import pipeline
from htx.models import TDU_ONCOR


def test_pipeline_runs_on_real_oncor_data(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    c = result.data["counts"]
    assert 0 < c["total"] <= 297      # deduped from the 297 raw rows
    assert c["honest"] >= 60          # keeps at least the curator's kept set
    assert c["honest"] < c["total"]   # and rejects real gimmicks
    assert c["rejected"] > 0
    assert c["dropped_invalid"] == 0  # real Oncor data has no unusable records


def test_pipeline_dedupes_plan_ids(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    ranked_ids = [r["plan_id"] for r in result.data["rankings"]["1000"]["plans"]]
    assert len(ranked_ids) == len(set(ranked_ids)), "a plan appears twice in the ranking"


def test_pipeline_output_is_json_serializable(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    round_tripped = json.loads(result.to_json())
    assert round_tripped["tdu"] == TDU_ONCOR
    assert "1000" in round_tripped["rankings"]


def test_every_honest_plan_has_cost_coefficients(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    for pid, p in result.data["honest_plans"].items():
        assert "cost" in p, f"{pid} missing precomputed cost coefficients"
        assert "rate_per_kwh" in p["cost"]


def test_top_pick_at_1000_is_present_and_honest(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    top = result.data["rankings"]["1000"]["top_pick_id"]
    assert top is not None
    assert top in result.data["honest_plans"]


def test_autopsies_have_verdicts(oncor_all):
    result = pipeline.run(oncor_all, TDU_ONCOR, generated_at="2026-07-20T00:00:00Z")
    assert result.data["autopsies"]
    for a in result.data["autopsies"]:
        assert a["reason_codes"]
        assert len(a["verdicts"]) == len(a["reason_codes"])
