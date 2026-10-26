#!/usr/bin/env python3
"""Health check after a refresh. Prints a Markdown report of anything that needs a human look
(empty output means all clear). The workflow opens a GitHub issue when the report is not empty.

Checks, for the newest order month against the one before:
  - downloads that failed, or months NERC listed nothing for (from data/last_checked.json)
  - any order file that produced 0 rows (layout change or unreadable scan)
  - a DisCo whose feeder count fell by more than 40 percent, or that disappeared
  - more than 10 percent of a month's bands unreadable ('?'), or unparsed lines
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
issues = []

hb_path = ROOT / "data" / "last_checked.json"
if hb_path.exists():
    hb = json.loads(hb_path.read_text())
    if hb.get("failed_downloads"):
        issues.append("Downloads failed:\n" + "\n".join(f"- {u}" for u in hb["failed_downloads"]))

src = pd.read_csv(ROOT / "data" / "parsed" / "sources.csv")
months = sorted(src["order_month"].unique())
latest, prev = months[-1], (months[-2] if len(months) > 1 else None)
cur = src[src["order_month"] == latest]

zero = cur[cur["rows"] == 0]
for r in zero.itertuples():
    issues.append(f"`{r.file}` ({r.disco}, {latest}) produced 0 rows. Extraction: {r.extraction}, {r.pages} pages. "
                  "Likely a new table layout or an unreadable scan.")

if prev:
    a = src[src["order_month"] == prev].groupby("disco")["rows"].sum()
    b = cur.groupby("disco")["rows"].sum()
    for d, n_prev in a.items():
        n_cur = int(b.get(d, 0))
        if n_cur == 0:
            issues.append(f"{d} had {n_prev} feeders in {prev} and none in {latest}. "
                          "Either NERC stopped listing it (a state handover) or its order was missed.")
        elif n_cur < 0.6 * n_prev:
            issues.append(f"{d} fell from {n_prev} feeders in {prev} to {n_cur} in {latest} (more than 40 percent).")

parsed = ROOT / "data" / "parsed" / f"nerc_caps_{latest}.csv"
if parsed.exists():
    p = pd.read_csv(parsed, dtype=str)
    if len(p):
        q = (p["service_band"] == "?").mean()
        if q > 0.10:
            issues.append(f"{q:.0%} of bands in {latest} could not be read.")
unp = cur["unparsed_lines"].sum()
if unp > 10:
    issues.append(f"{unp} unparsed lines in {latest}; see data/parsed/reparse_qa.log.")

if issues:
    print(f"## naija-grid refresh needs a look ({latest})\n")
    print("\n\n".join(issues))
    print("\nThe data was still committed. Check the source PDFs in raw/pdfs and the log of this run.")
sys.exit(0)
