"""ZIP -> TDU (wires-company / region) mapping.

Milestone 1 ships a small seed map plus an honest fallback. Some Texas ZIPs
span two TDUs; those return multiple candidates so the UI can ask the user to
confirm their utility rather than silently guessing (decision: no silent wrong
answers). A full address/ESI-ID lookup is a later precision upgrade (see TODOS).
"""
from __future__ import annotations

from .models import TDU_ONCOR

# Seed: a handful of unambiguous ZIPs per region for Milestone 1 (Oncor focus).
# Real coverage comes from a sourced ZIP->TDU dataset in a later milestone.
_SEED: dict[str, list[str]] = {
    # Oncor (Dallas / Fort Worth / Waco / Midland-Odessa / Round Rock)
    "75201": [TDU_ONCOR], "75202": [TDU_ONCOR], "76101": [TDU_ONCOR],
    "76701": [TDU_ONCOR], "79701": [TDU_ONCOR], "78664": [TDU_ONCOR],
    # CenterPoint (Houston)
    "77002": ["CENTERPOINT"], "77004": ["CENTERPOINT"],
    # AEP Central (Corpus Christi), AEP North (Abilene)
    "78401": ["AEP TEXAS CENTRAL"], "79601": ["AEP TEXAS NORTH"],
    # TNMP (League City), Lubbock
    "77573": ["TEXAS-NEW MEXICO POWER"], "79401": ["LUBBOCK POWER & LIGHT"],
}


def lookup(zip_code: str) -> list[str]:
    """Return candidate TDUs for a ZIP. Empty list means we don't know it yet
    (the UI should say so, not guess). More than one means: ask the user."""
    return list(_SEED.get(str(zip_code).strip()[:5], []))


def is_ambiguous(zip_code: str) -> bool:
    return len(lookup(zip_code)) > 1
