"""Verify honest plans against their EFLs and cache the result.

For every honest plan, download its EFL and confirm the legally-binding
"Average price per kWh" figures match the PowerToChoose feed. Writes a cache
keyed by EFL URL so the pipeline can set each plan's `efl_verified` flag, and so
re-runs skip URLs already checked.

Output: web/src/data/efl-cache.json
  { "checked_at": ..., "urls": { "<efl_url>": {"status": "verified"|..., "avg": [..]} } }

Non-blocking by design: a plan whose EFL won't download or parse is simply left
"unparseable" (shown, but never the sole #1 recommendation).

Run:  python scripts/verify_efls.py            # offline fixture
      python scripts/verify_efls.py --live      # current PowerToChoose data
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from htx import efl, ingest  # noqa: E402
from htx.filter import is_honest  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "all_plans.json")
OUT_PATH = os.path.join(ROOT, "web", "src", "data", "efl-cache.json")
WORKERS = 8
SAVE_EVERY = 50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()

    plans = ingest.fetch_live() if args.live else ingest.load_json_fixture(FIXTURE)

    # Collect one verification job per unique EFL URL among honest plans.
    jobs: dict[str, tuple[float, float, float]] = {}
    for p in plans:
        if not is_honest(p) or not p.efl_url:
            continue
        if p.rate500 is None or p.rate1000 is None or p.rate2000 is None:
            continue
        jobs.setdefault(p.efl_url, (p.rate500 * 100, p.rate1000 * 100, p.rate2000 * 100))

    cache = {"checked_at": "", "urls": {}}
    if os.path.exists(OUT_PATH):
        cache = json.load(open(OUT_PATH))
    urls = cache["urls"]
    # Re-check anything not cached OR cached before we captured editorial flags.
    todo = [(u, avg) for u, avg in jobs.items()
            if u not in urls or "flags" not in urls[u]]
    print(f"{len(jobs)} honest EFLs · {len(urls)} cached · {len(todo)} to verify")

    def work(url, avg):
        r = efl.verify(url, avg)
        return url, {
            "status": r.status.value,
            "avg": list(r.efl_avg) if r.efl_avg else None,
            "flags": r.flags,
        }

    processed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(work, u, a): u for u, a in todo}
        for fut in as_completed(futs):
            try:
                url, rec = fut.result()
                urls[url] = rec
            except Exception:  # noqa: BLE001
                continue
            processed += 1
            if processed % SAVE_EVERY == 0:
                _save(cache)
                print(f"  {processed}/{len(todo)}...")

    cache["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save(cache)

    counts: dict[str, int] = {}
    for rec in urls.values():
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    print("Done.", counts)
    verified = counts.get("verified", 0)
    print(f"Verified {verified}/{len(urls)} ({100*verified//max(len(urls),1)}%).")


def _save(cache: dict) -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
