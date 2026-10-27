"""Regression tests on committed PDFs. Counts checked against the PDFs by hand."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nerc_caps  # noqa: E402

PDFS = ROOT / "raw" / "pdfs"

# Text PDFs, September 2026. IBEDC is 508: one wrapped feeder name that an earlier parser split in two.
SEPT_2026 = {
    "AEDC-Monthly-Energy-Cap-September-2026.pdf": 642,
    "BEDC-Monthly-Energy-Cap-September-2026.pdf": 243,
    "EEDC-Monthly-Energy-Cap-September-2026.pdf": 17,
    "EKEDP-Monthly-Energy-Cap-September-2026.pdf": 17,
    "IBEDC-Monthly-Energy-Cap-September-2026.pdf": 508,
    "IE-Monthly-Energy-Cap-September-2026.pdf": 34,
    "JED-Monthly-Energy-Cap-September-2026.pdf": 98,
    "KAEDC-Monthly-Energy-Cap-September-2026.pdf": 206,
    "KEDCO-Monthly-Energy-Cap-September-2026.pdf": 158,
    "PHED-Monthly-Energy-Cap-September-2026.pdf": 236,
    "YEDC-Monthly-Energy-Cap-September-2026.pdf": 149,
}


@pytest.mark.parametrize("name,expected", sorted(SEPT_2026.items()))
def test_september_2026_counts(name, expected):
    rows, unparsed = nerc_caps.parse_pdf(PDFS / name)
    assert len(rows) == expected
    assert unparsed == []


@pytest.mark.parametrize("name", ["IE-Monthly-Energy-Cap-September-2026.pdf",
                                  "AEDC-Monthly-Energy-Cap-September-2026.pdf"])
def test_bands_and_caps(name):
    for r in nerc_caps.parse_pdf(PDFS / name)[0]:
        assert r["service_band"] in {"A", "B", "C", "D", "E"}
        assert isinstance(r["cap_kwh"], int) and r["cap_kwh"] > 0


def test_ikeja_first_row():
    r = nerc_caps.parse_pdf(PDFS / "IE-Monthly-Energy-Cap-September-2026.pdf")[0][0]
    assert r["state"] == "OGUN"
    assert r["business_unit"] == "ABULE-EGBA BU"
    assert (r["service_band"], r["cap_kwh"]) == ("C", 226)


def test_old_layout_without_state_column():
    rows, unparsed = nerc_caps.parse_pdf(PDFS / "EEDC-Monthly-Energy-Cap-for-May-2023.pdf")
    assert len(rows) == 314 and unparsed == []
    assert rows[0]["business_unit"] == "ABAKALIKI DISTRICT"
    assert rows[0]["feeder_raw"] == "ABAKALIKI INDUSTRIAL 11KV"


def test_merged_business_unit_cells_are_filled():
    rows, _ = nerc_caps.parse_pdf(PDFS / "EKEDC-Monthly-Energy-Cap-for-October-2022.pdf")
    assert all(r["business_unit"] for r in rows)
    assert rows[0]["business_unit"] == "AGBARA"


def test_scanned_order_uses_committed_ocr_text():
    """Scanned Aba Power, December 2025: rows come from raw/ocr_text, so this runs on any OS."""
    rows, _ = nerc_caps.parse_pdf(PDFS / "APLE-monthly-energy-caps-December-2025.pdf")
    assert len(rows) >= 34
    first = [(r["feeder_raw"], r["service_band"], r["cap_kwh"]) for r in rows[:3]]
    assert first[2][1:] == ("B", 117)  # ABA BARRACKS, band letter recovered by the cell re-read


@pytest.mark.parametrize("title,code", [
    ("Ikeja Electricity Distribution Plc - Monthly Energy Cap (September 2026)", "IKEDC"),
    ("Aba Power Electricity Distribution Plc - Monthly Energy Cap (December 2025)", "APLE"),
    ("Eko Electricity Distribution Plc - Monthly Energy Cap- for October 2022", "EKEDC"),
    ("Port Harcourt Electricity Distribution Plc - Monthly Energy Cap", "PHED"),
])
def test_disco_from_title(title, code):
    assert nerc_caps.disco_from_text(title) == code


def test_month_conflicts_resolved_to_free_slot():
    """Kano named January 2024 (title January 2025) and Enugu named January 2025 (title January 2024)
    both belong in January 2025, where neither DisCo has another order."""
    import pandas as pd
    s = pd.read_csv(ROOT / "data" / "parsed" / "sources.csv")
    assert not s.duplicated(["order_month", "disco"]).any()
    jan25 = s[s["order_month"] == "2025-01"]
    assert {"EEDC", "KEDCO"} <= set(jan25["disco"])


def test_truncated_pdf_is_refused():
    """A cut-off download starts with %PDF but has no %%EOF; it must not be saved or reused."""
    assert nerc_caps.pdf_complete(b"%PDF-1.7\n...\n%%EOF\n")
    assert not nerc_caps.pdf_complete(b"%PDF-1.7\n" + b"x" * 5000)
    assert not nerc_caps.pdf_complete(b"<html>error</html>")


def test_every_committed_pdf_is_complete():
    for p in list((ROOT / "raw" / "pdfs").glob("*.pdf")) + list((ROOT / "raw" / "state").rglob("*.pdf")):
        assert nerc_caps.pdf_complete(p.read_bytes()), p.name


def test_ocr_name_fixes():
    """Capital I read as lowercase l by OCR (docs/KNOWN_EXTRACTION_ERRORS.md rows 8 and 9)."""
    f = nerc_caps.fix_ocr_name
    assert f("11-AgegelNJ-T1-Oko Oba") == "11-AgegeINJ-T1-Oko Oba"
    assert f("11-MagodolN-T1-Shangisha") == "11-MagodoINJ-T1-Shangisha"
    assert f("11-ljaiye OjokorolNJ-T1-Jankara") == "11-Ijaiye OjokoroINJ-T1-Jankara"
    for good in ["11-Abule IrokoINJ-T1-Books", "11-Akute INJ-T1-Ishashi", "OLUWOLE lNJ ROAD"]:
        assert f(good) == good


def test_state_regulator_files():
    """LASERC and EERC files parse completely; EERC's space-stripped July names are restored (rows 19, 20)."""
    import csv
    rows = list(csv.DictReader((ROOT / "data" / "parsed" / "state_caps_all.csv").open(encoding="utf-8")))
    las = [r for r in rows if r["regulator"] == "LASERC" and r["year"] == "2026" and r["month"] == "10"]
    assert len([r for r in las if r["disco"] == "IKEDC"]) == 313
    assert len([r for r in las if r["disco"] == "EKEDC"]) == 217
    july = [r["feeder_raw"] for r in rows if r["regulator"] == "EERC" and r["month"] == "7"]
    assert "ABAKALIKI ROAD 11KV" in july and "ORBA OBOLLO 33KV" in july
    assert not [x for x in july if " " not in x]
