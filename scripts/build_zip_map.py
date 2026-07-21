"""Build the authoritative Texas ZIP -> region map.

For every real Texas ZIP code (from GeoNames), ask PowerToChoose's own ZIP
lookup which TDU serves it. That's the authoritative answer to "what can this
address actually buy" — and it correctly reports non-deregulated areas (Austin,
San Antonio, El Paso, most co-ops) as having no competitive plans.

Output: web/src/data/zip-tdu.json
  { "generated_at": ..., "zips": { "75201": "oncor", "78701": "none", ... } }
  slug  = one of our six covered regions
  "none" = a real Texas ZIP with no competitive plans we can show (non-deregulated
           or a tiny TDU/co-op we don't cover)

Resumable: re-running skips ZIPs already resolved, so a network hiccup is safe.

Run:  python scripts/build_zip_map.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from htx.models import SLUG_BY_TDU, normalize_tdu  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(ROOT, "web", "src", "data", "zip-tdu.json")
CACHE_DIR = os.path.join(ROOT, "data")
TX_ZIPS_CACHE = os.path.join(CACHE_DIR, "tx_zips.json")

GEONAMES_URL = "http://download.geonames.org/export/zip/US.zip"
API = "http://api.powertochoose.org/api/PowerToChoose/plans?zip_code={zip}&estimated_use=Any"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
WORKERS = 6
SAVE_EVERY = 100


def texas_zips() -> list[str]:
    if os.path.exists(TX_ZIPS_CACHE):
        return json.load(open(TX_ZIPS_CACHE))
    print("Downloading GeoNames US postal codes...")
    req = urllib.request.Request(GEONAMES_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        blob = resp.read()
    tx = set()
    with zipfile.ZipFile(BytesIO(blob)) as z:
        for line in z.read("US.txt").decode("utf-8").splitlines():
            f = line.split("\t")
            if len(f) >= 5 and f[4] == "TX":
                tx.add(f[1])
    os.makedirs(CACHE_DIR, exist_ok=True)
    json.dump(sorted(tx), open(TX_ZIPS_CACHE, "w"))
    return sorted(tx)


def resolve(zip_code: str) -> str:
    """Return the region slug for a ZIP, or 'none' if no covered competitive plan."""
    url = API.format(zip=zip_code)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            data = payload.get("data") or []
            if not data:
                return "none"
            tdu = normalize_tdu(data[0].get("company_tdu_name"))
            return SLUG_BY_TDU.get(tdu, "none")
        except Exception:  # noqa: BLE001
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"failed to resolve {zip_code}")


def main() -> None:
    zips = texas_zips()
    result = {"generated_at": "", "zips": {}}
    if os.path.exists(OUT_PATH):
        result = json.load(open(OUT_PATH))
    done = result["zips"]
    todo = [z for z in zips if z not in done]
    print(f"{len(zips)} TX ZIPs · {len(done)} already resolved · {len(todo)} to go")

    processed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(resolve, z): z for z in todo}
        for fut in as_completed(futures):
            z = futures[fut]
            try:
                done[z] = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  skip {z}: {e}")
                continue
            processed += 1
            if processed % SAVE_EVERY == 0:
                _save(result)
                print(f"  {processed}/{len(todo)} resolved...")

    result["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save(result)

    covered = sum(1 for v in done.values() if v != "none")
    print(f"Done. {len(done)} ZIPs resolved, {covered} in a covered region, "
          f"{len(done) - covered} non-deregulated/uncovered.")


def _save(result: dict) -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
