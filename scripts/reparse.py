#!/usr/bin/env python3
"""
Re-parse every NERC cap PDF already on disk with the current parser (layout text + OCR fallback).

Month and year come from the file name; NERC names always carry both, in one of these styles:
  IE-Monthly-Energy-Cap-September-2026.pdf, EEDC-monthly-energy-caps-Aug-2026.pdf,
  Eko-Electricity-Distribution-Plc.-Monthly-Energy-CapSeptember-2025.pdf,
  AbujaElectricityDistributionPlcMonthlyEnergyCapJanuary2024.pdf, Abuja-December-2022-Cap.pdf

Writes output/grid/nerc_caps_YYYY-MM.csv per month, nerc_caps_all.csv, sources.csv and a QA log.
Run: python scripts/reparse.py [--only 2025-12]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import nerc_caps as n  # noqa: E402

MONTH_RE = re.compile(r"(?i)(january|february|march|april|may|june|july|august|september|october|november|december|"
                      r"jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)")


def month_of(name: str) -> tuple[int, int] | None:
    low = name.lower()
    y = re.findall(r"(20\d{2})", low)
    if not y:
        return None
    # prefer full names; fall back to abbreviations bounded by non-letters
    for i, full in enumerate(n.MONTHS):
        if full in low:
            return int(y[-1]), i + 1
    m = re.search(r"(?<![a-z])(jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)(?![a-z])", low)
    if m:
        return int(y[-1]), n.MONTH_ABBR[m.group(1)[:3]]
    m = MONTH_RE.search(low)
    if m:
        return int(y[-1]), n.MONTH_ABBR[m.group(1)[:3].lower()]
    return None


def month_from_title(path: Path) -> tuple[int, int] | None:
    """Read the order's own month from its title on page 1, e.g.
    'Monthly Energy Cap (September 2026); Energy Consumed in August 2026' or 'Monthly Energy Cap- for October 2022'.
    Only text PDFs; scanned ones return None and fall back to the file name."""
    try:
        t = (n.pypdf.PdfReader(str(path)).pages[0].extract_text() or "")
    except Exception:  # noqa: BLE001
        return None
    t = " ".join(t.split())
    m = re.search(r"Monthly Energy Caps?[^A-Za-z0-9]{0,6}(?:for\s+)?\(?\s*([A-Za-z]+)[ ,.-]*(20\d{2})", t, re.I)
    if not m:
        return None
    word = m.group(1).lower()
    for i, full in enumerate(n.MONTHS):
        if word == full or word[:3] == full[:3]:
            return int(m.group(2)), i + 1
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="YYYY-MM")
    args = ap.parse_args()

    by_month: dict[str, list[Path]] = defaultdict(list)
    qa_moves: list[str] = []
    skipped = []
    conflicts = []
    for p in sorted(n.PDF_DIR.glob("*.pdf")):
        mm_name = month_of(p.name)
        mm_title = month_from_title(p)
        mm = mm_title or mm_name
        if not mm:
            skipped.append(p.name)
            continue
        if mm_name and mm_title and mm_name != mm_title:
            conflicts.append((p, mm_name, mm_title))
            continue
        key = f"{mm[0]:04d}-{mm[1]:02d}"
        if args.only and key != args.only:
            continue
        by_month[key].append(p)

    # File name and title disagree (NERC has done both: a stale title, and a wrong file name).
    # Put the order in whichever of the two months has no other order from the same DisCo.
    for p, mm_name, mm_title in conflicts:
        d = n.disco_from_filename(p.name)
        k_name, k_title = (f"{a:04d}-{b:02d}" for a, b in (mm_name, mm_title))
        has = lambda k: any(n.disco_from_filename(x.name) == d for x in by_month.get(k, []))
        if has(k_title) and not has(k_name):
            key, why = k_name, f"title says {k_title} but that month already has a {d} order"
        elif has(k_name) and not has(k_title):
            key, why = k_title, f"file name says {k_name} but that month already has a {d} order"
        else:
            key, why = k_title, "ambiguous; using the title"
        qa_moves.append(f"{p.name}: placed in {key} ({why})")
        if not args.only or key == args.only:
            by_month[key].append(p)

    sources = []
    qa = list(qa_moves)
    for key in sorted(by_month):
        y, m = map(int, key.split("-"))
        rows_all = []
        # Keep every file for the month except true reposts: the same bytes, or a text PDF whose
        # extracted text is identical to one already kept. (An order posted as several page images
        # is several files for one DisCo, and all of them must be kept.)
        kept: list[tuple[str, Path]] = []
        seen_hash: set[str] = set()
        seen_text: set[str] = set()
        for p in by_month[key]:
            d = n.disco_from_filename(p.name)
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            try:
                txt = "".join((pg.extract_text() or "") for pg in n.pypdf.PdfReader(str(p)).pages)
            except Exception:  # noqa: BLE001
                txt = ""
            tkey = hashlib.sha256(txt.encode()).hexdigest() if len(txt.strip()) > 200 else None
            if h in seen_hash or (tkey and tkey in seen_text):
                qa.append(f"{key} repost skipped for {d}: {p.name}")
                continue
            seen_hash.add(h)
            if tkey:
                seen_text.add(tkey)
            kept.append((d, p))
        for d, p in sorted(kept, key=lambda t: (t[0], t[1].name)):
            t0 = time.time()
            try:
                rows, unparsed = n.parse_pdf(p, y, m)
            except Exception as e:  # noqa: BLE001
                qa.append(f"{key} {p.name} FAILED {e!r}")
                continue
            meth = sorted({r.get("extraction_method", "text") for r in rows}) or ["none"]
            sources.append({
                "order_month": key, "disco": d, "file": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size, "pages": len(n.pypdf.PdfReader(str(p)).pages),
                "rows": len(rows), "unparsed_lines": len(unparsed), "extraction": "+".join(meth),
            })
            for u in unparsed:
                qa.append(f"{key} unparsed {u}")
            rows_all.extend(rows)
            n.log(f"{key} {d:6} {len(rows):5} rows  {'+'.join(meth):9} {len(unparsed)} unparsed  {time.time()-t0:4.1f}s  {p.name}")
        n.write_csv(n.OUT_DIR / f"nerc_caps_{key}.csv", rows_all)

    if not args.only:
        # remove month files for months with no PDFs (left over from earlier runs)
        for f in n.OUT_DIR.glob("nerc_caps_????-??.csv"):
            k = f.stem.split("_")[-1]
            if k not in by_month:
                f.unlink()
        n.rebuild_all()
    src_path = n.OUT_DIR / "sources.csv"
    if args.only and src_path.exists():
        with src_path.open(encoding="utf-8") as fh:
            keep = [r for r in csv.DictReader(fh) if r.get("order_month") != args.only]
        sources = keep + sources
        sources.sort(key=lambda r: (r["order_month"], r["disco"]))
    with src_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sources[0].keys()) if sources else ["order_month"])
        w.writeheader()
        w.writerows(sources)
    (n.OUT_DIR / (f"reparse_qa_{args.only}.log" if args.only else "reparse_qa.log")).write_text("\n".join(qa + [f"no month in name: {s}" for s in skipped]) + "\n")
    n.log(f"done: {len(sources)} files, {sum(int(s['rows']) for s in sources)} rows, {len(skipped)} names without a month")


if __name__ == "__main__":
    main()
