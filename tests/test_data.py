"""Integrity checks on the published tables."""
import glob
import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICT = (ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
STATES = {"ABIA", "ADAMAWA", "AKWA IBOM", "ANAMBRA", "BAUCHI", "BAYELSA", "BENUE", "BORNO", "CROSS RIVER", "DELTA",
          "EBONYI", "EDO", "EKITI", "ENUGU", "FCT", "GOMBE", "IMO", "JIGAWA", "KADUNA", "KANO", "KATSINA", "KEBBI",
          "KOGI", "KWARA", "LAGOS", "NASARAWA", "NIGER", "OGUN", "ONDO", "OSUN", "OYO", "PLATEAU", "RIVERS",
          "SOKOTO", "TARABA", "YOBE", "ZAMFARA", "UNKNOWN"}

CSVS = [p for p in sorted(glob.glob(str(DATA / "**" / "*.csv"), recursive=True))
        if not re.search(r"/parsed/nerc_caps_20\d\d-\d\d\.csv$", p) and not p.endswith("band_history_wide.csv")]


@pytest.fixture(scope="module")
def caps():
    return pd.read_csv(DATA / "clean" / "caps_long.csv", dtype={"cap_kwh": float})


@pytest.mark.parametrize("path", CSVS, ids=lambda p: str(Path(p).relative_to(DATA)))
def test_columns_documented(path):
    rel = str(Path(path).relative_to(ROOT))
    assert f"`{rel}`" in DICT, f"{rel} has no section in docs/DATA_DICTIONARY.md"
    for c in pd.read_csv(path, nrows=1).columns:
        assert f"| {c} |" in DICT, f"{rel}: column {c} not documented"


def test_main_table_values(caps):
    banded = caps["band_source"] != "not_published"
    assert set(caps.loc[banded, "band"]) <= set("ABCDE")
    assert caps.loc[~banded, "band"].isna().all()  # a state regulator printed no band and NERC never listed it
    assert (caps["cap_kwh"] > 0).all()
    assert set(caps["state"]) <= STATES
    assert caps["order_month"].str.fullmatch(r"20\d\d-(0[1-9]|1[0-2])").all()


def test_one_row_per_feeder_month(caps):
    assert not caps.duplicated(["feeder_id", "order_month"]).any()


def test_consumption_month_is_previous_month(caps):
    o = pd.PeriodIndex(caps["order_month"], freq="M")
    c = pd.PeriodIndex(caps["consumption_month"], freq="M")
    assert ((o - c).map(lambda d: d.n) == 1).all()


def test_every_source_pdf_is_committed():
    s = pd.read_csv(DATA / "parsed" / "sources.csv")
    missing = [f for f in s["file"] if not (ROOT / "raw" / "pdfs" / f).exists()]
    assert not missing, missing[:5]


def test_findings_match_tables(caps):
    """Findings are NERC-only; state regulator rows only add to the clean tables."""
    f = json.loads((DATA / "findings.json").read_text())
    nerc = caps[caps["regulator"] == "NERC"]
    assert f["distinct_feeders"] == nerc["feeder_id"].nunique()
    assert f["latest_month"] == nerc["order_month"].max()


def test_unreadable_bands_stay_rare():
    """Scanned orders: a band the OCR could not read is written as '?'. A jump means the reader regressed."""
    parsed = pd.read_csv(DATA / "parsed" / "nerc_caps_all.csv", usecols=["service_band", "extraction_method"])
    ocr = parsed[parsed.extraction_method == "ocr"]
    assert (ocr.service_band == "?").mean() < 0.005, (ocr.service_band == "?").sum()


def test_recovered_band_letters():
    """Rows the first OCR pass could not read, checked by eye against the scans."""
    p = pd.read_csv(DATA / "parsed" / "nerc_caps_all.csv", usecols=["disco", "year", "month", "feeder_raw", "service_band", "cap_kwh"])
    def band(disco, y, m, feeder, cap):
        r = p[(p.disco == disco) & (p.year == y) & (p.month == m) & p.feeder_raw.str.contains(feeder, regex=False) & (p.cap_kwh == cap)]
        assert len(r) == 1, (feeder, len(r))
        return r.service_band.iloc[0]
    assert band("YEDC", 2026, 7, "GRA MUBI", 179) == "C"
    assert band("JEDC", 2026, 1, "MAKURDI TOWN", 127) == "B"
    assert band("IKEDC", 2026, 2, "Shangisha", 1189) == "A"   # "A - Bilateral"


def test_few_one_month_feeders(caps):
    """Rows glued together or split apart by the parser show up as fake feeders listed in one month only.
    In text months this was 20.5 percent before wrapped names were attached to the right row; now about 15."""
    text = caps[caps.extraction_method == "text"]
    months = text.groupby("feeder_id").order_month.nunique()
    assert (months == 1).mean() < 0.17, round((months == 1).mean(), 3)


def test_business_units_are_not_feeder_fragments():
    """A business unit holding feeder text ('...INJ-', 'FEEDER', a kV tag) means cells shifted."""
    p = pd.read_csv(DATA / "parsed" / "nerc_caps_all.csv", usecols=["business_unit", "extraction_method"], dtype=str).fillna("")
    text = p[p.extraction_method == "text"]
    bad = text.business_unit.str.upper().str.contains(r"INJ-|FEEDER|\bFDR|\b(?:11|33)\s*KV|BILATERAL", regex=True)
    assert bad.mean() < 0.001, text.business_unit[bad].value_counts().head(10).to_dict()
