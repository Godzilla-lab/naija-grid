"""Checks on the published CSVs."""
import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICT = (ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")

# Columns the brief requires. Extra columns are allowed if they are documented.
REQUIRED = {
    "main": {"disco", "year", "month", "state", "business_unit", "feeder_name", "feeder_raw",
             "feeder_key", "service_band", "cap_kwh", "source_file"},
    "sources.csv": {"disco", "year", "month", "url", "filename", "sha256", "pages", "bytes",
                    "feeders_parsed", "extraction_method"},
    "derived/band_counts_by_disco_month.csv": {"disco"},
    "derived/band_changes.csv": {"disco", "feeder_key", "from_band", "to_band"},
    "derived/feeder_first_last_seen.csv": {"disco", "feeder_key"},
}
ALL_CSVS = sorted(p.relative_to(DATA).as_posix() for p in DATA.rglob("*.csv"))
MAIN_RE = re.compile(r"nerc_caps_(all|\d{4}-\d{2})\.csv$")


def header(rel):
    with (DATA / rel).open(encoding="utf-8") as f:
        return next(csv.reader(f))


def main_rows():
    with (DATA / "nerc_caps_all.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("rel", ALL_CSVS)
def test_required_columns(rel):
    need = REQUIRED["main"] if MAIN_RE.match(rel) else REQUIRED.get(rel, set())
    missing = need - set(header(rel))
    assert not missing, f"{rel} lacks {sorted(missing)}"


@pytest.mark.parametrize("rel", ALL_CSVS)
def test_columns_documented(rel):
    for col in header(rel):
        assert f"`{col}`" in DICT, f"{rel}: column {col} is not in docs/DATA_DICTIONARY.md"


def test_monthly_files_share_one_header():
    heads = {tuple(header(r)) for r in ALL_CSVS if MAIN_RE.match(r)}
    assert len(heads) == 1


def test_bands_and_caps():
    rows = main_rows()
    assert rows
    for r in rows:
        assert r["service_band"] in {"A", "B", "C", "D", "E"}, r
        assert r["cap_kwh"].isdigit() and int(r["cap_kwh"]) > 0, r


def test_months_are_valid():
    for r in main_rows():
        assert 2022 <= int(r["year"]) <= 2100 and 1 <= int(r["month"]) <= 12, r


def test_monthly_files_add_up():
    total = 0
    for p in DATA.glob("nerc_caps_????-??.csv"):
        with p.open(encoding="utf-8") as f:
            total += sum(1 for _ in f) - 1
    assert total == len(main_rows())


def test_sources_on_disk():
    with (DATA / "sources.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status", "used") == "used" and int(r.get("feeders_parsed") or 0):
                assert (ROOT / "raw" / "pdfs" / r["filename"]).exists(), r["filename"]
