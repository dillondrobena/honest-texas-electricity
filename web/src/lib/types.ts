// Shape of the per-region JSON emitted by the Python pipeline
// (see src/htx/pipeline.py). The frontend only READS this; all filtering,
// pricing coefficients, reason codes, and verdicts are computed upstream.

export interface CostModel {
  base_charge: number;
  rate_per_kwh: number;
  is_linear: boolean;
  max_residual: number;
}

export interface HonestPlan {
  plan_id: string;
  rep: string;
  product: string;
  rate_type: string | null;
  term_months: number | null;
  cancel_fee: number | null;
  renewable: number | null;
  rating: number | null;
  efl_url: string | null;
  enroll_url: string | null;
  efl_verified: boolean;
  cost?: CostModel;
}

export interface Autopsy {
  plan_id: string;
  rep: string;
  product: string;
  reason_codes: string[];
  verdicts: string[];
}

export interface RankedEntry {
  plan_id: string;
  monthly_bill: number;
  trustworthy_price: boolean;
}

export interface RegionData {
  tdu: string;
  generated_at: string;
  disclaimer: string;
  counts: { total: number; dropped_invalid: number; honest: number; rejected: number };
  honest_plans: Record<string, HonestPlan>;
  rankings: Record<string, { top_pick_id: string | null; plans: RankedEntry[] }>;
  autopsies: Autopsy[];
}
