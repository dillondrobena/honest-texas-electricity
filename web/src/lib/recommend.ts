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

// ── Preferences ──────────────────────────────────────────────────────────
// Different people optimize for different things. Every option still ranks
// ONLY honest, trustworthy-priced plans — we never surface a gimmick, we just
// let the user weight what matters (and cost always breaks ties).
export type Preference = "cheapest" | "renewable" | "shortest" | "lowcancel" | "rating";

export interface PreferencePick {
  pick: Priced;
  why: string;
  note?: string; // shown when a preference couldn't be fully satisfied
}

const money = (n: number) => `$${n.toFixed(0)}`;

export function pickByPreference(
  data: RegionData,
  usageKwh: number,
  pref: Preference,
): PreferencePick | null {
  const trustworthy = rankHonest(data, usageKwh).filter((r) => r.trustworthy);
  if (trustworthy.length === 0) return null;

  const byCost = (a: Priced, b: Priced) => a.monthlyBill - b.monthlyBill;
  const cents = (r: Priced) => ((r.monthlyBill / usageKwh) * 100).toFixed(1);

  // Build the plan list ordered by the chosen preference (cost breaks ties).
  let sorted = trustworthy;
  let note: string | undefined;
  if (pref === "renewable") {
    const green = trustworthy.filter((r) => (r.plan.renewable ?? 0) >= 100).sort(byCost);
    if (green.length) {
      sorted = green;
    } else {
      sorted = [...trustworthy].sort((a, b) => (b.plan.renewable ?? -1) - (a.plan.renewable ?? -1) || byCost(a, b));
      note = "No 100%-renewable plan passed our honest filter here, so this is the greenest one that did.";
    }
  } else if (pref === "shortest") {
    sorted = [...trustworthy].sort((a, b) => (a.plan.term_months ?? 999) - (b.plan.term_months ?? 999) || byCost(a, b));
  } else if (pref === "lowcancel") {
    sorted = [...trustworthy].sort((a, b) => (a.plan.cancel_fee ?? Infinity) - (b.plan.cancel_fee ?? Infinity) || byCost(a, b));
  } else if (pref === "rating") {
    sorted = [...trustworthy].sort((a, b) => (b.plan.rating ?? -1) - (a.plan.rating ?? -1) || byCost(a, b));
  }

  // Verified-#1 gate (T1A): the top pick must be EFL-verified when any verified
  // plan qualifies. Only fall back to an unverified plan (honestly badged "feed
  // estimate") when nothing verified is available, so there's always an answer.
  const anyVerified = trustworthy.some((r) => r.plan.efl_verified);
  const pick = sorted.find((r) => r.plan.efl_verified) ?? sorted[0];
  if (anyVerified && !pick.plan.efl_verified) {
    note = (note ? note + " " : "") +
      "No EFL-verified plan fit this preference, so this one is a feed estimate — verify its EFL.";
  }

  const p = pick.plan;
  let why: string;
  if (pref === "renewable") {
    why = (p.renewable ?? 0) >= 100
      ? `100% renewable and the cheapest green plan at your usage (${cents(pick)}¢/kWh).`
      : `The greenest honest plan available (${p.renewable ?? 0}% renewable) at ${cents(pick)}¢/kWh.`;
  } else if (pref === "shortest") {
    why = `Shortest honest commitment (${p.term_months ?? "—"} months) at ${cents(pick)}¢/kWh.`;
  } else if (pref === "lowcancel") {
    why = `Lowest early-exit cost (${p.cancel_fee != null ? money(p.cancel_fee) : "—"} cancel fee) among honest plans, at ${cents(pick)}¢/kWh.`;
  } else if (pref === "rating") {
    why = `Best-rated honest provider (${p.rating ?? "—"}/5) at ${cents(pick)}¢/kWh.`;
  } else {
    why = `Lowest true cost at your usage, no bill credit, no minimum-usage fee, and a flat rate that holds across usage levels.`;
  }

  return { pick, why, note };
}
