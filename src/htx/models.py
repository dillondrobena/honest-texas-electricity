"""Data model: the normalized Plan and the reason codes.

A Plan is normalized from a raw PowerToChoose record (CSV export or JSON API).
Field names below are the canonical internal names; from_ptc_record() maps the
messy PowerToChoose column names onto them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from enum import Enum


# ---------------------------------------------------------------------------
# Regions (TDU = Transmission & Distribution Utility, the wires company).
# Milestone 1 ships Oncor only; the others are here so the schema is stable.
# ---------------------------------------------------------------------------
TDU_ONCOR = "ONCOR"
KNOWN_TDUS = {
    TDU_ONCOR,
    "CENTERPOINT",
    "AEP TEXAS CENTRAL",
    "AEP TEXAS NORTH",
    "TEXAS-NEW MEXICO POWER",
    "LUBBOCK POWER & LIGHT",
}

# The live feed uses full legal TDU names ("ONCOR ELECTRIC DELIVERY COMPANY");
# the curator's spreadsheet used short codes ("ONCOR"). Normalize both onto the
# canonical short codes above. Match order matters: (needles-all-present) -> code.
_TDU_ALIASES = [
    (("CENTERPOINT",), "CENTERPOINT"),
    (("AEP", "CENTRAL"), "AEP TEXAS CENTRAL"),
    (("AEP", "NORTH"), "AEP TEXAS NORTH"),
    (("NEW MEXICO",), "TEXAS-NEW MEXICO POWER"),
    (("LUBBOCK",), "LUBBOCK POWER & LIGHT"),
    (("ONCOR",), TDU_ONCOR),
]


# Region metadata for the frontend: canonical TDU code, a short label, and the
# major cities people recognize (from the spreadsheet's "Find Your Region" tab).
REGION_META = [
    {"slug": "oncor", "tdu": TDU_ONCOR, "label": "Oncor",
     "cities": "Dallas–Fort Worth, Waco, Midland, Odessa, Round Rock"},
    {"slug": "centerpoint", "tdu": "CENTERPOINT", "label": "CenterPoint",
     "cities": "Houston and the Gulf Coast"},
    {"slug": "aep-central", "tdu": "AEP TEXAS CENTRAL", "label": "AEP Texas Central",
     "cities": "Corpus Christi, McAllen, Laredo, Victoria, Harlingen"},
    {"slug": "aep-north", "tdu": "AEP TEXAS NORTH", "label": "AEP Texas North",
     "cities": "Abilene, San Angelo, Vernon"},
    {"slug": "tnmp", "tdu": "TEXAS-NEW MEXICO POWER", "label": "Texas-New Mexico Power",
     "cities": "League City, Angleton, Pecos, Glen Rose"},
    {"slug": "lubbock", "tdu": "LUBBOCK POWER & LIGHT", "label": "Lubbock Power & Light",
     "cities": "Lubbock"},
]

SLUG_BY_TDU = {r["tdu"]: r["slug"] for r in REGION_META}


def normalize_tdu(name) -> str:
    """Map any TDU spelling onto a canonical code. NTU / NUECES are separate
    NTP / co-op markets (not standard TDUs) and are left unmapped so they fall
    out of the region filter rather than being merged into a real TDU."""
    if not name:
        return ""
    u = str(name).strip().upper()
    if "NTU" in u or "NUECES" in u:
        return u  # deliberately unmapped -> not in KNOWN_TDUS
    for needles, canon in _TDU_ALIASES:
        if all(n in u for n in needles):
            return canon
    return u


class ReasonCode(str, Enum):
    """Why a plan was excluded. Verdicts render from these codes, never from
    hand-written per-plan strings (explicit, consistent, testable)."""
    VARIABLE_RATE = "VARIABLE_RATE"      # not a fixed rate: price can change on you
    BILL_CREDIT = "BILL_CREDIT"          # usage-gated credit / fee: a gimmick
    PREPAID = "PREPAID"                  # prepaid product
    TIME_OF_USE = "TIME_OF_USE"          # rate depends on time of day
    NONLINEAR_RATE = "NONLINEAR_RATE"    # price doesn't scale cleanly with usage
                                         # (caught by the cost engine, not a flag)


# Plain-English verdict templates, keyed by reason code. The UI fills these in.
VERDICT_TEMPLATES = {
    ReasonCode.VARIABLE_RATE:
        "Variable rate — the price can change month to month with no cap.",
    ReasonCode.BILL_CREDIT:
        "Has a bill credit or usage fee — the advertised price depends on hitting "
        "a specific usage, and you pay more if you miss it.",
    ReasonCode.PREPAID:
        "Prepaid plan — pay-as-you-go with its own fees, not a straight rate.",
    ReasonCode.TIME_OF_USE:
        "Time-of-use — the rate spikes during certain hours; most homes pay more.",
    ReasonCode.NONLINEAR_RATE:
        "The bill doesn't scale cleanly with usage — a hidden tier or credit kink.",
}


def parse_cancel_fee(raw) -> float | None:
    """Cancel-fee cells are messy free text: '100.0', '20 per month remaining',
    '$150', '20.00 per month remaining term'. Pull out the leading dollar amount;
    return None if there's no number."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"\d+(?:\.\d+)?", str(raw))
    return float(m.group()) if m else None


