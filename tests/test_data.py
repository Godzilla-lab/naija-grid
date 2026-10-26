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
    assert set(caps["band"]) <= set("ABCDE")
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
    f = json.loads((DATA / "findings.json").read_text())
    assert f["distinct_feeders"] == caps["feeder_id"].nunique()
    assert f["latest_month"] == caps["order_month"].max()
