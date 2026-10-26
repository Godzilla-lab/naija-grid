#!/usr/bin/env python3
"""
Build the Kaggle mirror of the dataset in build/kaggle/ (the folder `kaggle datasets version -p` uploads).

Kaggle gets the analysis-ready tables only: clean, summary, rankings, reference and findings.
The source PDFs, OCR text and raw extraction stay on GitHub, which the description links to.
Run: python scripts/kaggle_package.py [--owner godzilla1215]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "kaggle"
INCLUDE = ["data/clean", "data/summary", "data/rankings", "data/reference", "data/findings.json", "docs/DATA_DICTIONARY.md"]

DESCRIPTION = """Every NERC Monthly Energy Cap order published online, October 2022 to {last}, as clean tables.

For each Nigerian electricity feeder with unmetered customers, NERC (the Nigerian Electricity Regulatory Commission) publishes a monthly order with the feeder's **service band** (A to E; Band A promises at least 20 hours of supply a day) and its **energy cap**: the most kWh a DisCo may bill an unmetered customer on that feeder for the month. This dataset extracts all of those orders ({pdfs} PDFs, the scanned ones read with OCR), links every feeder across months and adds analysis tables.

| | |
|---|---|
| Feeder-month records | {records:,} |
| Distinct feeders | {feeders:,} |
| Months | {months} |
| DisCos | all 11, plus Aba Power |

**Main table:** `clean/caps_long.csv` (or `.parquet`), one row per feeder per month.

Other files: `clean/feeders.csv` (one row per feeder), `clean/band_history_wide.csv` (feeders down, months across), `summary/` (band mix and caps by DisCo and state per month, every band change), `rankings/` (latest month, highest to lowest), `reference/state_regulators.csv` (the 17 states that have taken over electricity regulation), `findings.json` (every number in the analysis). Column definitions are in `DATA_DICTIONARY.md`.

The order for month M caps energy consumed in month M minus 1; both are columns.

**Source, method, analysis and updates:** https://github.com/Godzilla-lab/naija-grid. The GitHub repository holds the original PDFs, the OCR text, the code and a full analysis, refreshes itself monthly and pushes each new month here.

**Limitations.** Scanned months (November 2025 to August 2026) are less certain than text months. A cap is a legal maximum, not an actual bill. NERC has not put January to September 2022 or September to December 2023 online.

Source documents: NERC (nerc.gov.ng). Data licence: CC BY 4.0. Cite as: Busari, O. (2026). naija-grid. https://github.com/Godzilla-lab/naija-grid"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="godzilla1215")
    args = ap.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for rel in INCLUDE:
        src = ROOT / rel
        dst = OUT / Path(rel).relative_to("data") if rel.startswith("data/") else OUT / Path(rel).name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    f = json.loads((ROOT / "data" / "findings.json").read_text())
    import calendar
    y, m = map(int, f["latest_month"].split("-"))
    meta = {
        "id": f"{args.owner}/naija-grid",
        "title": "Nigeria Electricity Feeder Bands and Caps",
        "subtitle": "NERC service bands and billing caps for every Nigerian feeder, 2022 to date",
        "description": DESCRIPTION.format(
            last=f"{calendar.month_name[m]} {y}", pdfs=f["pdf_files"], records=f["rows"],
            feeders=f["distinct_feeders"], months=f["months_covered"]),
        "licenses": [{"name": "CC-BY-4.0"}],
        "keywords": ["energy", "africa", "government", "electricity", "tabular"],
    }
    (OUT / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"built {OUT} ({sum(1 for _ in OUT.rglob('*') if _.is_file())} files)")


if __name__ == "__main__":
    main()
