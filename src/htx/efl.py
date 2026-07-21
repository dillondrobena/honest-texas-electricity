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
    flags: dict | None = None  # editorial gotchas read from the EFL text

    @property
    def verified(self) -> bool:
        return self.status == EflStatus.VERIFIED


def _sanitize_url(url: str) -> str:
    """Some feed URLs carry stray whitespace/newlines. Strip control chars
    rather than reject, so an otherwise-valid EFL link still resolves."""
    return "".join(c for c in url.strip() if ord(c) >= 32)


def fetch(url: str, timeout: float = 25.0) -> tuple[str, bytes] | None:
    """Download an EFL. Returns (kind, body) where kind is 'pdf' or 'html'."""
    url = _sanitize_url(url)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read()
    except Exception:  # noqa: BLE001 - non-blocking by contract
        return None
    if body[:4] == b"%PDF":
        return ("pdf", body)
    # Everything else we treat as HTML and strip tags — many providers serve the
    # EFL as an HTML page rather than a PDF.
    return ("html", body)


_TAG_RE = re.compile(r"(?s)<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")


def _strip_html(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    text = _SCRIPT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = (text.replace("&cent;", "¢").replace("&nbsp;", " ")
                .replace("&amp;", "&").replace("&#162;", "¢"))
    return re.sub(r"\s+", " ", text)


def _pypdf_text(body: bytes) -> str | None:
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(body))
        return " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001
        return None


def _pdfplumber_text(body: bytes) -> str | None:
    """Stronger (slower) PDF extractor, used only when pypdf's text doesn't
    parse. Recovers many tabular EFLs pypdf scrambles. Optional dependency."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(body)) as pdf:
            return " ".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:  # noqa: BLE001
        return None


def extract_text(kind: str, body: bytes) -> str | None:
    """Primary text for a document (pypdf for PDFs, tag-strip for HTML)."""
    return _pypdf_text(body) if kind == "pdf" else _strip_html(body)


def _classify(text: str, feed_avg: tuple[float, float, float]) -> EflResult | None:
    """Parse+reconcile one text blob. Returns a verified/mismatch result, or
    None if this text yielded nothing (so a caller can try another extractor)."""
    labeled = extract_avg_prices(text)
    if labeled is not None:
        if reconcile(labeled, feed_avg):
            return EflResult(EflStatus.VERIFIED, efl_avg=labeled)
        return EflResult(
            EflStatus.MISMATCH, efl_avg=labeled,
            detail=f"EFL {labeled} vs feed {tuple(round(f, 1) for f in feed_avg)}",
        )
    if contains_triple(text, feed_avg, MATCH_TOLERANCE_CENTS):
        return EflResult(EflStatus.VERIFIED, efl_avg=feed_avg)
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


# Editorial gotchas the curator reads out of each EFL. Deliberately conservative
# (require fee/require context) — a false exclusion of an honest plan is worse
# than missing a rare fee, and the big one (base charge) is caught precisely by
# the cost-engine line fit, not here.
_EFL_BASE = re.compile(r"base\s*charge[^$A-Za-z]{0,12}\$\s*(\d+(?:\.\d+)?)", re.I)
_EFL_SETUP = re.compile(r"(enrollment|set[\s-]?up|activation)\s*fee", re.I)
_EFL_BUNDLE = re.compile(r"(bundle|membership|subscription)\s*(?:fee|charge|cost)", re.I)
_EFL_CC = re.compile(
    r"credit\s*card[^.]{0,30}(?:fee|surcharge|processing)|processing\s*fee|convenience\s*fee",
    re.I,
)
_EFL_DEVICE = re.compile(
    r"(?:thermostat|smart\s*device)[^.]{0,40}(?:requir|must|connect|enroll)"
    r"|(?:requir|must)[^.]{0,40}(?:thermostat|smart\s*device)",
    re.I,
)


def extract_flags(text: str) -> dict:
    """Editorial gotcha flags from EFL text (all conservative keyword scans).
    `base_charge` is the REP's flat monthly fee if the EFL states one."""
    base = None
    m = _EFL_BASE.search(text)
    if m:
        try:
            base = float(m.group(1))
        except ValueError:
            base = None
    return {
        "base_charge": base,
        "setup_fee": bool(_EFL_SETUP.search(text)),
        "bundle_fee": bool(_EFL_BUNDLE.search(text)),
        "cc_fee": bool(_EFL_CC.search(text)),
        "device_required": bool(_EFL_DEVICE.search(text)),
    }


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
    fetched = fetch(url)
    if fetched is None:
        return EflResult(EflStatus.UNPARSEABLE, detail="download failed")
    kind, body = fetched

    # Try each available extractor in turn (pypdf, then the stronger pdfplumber
    # for PDFs; tag-strip for HTML). The first that yields a verified/mismatch
    # result wins — a MISMATCH is a real finding, not something to "fix" with a
    # second extractor.
    extractors = (_pypdf_text, _pdfplumber_text) if kind == "pdf" else (lambda b: _strip_html(b),)
    flags = None
    for extract in extractors:
        text = extract(body)
        if not text:
            continue
        if flags is None:
            flags = extract_flags(text)  # editorial gotchas from whatever text we got
        result = _classify(text, feed_avg)
        if result is not None:
            result.flags = flags
            return result
    return EflResult(EflStatus.UNPARSEABLE, detail="avg-price figures not found", flags=flags)
