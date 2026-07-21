"""EFL verification — confirm the feed's price matches the legally-binding doc.

Every Texas plan must publish an Electricity Facts Label (EFL) in a PUCT-mandated
format that includes an "Average price per kWh" row at 500 / 1,000 / 2,000 kWh.
We download the EFL PDF, extract those three numbers, and reconcile them against
the PowerToChoose feed. If they match, the plan is VERIFIED — the numbers we show
are backed by the legal document. If they disagree, that's the exact trust-killer
we exist to catch, and the plan is flagged, not trusted.

Guardrail (decision 3C): this is per-plan and NON-BLOCKING. Any download or parse
failure returns an "unparseable" status; it never raises, so a brittle PDF can
never halt a data refresh. Unverified plans still appear — just badged, and never
the sole #1 recommendation.
"""
from __future__ import annotations

import io
import re
import urllib.request
from dataclasses import dataclass
from enum import Enum

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# Match against the feed's avg-¢/kWh at each point. 0.3¢ absorbs rounding between
# the EFL's published figure and our reconstructed feed average.
MATCH_TOLERANCE_CENTS = 0.3

# The "Average price per kWh" row, in English or Spanish, followed by three cent
# figures. The ¢ symbol and column gaps render as assorted junk when extracted,
# so we skip non-digits between the numbers. "in ¢"/"in cents" variants allowed.
_AVG_RE = re.compile(
    r"(?:average\s*price(?:\s*in\s*\S*)?\s*per\s*kwh"
    r"|precio\s*promedio\s*por\s*kwh)\D{0,14}"
    r"(\d{1,2}\.\d{1,3})\D{1,8}(\d{1,2}\.\d{1,3})\D{1,8}(\d{1,2}\.\d{1,3})",
    re.IGNORECASE,
)

# Any decimal that could be a cents-per-kWh figure (used by the fallback scan).
_NUM_RE = re.compile(r"\d{1,2}\.\d{1,3}")


class EflStatus(str, Enum):
    VERIFIED = "verified"        # EFL numbers match the feed
    MISMATCH = "mismatch"        # EFL numbers found but disagree with the feed
    UNPARSEABLE = "unparseable"  # couldn't download/parse the EFL
    NO_EFL = "no_efl"            # plan has no EFL URL


@dataclass
class EflResult:
    status: EflStatus
    efl_avg: tuple[float, float, float] | None = None  # ¢/kWh at 500/1000/2000
    detail: str = ""

    @property
    def verified(self) -> bool:
        return self.status == EflStatus.VERIFIED


def fetch_pdf(url: str, timeout: float = 25.0) -> bytes | None:
    """Download an EFL. Returns the bytes only if it's actually a PDF."""
    # Some feed URLs contain stray whitespace/control chars — reject cleanly.
    if not url or any(ord(c) < 32 for c in url):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except Exception:  # noqa: BLE001 - non-blocking by contract
        return None
    return body if body[:4] == b"%PDF" else None


def extract_text(pdf_bytes: bytes) -> str | None:
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001
        return None


def _plausible(vals: tuple[float, float, float]) -> bool:
    return all(3.0 <= v <= 45.0 for v in vals)


def extract_avg_prices(text: str) -> tuple[float, float, float] | None:
    """Pull the three labeled 'Average price per kWh' figures (EN or ES)."""
    m = _AVG_RE.search(text)
    if not m:
        return None
    try:
        vals = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    except ValueError:
        return None
    return vals if _plausible(vals) else None


def contains_triple(text: str, feed_avg: tuple[float, float, float], tolerance: float) -> bool:
    """Layout/language-independent fallback: does the document contain our three
    price numbers in order? Three specific figures matching by chance is
    vanishingly unlikely, so a hit is strong evidence the EFL backs the price."""
    nums = [float(x) for x in _NUM_RE.findall(text)]
    for i in range(len(nums) - 2):
        triple = (nums[i], nums[i + 1], nums[i + 2])
        if reconcile(triple, feed_avg, tolerance):
            return True
    return False


def reconcile(
    efl_avg: tuple[float, float, float],
    feed_avg: tuple[float, float, float],
    tolerance: float = MATCH_TOLERANCE_CENTS,
) -> bool:
    """True when every EFL figure matches the corresponding feed average."""
    return all(abs(e - f) <= tolerance for e, f in zip(efl_avg, feed_avg))


def verify(url: str | None, feed_avg: tuple[float, float, float]) -> EflResult:
    """Full per-plan verification. Never raises."""
    if not url:
        return EflResult(EflStatus.NO_EFL, detail="no EFL URL")
    pdf = fetch_pdf(url)
    if pdf is None:
        return EflResult(EflStatus.UNPARSEABLE, detail="download failed or not a PDF")
    text = extract_text(pdf)
    if not text:
        return EflResult(EflStatus.UNPARSEABLE, detail="no extractable text")

    # Primary: the labeled avg-price row. Lets us detect a real MISMATCH — the
    # exact case (feed disagrees with the legal doc) we most need to catch.
    efl_avg = extract_avg_prices(text)
    if efl_avg is not None:
        if reconcile(efl_avg, feed_avg):
            return EflResult(EflStatus.VERIFIED, efl_avg=efl_avg)
        return EflResult(
            EflStatus.MISMATCH,
            efl_avg=efl_avg,
            detail=f"EFL {efl_avg} vs feed {tuple(round(f, 1) for f in feed_avg)}",
        )

    # Fallback: the label didn't parse (odd layout/language), but if our three
    # numbers are present in order, the doc backs the price.
    if contains_triple(text, feed_avg, MATCH_TOLERANCE_CENTS):
        return EflResult(EflStatus.VERIFIED, efl_avg=feed_avg)
    return EflResult(EflStatus.UNPARSEABLE, detail="avg-price figures not found")
