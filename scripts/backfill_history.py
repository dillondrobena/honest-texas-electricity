"""One-time backfill of the price-history archive.

An earlier rebase overwrote the August snapshot with a copy of July, so the two
recorded months were identical. This rebuilds history.json honestly:
  2026-07  from the committed July fixture (the real July 20 PowerToChoose data)
  2026-08  from a live PowerToChoose pull (real current data)

Uses the SAME enriched per-plan format as run_pipeline (each plan stores its
¢/kWh at 1,000 kWh plus its name), so the "plans that changed" diff can name
plans that disappear. After this, the normal monthly refresh appends future
months and no backfill is ever needed again.

Run:  python scripts/backfill_history.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from htx import ingest, pipeline  # noqa: E402
from htx.models import REGION_META  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "all_plans.json")
SRC_DIR = os.path.join(ROOT, "web", "src", "data")


def month_snapshot(plans, generated_at: str) -> dict:
    """Per-region price summary for one set of plans (English/canonical)."""
    snap = {}
    for region in REGION_META:
        result = pipeline.run(plans, region["tdu"], generated_at=generated_at, language="English")
        ranked = result.data["rankings"]["1000"]["plans"]
        hp = result.data["honest_plans"]
        cents = sorted(round(r["monthly_bill"] / 1000 * 100, 2) for r in ranked)
        if not cents:
            continue
        snap[region["slug"]] = {
            "avg": round(statistics.fmean(cents), 2),
            "median": round(statistics.median(cents), 2),
            "cheapest": cents[0],
            "honest": len(cents),
            # Keyed by a source-independent name signature so a plan is the same
            # plan across months even when the feed's internal id changes.
            "plans": {
                _sig(hp[r["plan_id"]]): {
                    "c": round(r["monthly_bill"] / 1000 * 100, 2),
                    "n": f"{hp[r['plan_id']]['rep']} — {hp[r['plan_id']]['product']}",
                }
                for r in ranked
            },
        }
    return snap


def _sig(plan: dict) -> str:
    return f"{plan['rep']}|{plan['product']}".lower().strip()


def main() -> None:
    print("Building 2026-07 from the July fixture...")
    july = month_snapshot(ingest.load_json_fixture(FIXTURE), "2026-07-20T00:00:00Z")
    print("Fetching live PowerToChoose for 2026-08...")
    august = month_snapshot(ingest.fetch_live(), "2026-08-01T00:00:00Z")

    history = {
        "updated": "2026-08-01T00:00:00Z",
        "months": {"2026-07": july, "2026-08": august},
    }
    with open(os.path.join(SRC_DIR, "history.json"), "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)

    for m in ("2026-07", "2026-08"):
        o = history["months"][m]["oncor"]
        print(f"  {m}: oncor cheapest {o['cheapest']}¢, {o['honest']} honest plans")
    print("Wrote web/src/data/history.json")


if __name__ == "__main__":
    main()
