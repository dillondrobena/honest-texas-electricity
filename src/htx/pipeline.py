"""The Milestone 1 pipeline: raw plans -> validated -> filtered -> priced -> JSON.

    ingest ─▶ validate ─▶ filter ─▶ cost ─▶ recommend ─▶ per-region JSON

Output is the static artifact the frontend reads: one honest ranked list plus
the autopsy list (every rejected plan + why), for a set of usage levels.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import filter as flt
from .cost import build_cost_model
from .models import Plan, ReasonCode, SLUG_BY_TDU, VERDICT_TEMPLATES
from .recommend import rank, top_pick
from .validate import is_usable, validate_plan

# Usage levels we precompute rankings for. The frontend can also recompute at an
# arbitrary usage using each plan's (base_charge, rate_per_kwh) coefficients.
DEFAULT_USAGE_LEVELS = (500, 1000, 1500, 2000)

# A plan whose line-fit intercept sits more than this many dollars above the
# region's baseline (the fixed TDU delivery charge that every plan pays) is
# carrying its own monthly base charge — a gotcha the curator filters out.
BASE_CHARGE_TOLERANCE = 1.0


def _region_base_baseline(plans: list[Plan]) -> float:
    """Estimate the region's fixed TDU monthly charge — the line-fit intercept
    shared by every $0-base plan. The low-percentile intercept lands in that
    cluster (most plans have no base charge), so anything well above it is a
    plan-specific base charge."""
    xs = sorted(m.base_charge for m in (build_cost_model(p) for p in plans) if m is not None)
    if not xs:
        return 0.0
    return xs[int(len(xs) * 0.2)]  # 20th percentile


@dataclass
class RegionResult:
    tdu: str
    generated_at: str
    total_plans: int
    dropped_invalid: int
    honest_count: int
    rejected_count: int
    data: dict

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent)


def _plan_public(p: Plan, efl_status: str = "no_efl") -> dict:
    """The plan fields the frontend needs, plus precomputed cost coefficients."""
    model = build_cost_model(p)
    out = {
        "plan_id": p.plan_id,
        "rep": p.rep,
        "product": p.product,
        "rate_type": p.rate_type,
        "term_months": p.term_months,
        "cancel_fee": p.cancel_fee,
        "renewable": p.renewable,
        "rating": p.rating,
        "efl_url": p.efl_url,
        "enroll_url": p.enroll_url,
        "efl_verified": p.efl_verified,
        "efl_status": efl_status,
    }
    if model is not None:
        out["cost"] = {
            "base_charge": round(model.base_charge, 4),
            "rate_per_kwh": round(model.rate_per_kwh, 5),
            "is_linear": model.is_linear,
            "max_residual": round(model.max_residual, 3),
        }
    return out


def run(plans: list[Plan], tdu: str, generated_at: str,
        usage_levels=DEFAULT_USAGE_LEVELS, efl_cache: dict | None = None,
        language: str = "English") -> RegionResult:
    """Build the region result for one language. `plans` should already be the
    region's plans.

    The PowerToChoose feed lists many plans in both English and Spanish; showing
    both pollutes the list with duplicates (flagged by the curator). We partition
    by `language` so each language site shows a clean list with its own EFLs —
    the same way PowerToChoose itself lets you pick a language.

    `efl_cache` is the {url: {status,...}} map from verify_efls; when present, a
    plan whose EFL was reconciled against the feed is marked efl_verified and
    becomes eligible to be the #1 recommendation (decision T1A)."""
    efl_urls = (efl_cache or {}).get("urls", {})
    _lang = language.lower()[:3]
    # The source feed contains literal duplicate rows (same plan listed twice).
    # Dedup by plan_id, keeping the first occurrence, so a plan never appears
    # twice in the rankings. (Fuller provider/plan identity normalization is a
    # later milestone; this handles the exact-duplicate case at the seam.)
    # Region + target-language filter + exact-duplicate (plan_id) dedup.
    region_plans = []
    seen: set[str] = set()
    for p in plans:
        if p.tdu != tdu or p.plan_id in seen:
            continue
        if not (p.language or "english").lower().startswith(_lang):
            continue
        seen.add(p.plan_id)
        region_plans.append(p)

    # Drop ONLY truly unusable records (no name, or < 2 price points). Non-fatal:
    # a bad record is dropped, never an exception, so one bad row can't sink the
    # region. Odd terms / out-of-range rates / non-monotonic bills are KEPT and
    # handled by the filter + cost engine (non-monotonic == a gimmick to expose).
    valid: list[Plan] = []
    dropped = 0
    for p in region_plans:
        if is_usable(p):
            valid.append(p)
        else:
            dropped += 1

    # Categorize: structural rules PLUS the curator's editorial EFL filters —
    # base charges (from the cost-engine line fit, full coverage), and setup /
    # bundle / credit-card fees and device requirements (from the EFL text, where
    # parseable). A plan with any reason is rejected (and explained in the autopsy).
    baseline = _region_base_baseline(valid)
    honest: list[Plan] = []
    rejected: list[tuple[Plan, list[ReasonCode]]] = []
    for p in valid:
        reasons = flt.structural_reasons(p)
        model = build_cost_model(p)
        if model is not None and (model.base_charge - baseline) > BASE_CHARGE_TOLERANCE:
            reasons.append(ReasonCode.BASE_CHARGE)
        fl = (efl_urls.get(p.efl_url or "") or {}).get("flags") or {}
        if fl.get("setup_fee"):
            reasons.append(ReasonCode.SETUP_FEE)
        if fl.get("bundle_fee"):
            reasons.append(ReasonCode.BUNDLE_FEE)
        if fl.get("cc_fee"):
            reasons.append(ReasonCode.CC_FEE)
        if fl.get("device_required"):
            reasons.append(ReasonCode.DEVICE_REQUIRED)
        (rejected.append((p, reasons)) if reasons else honest.append(p))

    # Annotate each honest plan with its EFL verification status from the cache.
    efl_status: dict[str, str] = {}
    for p in honest:
        rec = efl_urls.get(p.efl_url or "")
        status = rec["status"] if rec else "no_efl"
        efl_status[p.plan_id] = status
        p.efl_verified = status == "verified"

    # Rankings per usage level. The #1 pick must be EFL-verified when any verified
    # plan exists (T1A); otherwise fall back to cheapest, honestly badged as a
    # feed estimate, so a region is never left without an answer.
    rankings = {}
    for u in usage_levels:
        ranked = rank(honest, u)
        pick = top_pick(ranked, require_verified=True) or top_pick(ranked, require_verified=False)
        rankings[str(u)] = {
            "top_pick_id": pick.plan.plan_id if pick else None,
            "plans": [
                {"plan_id": r.plan.plan_id,
                 "monthly_bill": round(r.monthly_bill, 2),
                 "trustworthy_price": r.trustworthy_price}
                for r in ranked
            ],
        }

    # Autopsy list: every rejected plan with its reason codes, verdicts, and the
    # pricing needed to render a shareable "why this is a gimmick" page (incl. the
    # three avg-rate points, whose non-flat shape is the visible tell).
    autopsies = []
    for p, reasons in rejected:
        model = build_cost_model(p)
        autopsies.append({
            "plan_id": p.plan_id,
            "rep": p.rep,
            "product": p.product,
            "reason_codes": [r.value for r in reasons],
            "verdicts": [VERDICT_TEMPLATES[r] for r in reasons],
            "rates": {"500": p.rate500, "1000": p.rate1000, "2000": p.rate2000},
            "bills": {"500": p.bill500, "1000": p.bill1000, "2000": p.bill2000},
            "term_months": p.term_months,
            "cancel_fee": p.cancel_fee,
            "renewable": p.renewable,
            "rate_type": p.rate_type,
            "efl_url": p.efl_url,
            "is_linear": model.is_linear if model else None,
        })

    data = {
        "tdu": tdu,
        "slug": SLUG_BY_TDU.get(tdu, tdu.lower()),
        "language": language,
        "generated_at": generated_at,
        "disclaimer": "Free, no-affiliate. Always verify the plan's EFL before enrolling.",
        "counts": {
            "total": len(region_plans),
            "dropped_invalid": dropped,
            "honest": len(honest),
            "rejected": len(rejected),
            "verified": sum(1 for s in efl_status.values() if s == "verified"),
        },
        "honest_plans": {p.plan_id: _plan_public(p, efl_status.get(p.plan_id, "no_efl")) for p in honest},
        "rankings": rankings,
        "autopsies": autopsies,
    }
    return RegionResult(
        tdu=tdu,
        generated_at=generated_at,
        total_plans=len(region_plans),
        dropped_invalid=dropped,
        honest_count=len(honest),
        rejected_count=len(rejected),
        data=data,
    )
