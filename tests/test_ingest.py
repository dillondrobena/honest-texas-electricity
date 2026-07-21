"""Ingestion: live-CSV schema handling (brackets, computed bills) + TDU norm."""
import pytest

from htx.ingest import parse_csv
from htx.models import TDU_ONCOR, normalize_tdu

# A minimal sample in the LIVE feed's shape: [bracketed] headers, per-kWh rates
# only (no precomputed bill columns), full legal TDU name, and an idKey.
LIVE_CSV = (
    "[idKey],[TduCompanyName],[RepCompany],[Product],[kwh500],[kwh1000],[kwh2000],"
    "[Fees/Credits],[PrePaid],[TimeOfUse],[RateType],[Renewable],[TermValue],"
    "[CancelFee],[FactsURL],[Rating]\n"
    "34904,ONCOR ELECTRIC DELIVERY COMPANY,Energy Texas,No Bull 12,0.12,0.12,0.121,"
    ",False,False,Fixed,100,12,20 / remaining month,https://efl.example/604912,3\n"
    "40001,CENTERPOINT ENERGY HOUSTON ELECTRIC LLC,Acme,Gimmick 12,0.06,0.11,0.13,"
    "$100 usage credit,False,False,Fixed,20,12,150,https://efl.example/x,2\n"
)


def test_parse_live_csv_strips_brackets_and_maps_fields():
    plans = parse_csv(LIVE_CSV)
    assert len(plans) == 2
    p = plans[0]
    assert p.rep == "Energy Texas"
    assert p.product == "No Bull 12"
    assert p.rate_type == "Fixed"
    assert p.efl_url == "https://efl.example/604912"  # FactsURL -> efl_url
    assert p.plan_id == "ptc-34904"                     # idKey -> stable id
    assert p.cancel_fee == 20.0                          # parsed from messy text


def test_bills_are_computed_from_rates_when_absent():
    p = parse_csv(LIVE_CSV)[0]
    assert p.bill500 == pytest.approx(0.12 * 500)   # 60
    assert p.bill1000 == pytest.approx(0.12 * 1000)  # 120
    assert p.bill2000 == pytest.approx(0.121 * 2000)  # 242


def test_live_tdu_names_normalize_to_short_codes():
    plans = parse_csv(LIVE_CSV)
    assert plans[0].tdu == TDU_ONCOR
    assert plans[1].tdu == "CENTERPOINT"


def test_bill_credit_field_survives_for_the_filter():
    gimmick = parse_csv(LIVE_CSV)[1]
    assert gimmick.fees_credits == "$100 usage credit"


def test_schema_drift_raises():
    with pytest.raises(ValueError, match="schema drift"):
        parse_csv("[idKey],[RepCompany]\n1,Acme\n")  # missing required columns


def test_normalize_tdu_variants():
    assert normalize_tdu("ONCOR ELECTRIC DELIVERY COMPANY") == TDU_ONCOR
    assert normalize_tdu("ONCOR") == TDU_ONCOR
    assert normalize_tdu("AEP TEXAS CENTRAL COMPANY") == "AEP TEXAS CENTRAL"
    assert normalize_tdu("AEP TEXAS NORTH COMPANY") == "AEP TEXAS NORTH"
    assert normalize_tdu("TEXAS-NEW MEXICO POWER COMPANY") == "TEXAS-NEW MEXICO POWER"
    assert normalize_tdu("LUBBOCK POWER & LIGHT SYSTEM") == "LUBBOCK POWER & LIGHT"


def test_ntu_and_nueces_not_merged_into_a_real_tdu():
    # These are separate NTP/co-op markets; they must NOT become Oncor/etc.
    assert normalize_tdu("Oncor Electric Delivery Company NTU LLC") != TDU_ONCOR
    assert normalize_tdu("NUECES ELECTRIC COOPERATIVE") not in {
        TDU_ONCOR, "CENTERPOINT", "AEP TEXAS CENTRAL", "AEP TEXAS NORTH",
        "TEXAS-NEW MEXICO POWER", "LUBBOCK POWER & LIGHT",
    }
    assert normalize_tdu(None) == ""