def _slug(*parts) -> str:
    s = "-".join("" if p is None else str(p) for p in parts).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean(v) -> str | None:
    """Normalize empty-ish cells to None so 'no bill credit' is unambiguous."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


@dataclass
class Plan:
    # identity + display
    plan_id: str
    tdu: str
    rep: str                    # Retail Electric Provider (the seller)
    product: str
    # pricing: three sample points from PowerToChoose (avg rate + total bill)
    rate500: float | None
    bill500: float | None
    rate1000: float | None
    bill1000: float | None
    rate2000: float | None
    bill2000: float | None
    # structural attributes (drive the filter)
    rate_type: str | None        # "Fixed" / "Variable"
    fees_credits: str | None     # non-empty => bill-credit gimmick
    prepaid: bool = False
    time_of_use: bool = False
    # terms + metadata
    term_months: float | None = None
    cancel_fee: float | None = None
    cancel_fee_raw: str | None = None
    renewable: float | None = None
    rating: float | None = None
    efl_url: str | None = None
    enroll_url: str | None = None
    enroll_phone: str | None = None
    new_customer: bool = False
    language: str | None = None
    # EFL verification is a later milestone; every M1 plan is unverified.
    efl_verified: bool = False

    def bill_points(self) -> list[tuple[float, float]]:
        """(kWh, monthly bill) sample points, only the ones present."""
        pts = []
        for kwh, bill in ((500, self.bill500), (1000, self.bill1000), (2000, self.bill2000)):
            if bill is not None:
                pts.append((float(kwh), float(bill)))
        return pts

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in fields})


# Mapping from raw PowerToChoose column names -> Plan. Used by both the xlsx
# fixture builder and the live CSV/API ingestion so there is ONE normalizer.
def from_ptc_record(raw: dict) -> Plan:
    def g(*names):
        for n in names:
            if n in raw:
                return raw[n]
        return None

    tdu = normalize_tdu(_clean(g("TduCompanyName")))
    rep = _clean(g("RepCompany")) or "Unknown"
    product = _clean(g("Product")) or "Unknown"
    term = _to_float(g("TermValue"))
    cancel_raw = g("CancelFee")

    # The curator's spreadsheet had precomputed "Bill @ N" columns; the live feed
    # has only the per-kWh rates. Compute the bill from rate * kWh when the bill
    # column is absent (bill = avg-rate * usage, which is how PTC defines it).
    def _bill(kwh: int, rate, *bill_cols):
        b = _to_float(g(*bill_cols)) if bill_cols else None
        if b is None and rate is not None:
            b = rate * kwh
        return b

    rate500 = _to_float(g("kwh500"))
    rate1000 = _to_float(g("kwh1000"))
    rate2000 = _to_float(g("kwh2000"))

    # Stable identity: prefer the feed's own idKey; fall back to a content slug
    # (the spreadsheet fixtures have no idKey).
    id_key = _clean(g("idKey"))
    plan_id = f"ptc-{id_key}" if id_key else _slug(rep, product, tdu, term)

    return Plan(
        plan_id=plan_id,
        tdu=tdu,
        rep=rep,
        product=product,
        rate500=rate500,
        bill500=_bill(500, rate500, "Bill @ 500", "Bill @500", "bill500"),
        rate1000=rate1000,
        bill1000=_bill(1000, rate1000, "Bill @ 1000", "Bill @1000", "bill1000"),
        rate2000=rate2000,
        bill2000=_bill(2000, rate2000, "Bill @ 2000", "Bill @2000", "bill2000"),
        rate_type=_clean(g("RateType")),
        fees_credits=_clean(g("Fees/Credits")),
        prepaid=_to_bool(g("PrePaid")),
        time_of_use=_to_bool(g("TimeOfUse")),
        term_months=term,
        cancel_fee=parse_cancel_fee(cancel_raw),
        cancel_fee_raw=_clean(cancel_raw),
        renewable=_to_float(g("Renewable")),
        rating=_to_float(g("Rating")),
        efl_url=_clean(g("EFL", "FactsURL")),
        enroll_url=_clean(g("EnrollURL")),
        enroll_phone=_clean(g("EnrollPhone")),
        new_customer=_to_bool(g("NewCustomer")),
        language=_clean(g("Language")),
    )
