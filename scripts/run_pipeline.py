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

    manifest = []
    for region in REGION_META:
        result = pipeline.run(plans, region["tdu"], generated_at=now)
        out = result.to_json()
        # public/data -> client fetch (region switching); src/data -> build-time
        # imports (home SSR + autopsy static pages).
        with open(os.path.join(PUBLIC_DIR, f"{region['slug']}.json"), "w", encoding="utf-8") as fh:
            fh.write(out)
        with open(os.path.join(SRC_DIR, f"{region['slug']}.json"), "w", encoding="utf-8") as fh:
            fh.write(out)
        c = result.data["counts"]
        manifest.append({
            "slug": region["slug"], "tdu": region["tdu"],
            "label": region["label"], "cities": region["cities"],
            "counts": c, "generated_at": now,
        })
        print(f"  {region['label']:24s} {c['honest']:3d} honest / {c['rejected']:3d} rejected "
              f"({c['total']} total, {c['dropped_invalid']} dropped)")

    manifest_json = json.dumps({"generated_at": now, "regions": manifest}, indent=2)
    for d in (PUBLIC_DIR, SRC_DIR):
        with open(os.path.join(d, "regions.json"), "w", encoding="utf-8") as fh:
            fh.write(manifest_json)

    print(f"Wrote {len(manifest)} regions + manifest to web/public/data and web/src/data")


if __name__ == "__main__":
    main()
