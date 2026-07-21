"""Run the pipeline for every TDU region and write the frontend data artifacts.

Writes, from ONE data pull:
  web/public/data/<slug>.json   per-region honest list + rankings + autopsies
  web/public/data/regions.json  manifest (slug, label, cities, counts, generated_at)
  web/src/data/oncor.json       default region, imported at build time for SSR
  web/src/data/regions.json     manifest, imported at build time for the selector

Offline (default) runs against the committed all-regions fixture; --live pulls the
current CSV export from PowerToChoose.

Run:  python scripts/run_pipeline.py           # offline (fixture)
      python scripts/run_pipeline.py --live     # live fetch
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from htx import ingest, pipeline  # noqa: E402
from htx.models import REGION_META  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "all_plans.json")
PUBLIC_DIR = os.path.join(ROOT, "web", "public", "data")
SRC_DIR = os.path.join(ROOT, "web", "src", "data")
DEFAULT_SLUG = "oncor"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="fetch live from PowerToChoose")
    args = ap.parse_args()

    if args.live:
        print("Fetching live from PowerToChoose (all regions)...")
        plans = ingest.fetch_live()
    else:
        print(f"Loading offline fixture: {os.path.relpath(FIXTURE, ROOT)}")
        plans = ingest.load_json_fixture(FIXTURE)

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    os.makedirs(SRC_DIR, exist_ok=True)

    # EFL verification cache (from scripts/verify_efls.py), if present.
    efl_cache = None
    efl_path = os.path.join(SRC_DIR, "efl-cache.json")
    if os.path.exists(efl_path):
        efl_cache = json.load(open(efl_path, encoding="utf-8"))
        print(f"Loaded EFL cache: {len(efl_cache.get('urls', {}))} verified/checked EFLs")

    month = now[:7]  # YYYY-MM
    history_month = {}  # per-region price summary for this run's month

    manifest = []
    for region in REGION_META:
        # Two languages: English is canonical (drives the manifest + history);
        # Spanish is written alongside as <slug>.es.json for the Spanish site.
        for language, suffix in (("English", ""), ("Spanish", ".es")):
            result = pipeline.run(plans, region["tdu"], generated_at=now,
                                  efl_cache=efl_cache, language=language)
            out = result.to_json()
            fname = f"{region['slug']}{suffix}.json"
            # public/data -> client fetch (region switching); src/data -> build-time
            # imports (home SSR + autopsy static pages).
            with open(os.path.join(PUBLIC_DIR, fname), "w", encoding="utf-8") as fh:
                fh.write(out)
            with open(os.path.join(SRC_DIR, fname), "w", encoding="utf-8") as fh:
                fh.write(out)
            c = result.data["counts"]
            if language == "English":
                # Monthly price archive uses the canonical (English) list.
                ranked = result.data["rankings"]["1000"]["plans"]
                cents = sorted(round(r["monthly_bill"] / 1000 * 100, 2) for r in ranked)
                if cents:
                    history_month[region["slug"]] = {
                        "avg": round(statistics.fmean(cents), 2),
                        "median": round(statistics.median(cents), 2),
                        "cheapest": cents[0],
                        "honest": len(cents),
                        "plans": {r["plan_id"]: round(r["monthly_bill"] / 1000 * 100, 2) for r in ranked},
                    }
                manifest.append({
                    "slug": region["slug"], "tdu": region["tdu"],
                    "label": region["label"], "cities": region["cities"],
                    "counts": c, "generated_at": now,
                })
            print(f"  {region['label']:20s} [{language[:2]}] {c['honest']:3d} honest / {c['rejected']:3d} rejected")

    manifest_json = json.dumps({"generated_at": now, "regions": manifest}, indent=2)
    for d in (PUBLIC_DIR, SRC_DIR):
        with open(os.path.join(d, "regions.json"), "w", encoding="utf-8") as fh:
            fh.write(manifest_json)

    # Merge this month into the price history archive (idempotent per month; past
    # months are preserved). The trend charts grow as months accumulate.
    history_path = os.path.join(SRC_DIR, "history.json")
    history = {"months": {}}
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as fh:
            history = json.load(fh)
    history["months"][month] = history_month
    history["updated"] = now
    with open(history_path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2)

    print(f"Wrote {len(manifest)} regions + manifest to web/public/data and web/src/data")
    print(f"Recorded price history for {month} ({len(history['months'])} month(s) tracked)")


if __name__ == "__main__":
    main()
