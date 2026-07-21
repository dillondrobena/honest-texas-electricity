"""Run the Milestone 1 pipeline for Oncor and write the region JSON artifact.

By default it runs OFFLINE against the fixture data (the July snapshot), so you
can see real output without hitting PowerToChoose. Pass --live to fetch the
current CSV export instead.

Run:  python scripts/run_pipeline.py
      python scripts/run_pipeline.py --live
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from htx import ingest, pipeline  # noqa: E402
from htx.models import TDU_ONCOR  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "oncor_all.json")
# The frontend imports this JSON at build time. Committed so the site builds
# without needing to run the Python pipeline; the monthly refresh overwrites it.
OUT_DIR = os.path.join(ROOT, "web", "src", "data")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="fetch live from PowerToChoose")
    args = ap.parse_args()

    if args.live:
        print("Fetching live from PowerToChoose...")
        plans = ingest.fetch_live()
    else:
        print(f"Loading offline fixture: {os.path.relpath(FIXTURE, ROOT)}")
        plans = ingest.load_json_fixture(FIXTURE)

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = pipeline.run(plans, TDU_ONCOR, generated_at=now)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "oncor.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(result.to_json())

    c = result.data["counts"]
    print(f"Oncor: {c['total']} plans -> {c['honest']} honest, "
          f"{c['rejected']} rejected, {c['dropped_invalid']} dropped (data issues)")
    pick = result.data["rankings"]["1000"]["top_pick_id"]
    print(f"Top honest pick @ 1000 kWh: {pick}")
    print(f"Wrote {os.path.relpath(out_path, ROOT)}")


if __name__ == "__main__":
    main()
