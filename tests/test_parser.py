"""Regression tests on committed PDFs. September 2026 counts were checked against the PDFs."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nerc_caps  # noqa: E402

PDFS = ROOT / "raw" / "pdfs"

SEPT_2026 = {
    "AEDC-Monthly-Energy-Cap-September-2026.pdf": 642,
    "BEDC-Monthly-Energy-Cap-September-2026.pdf": 243,
    "EEDC-Monthly-Energy-Cap-September-2026.pdf": 17,
    "EKEDP-Monthly-Energy-Cap-September-2026.pdf": 17,
    "IBEDC-Monthly-Energy-Cap-September-2026.pdf": 509,
    "IE-Monthly-Energy-Cap-September-2026.pdf": 34,
    "JED-Monthly-Energy-Cap-September-2026.pdf": 98,
    "KAEDC-Monthly-Energy-Cap-September-2026.pdf": 206,
    "KEDCO-Monthly-Energy-Cap-September-2026.pdf": 158,
    "PHED-Monthly-Energy-Cap-September-2026.pdf": 236,
    "YEDC-Monthly-Energy-Cap-September-2026.pdf": 149,
}


def parse(name):
    """Return (rows, unparsed) whether parse_pdf returns a tuple or a dict."""
    res = nerc_caps.parse_pdf(PDFS / name)
    if isinstance(res, dict):
        return res["rows"], res["unparsed"]
    return res[0], res[1]


@pytest.mark.parametrize("name,expected", sorted(SEPT_2026.items()))
def test_september_2026_counts(name, expected):
    rows, unparsed = parse(name)
    assert len(rows) == expected
    assert unparsed == []


def test_september_2026_total():
    assert sum(len(parse(n)[0]) for n in SEPT_2026) == 2309


@pytest.mark.parametrize("name", ["IE-Monthly-Energy-Cap-September-2026.pdf",
                                  "AEDC-Monthly-Energy-Cap-September-2026.pdf"])
def test_bands_and_caps_in_parsed_rows(name):
    for r in parse(name)[0]:
        assert r["service_band"] in {"A", "B", "C", "D", "E"}
        assert isinstance(r["cap_kwh"], int) and r["cap_kwh"] > 0


def test_ikeja_first_row():
    r = parse("IE-Monthly-Energy-Cap-September-2026.pdf")[0][0]
    assert r["state"] == "OGUN"
    assert r["business_unit"] == "ABULE-EGBA BU"
    assert (r["service_band"], r["cap_kwh"]) == ("C", 226)


def test_wrapped_row_keeps_both_halves():
    """'FCT APO AT3_H37_S26_BEHIND' + 'TRANSMISSION A 838' is one row, not a truncated one."""
    rows = parse("AEDC-Monthly-Energy-Cap-September-2026.pdf")[0]
    hits = [r for r in rows if r["cap_kwh"] == 838 and r["service_band"] == "A"]
    assert len(hits) == 1
    text = " ".join(str(v) for v in hits[0].values())
    assert "BEHIND" in text and "TRANSMISSION" in text


def test_month_filter_accepts_abbreviations():
    """August 2026 files are named '...-Aug-2026.pdf' and must not be missed."""
    fn = getattr(nerc_caps, "period_from_text", None)
    if fn is None:
        pytest.skip("parser has no period_from_text helper")
    assert fn("EEDC-monthly-energy-caps-Aug-2026.pdf") == (2026, 8)
    assert fn("AEDC-monthly-energy-caps-Feb-2026.pdf") == (2026, 2)
    assert fn("Eko-Electricity-Distribution-Plc.-Monthly-Energy-CapSeptember-2025.pdf") == (2025, 9)
    assert fn("AEDCMonthlyEnergyCapforFebruary2024.pdf") == (2024, 2)


def test_feeder_key_normalisation():
    fn = getattr(nerc_caps, "feeder_key", None)
    if fn is None:
        pytest.skip("parser has no feeder_key helper")
    assert fn("Abule  Iroko") == fn("ABULE IROKO")
    assert "/" in fn("Kubwa 33kV/11kV")
    assert fn("11-Abule.Iroko") == fn("11 Abule Iroko")
