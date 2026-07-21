"""EFL parsing + reconciliation (pure functions; no network)."""
from htx.efl import (
    EflStatus,
    contains_triple,
    extract_avg_prices,
    extract_text,
    reconcile,
    verify,
)

# How the PUCT "Average price per kWh" row extracts from a real EFL (¢ becomes junk).
EN_TEXT = (
    "Electricity Price Average Monthly Use 500 kWh 1,000 kWh 2,000 kWh "
    "Average price per kWh 13.3� 12.9� 12.7� "
    "Base Charge $0 Energy Charge 6.412� per kWh Oncor Delivery 6.1196�"
)
ES_TEXT = "Uso mensual promedio 500 kWh Precio promedio por kWh 14.1� 13.7� 13.5�"


def test_extract_english_avg_row():
    assert extract_avg_prices(EN_TEXT) == (13.3, 12.9, 12.7)


def test_extract_spanish_avg_row():
    assert extract_avg_prices(ES_TEXT) == (14.1, 13.7, 13.5)


def test_extract_ignores_absent_row():
    assert extract_avg_prices("no average price row here, just 6.4 and 12") is None


def test_reconcile_within_and_outside_tolerance():
    assert reconcile((13.3, 12.9, 12.7), (13.3, 12.9, 12.72))
    assert not reconcile((13.3, 12.9, 12.7), (13.3, 12.9, 15.0))


def test_contains_triple_is_layout_independent():
    # Numbers scattered by a scrambled table, but the feed triple is present in order.
    scrambled = "col headers 13.3 other 12.9 stuff 12.7 fees $4.06 term 12"
    assert contains_triple(scrambled, (13.3, 12.9, 12.7), 0.3)
    assert not contains_triple(scrambled, (10.0, 9.0, 8.0), 0.3)


def test_verify_no_url_is_no_efl():
    r = verify(None, (12.0, 11.0, 10.0))
    assert r.status == EflStatus.NO_EFL


def test_html_efl_text_extraction_and_parse():
    # Providers that serve the EFL as HTML: tags stripped, entities decoded,
    # then the same avg-price parsing applies.
    html = (
        b"<html><body><script>ignore()</script><table>"
        b"<tr><td>Average price per kWh</td>"
        b"<td>13.3&cent;</td><td>12.9&cent;</td><td>12.7&cent;</td></tr>"
        b"</table></body></html>"
    )
    text = extract_text("html", html)
    assert extract_avg_prices(text) == (13.3, 12.9, 12.7)


def test_extract_rejects_implausible_values():
    # Values outside the residential band shouldn't be treated as avg prices.
    assert extract_avg_prices("Average price per kWh 0.5� 0.4� 0.3�") is None
