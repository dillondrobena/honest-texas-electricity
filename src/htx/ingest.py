"""Ingestion — get raw plan records into normalized Plans.

Live source (decision 2A): the PowerToChoose CSV export is primary; the
undocumented JSON API is the fallback. Both are parsed through the SAME
normalizer (models.from_ptc_record). On any schema surprise we raise so the
pipeline keeps the last-good snapshot rather than publishing garbage.

Offline sources: JSON fixtures (canonical Plan dicts) for tests, and a list of
raw records (used by the fixture builder that reads the source spreadsheet).
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request

from .models import Plan, from_ptc_record

CSV_EXPORT_URL = "http://www.powertochoose.org/en-us/Plan/ExportToCsv"
JSON_API_URL = "http://api.powertochoose.org/api/PowerToChoose/plans/"

# PowerToChoose sits behind a WAF that 403s the default urllib User-Agent, so we
# present a normal browser UA. (No auth, no cookies — this is public PUC data.)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,application/json,*/*",
}

# Minimum columns we must see in a CSV pull, or the schema has drifted. The live
# feed wraps headers in [brackets]; parse_csv strips them before this check.
REQUIRED_COLUMNS = {"TduCompanyName", "RepCompany", "Product", "RateType", "kwh1000"}


def _strip_bracket(header: str) -> str:
    """'[TduCompanyName]' -> 'TduCompanyName' (live feed) / leaves plain names."""
    return header.strip().strip("[]").strip()


def load_records(raw_records: list[dict]) -> list[Plan]:
    """Normalize a list of raw PowerToChoose records (dict per plan)."""
    return [from_ptc_record(r) for r in raw_records]


def load_json_fixture(path: str) -> list[Plan]:
    """Load canonical Plan dicts (as written by build_fixtures)."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [Plan.from_dict(d) for d in data]


def parse_csv(text: str) -> list[Plan]:
    """Parse a PowerToChoose CSV export into Plans. Raises on schema drift.

    Handles the live feed's [bracketed] headers and its lack of precomputed bill
    columns (models.from_ptc_record computes bill = rate * kWh)."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("empty CSV: no rows")
    header = [_strip_bracket(h) for h in rows[0]]
    missing = REQUIRED_COLUMNS - set(header)
    if missing:
        raise ValueError(f"CSV schema drift: missing columns {sorted(missing)}")
    plans = [
        from_ptc_record(dict(zip(header, r)))
        for r in rows[1:]
        if any((c or "").strip() for c in r)
    ]
    if not plans:
        raise ValueError("CSV had a header but no data rows")
    return plans


def _get(url: str, timeout: float, data: bytes | None = None) -> str:
    headers = dict(BROWSER_HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # The export is UTF-8 with a BOM; utf-8-sig strips it so the first header
        # isn't polluted.
        return resp.read().decode("utf-8-sig", errors="replace")


def fetch_live(timeout: float = 30.0) -> list[Plan]:
    """Fetch from the live CSV export (primary), falling back to the JSON API.

    Not exercised by the offline test suite; the tested path is parse_csv against
    a fixture. Kept defensive so a feed change fails loudly, never silently."""
    try:
        return parse_csv(_get(CSV_EXPORT_URL, timeout))
    except Exception as csv_err:  # noqa: BLE001 - fall back, then re-raise below
        try:
            # The API needs a POST search body; a bare GET returns an empty set.
            # Best-effort fallback (schema is undocumented) — validated below.
            body = json.dumps({"zipcode": "", "tdsp": ""}).encode()
            payload = json.loads(_get(JSON_API_URL, timeout, data=body))
            records = payload.get("data") if isinstance(payload, dict) else payload
            plans = load_records(records or [])
            if not plans:
                raise ValueError("JSON API returned no plans (needs a valid search)")
            return plans
        except Exception as api_err:  # noqa: BLE001
            raise RuntimeError(
                f"both PowerToChoose sources failed. CSV: {csv_err}; API: {api_err}"
            ) from api_err
