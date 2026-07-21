// Client-side re-ranking at an arbitrary usage.
//
// This is ARITHMETIC on precomputed coefficients, not a re-implementation of the
// editorial filter. The pipeline already decided which plans are honest and gave
// each one {base_charge, rate_per_kwh}; here we just evaluate bill = base + rate*U
// and apply the same published tie-break ladder as recommend.py so the answer
// updates live as the user drags the usage slider.

import type { HonestPlan, RegionData } from "./types";

export interface Priced {
  plan: HonestPlan;
  monthlyBill: number;
  trustworthy: boolean;
}

export function billAt(plan: HonestPlan, usageKwh: number): number | null {
  if (!plan.cost) return null;
  return plan.cost.base_charge + plan.cost.rate_per_kwh * usageKwh;
}

// Same ordering as the Python sort_key: cheapest, then lower cancel fee, higher
// rating, shorter term, higher renewable.
function compare(a: Priced, b: Priced): number {
  const round2 = (n: number) => Math.round(n * 100) / 100;
  return (
    round2(a.monthlyBill) - round2(b.monthlyBill) ||
    (a.plan.cancel_fee ?? Infinity) - (b.plan.cancel_fee ?? Infinity) ||
    (b.plan.rating ?? -1) - (a.plan.rating ?? -1) ||
    (a.plan.term_months ?? Infinity) - (b.plan.term_months ?? Infinity) ||
    (b.plan.renewable ?? -1) - (a.plan.renewable ?? -1)
  );
}

export function rankHonest(data: RegionData, usageKwh: number): Priced[] {
  const priced: Priced[] = [];
  for (const plan of Object.values(data.honest_plans)) {
    const bill = billAt(plan, usageKwh);
    if (bill === null) continue;
    priced.push({ plan, monthlyBill: bill, trustworthy: plan.cost!.is_linear });
  }
  priced.sort(compare);
  return priced;
}

// The single honest #1: cheapest with a trustworthy (linear) price. When
// requireVerified is on (once the EFL milestone lands) it must also be
// EFL-verified. In M1 nothing is verified yet, so the default is false.
export function topPick(ranked: Priced[], requireVerified = false): Priced | null {
  for (const r of ranked) {
    if (!r.trustworthy) continue;
    if (requireVerified && !r.plan.efl_verified) continue;
    return r;
  }
  return null;
}
