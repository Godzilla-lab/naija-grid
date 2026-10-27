#!/usr/bin/env python3
"""
Monthly energy caps published by STATE electricity regulators, for states that left NERC's orders.

Only two state regulators publish caps (checked 2026-10-26, see docs/STATE_REGULATORS.md):
  LASERC (Lagos)  laserc.com.ng: one PDF per successor DisCo, same layout as NERC's (state, BU, feeder, band, cap)
  EERC (Enugu)    eerc.en.gov.ng: one PDF a month for MainPower, district + feeder + cap, no band column

Rows keep the original DisCo code (IKEDC, EKEDC, EEDC) so a feeder links to its NERC history; the
`regulator` column says who set the cap. Enugu has no band in its files: the band is carried from the
feeder's last NERC order and flagged in `band_source`, and those rows are left out of band statistics.

Writes data/parsed/state_caps_all.csv and data/parsed/state_sources.csv.
Run: python scripts/state_caps.py [--no-download]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import nerc_caps as n  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "state"
OUT = ROOT / "data" / "parsed"

LASERC_API = "https://larsec-bk-epeak.ondigitalocean.app/api/content/energy-caps"
EERC_LIST = "https://eerc.en.gov.ng/estimated-billing-caps"

# Successor companies in Lagos, mapped back to the DisCo code their feeders carry in NERC's orders.
LAGOS_ENTITY = [
    (r"(?<![A-Z])(IE|IEEL|IKEJA|IKEDC)(?![A-Z])", "IKEDC"),
    (r"(?<![A-Z])(EKEDP|EKEDC|EKO|EXCEL|EEDL|LEDL)(?![A-Z])", "EKEDC"),
]
MONTH_RE = re.compile(r"(january|february|march|april|may|june|july|august|september|october|november|december)\W*(20\d\d)", re.I)


def _month(text: str) -> tuple[int, int] | None:
    m = MONTH_RE.search(text)
    if not m:
        return None
    return int(m.group(2)), n.MONTHS.index(m.group(1).lower()) + 1


def _fetch(url: str) -> bytes | None:
    try:
        return n.http_get(url)
    except Exception as e:  # noqa: BLE001
        n.log(f"unavailable: {url} ({e})")
        return None


def download_laserc() -> list[dict]:
    """Every listed LASERC cap file; older files on its storage now return 403 and are logged as unavailable."""
    listed = []
    body = _fetch(LASERC_API)
    if not body:
        return listed
    for it in json.loads(body):
        title = it.get("title", "")
        url = it.get("pdfUrl") or it.get("externalUrl") or ""
        mm = _month(title)
        disco = next((d for pat, d in LAGOS_ENTITY if re.search(pat, title.upper())), None)
        if not (url and mm and disco):
            n.log(f"LASERC skipped (no month, DisCo or link): {title}")
            continue
        dest = RAW / "laserc" / f"LASERC_{disco}_{mm[0]}-{mm[1]:02d}.pdf"
        status = "have"
        if not dest.exists():
            data = _fetch(url.replace(" ", "%20"))
            if data and n.pdf_complete(data):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                status = "downloaded"
            else:
                status = "unavailable"
        listed.append({"regulator": "LASERC", "order_month": f"{mm[0]}-{mm[1]:02d}", "disco": disco,
                       "title": title, "url": url, "status": status})
    return listed


def download_eerc() -> list[dict]:
    listed = []
    page = _fetch(EERC_LIST)
    if not page:
        return listed
    links = sorted(set(re.findall(r'href="(https://eerc\.en\.gov\.ng/estimated-billing-caps/[^"]+)"', page.decode("utf-8", "ignore"))))
    for link in links:
        mm = _month(link.rsplit("/", 1)[-1].replace("-", " "))
        if not mm:
            continue
        dest = RAW / "eerc" / f"EERC_EEDC_{mm[0]}-{mm[1]:02d}.pdf"
        status, url = "have", link
        if not dest.exists():
            detail = _fetch(link)
            pdf = re.search(r'href="([^"]*/storage/estimated-billing-caps/documents/[^"]+\.pdf)"',
                            (detail or b"").decode("utf-8", "ignore"))
            status = "unavailable"
            if pdf:
                url = pdf.group(1) if pdf.group(1).startswith("http") else "https://eerc.en.gov.ng" + pdf.group(1)
                data = _fetch(url)
                if data and n.pdf_complete(data):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    status = "downloaded"
        listed.append({"regulator": "EERC", "order_month": f"{mm[0]}-{mm[1]:02d}", "disco": "EEDC",
                       "title": link.rsplit("/", 1)[-1], "url": url, "status": status})
    return listed


def _squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _nerc_eedc() -> dict[str, tuple[str, str, str]]:
    """Enugu feeders as NERC last printed them: squashed name -> (printed name, band, order month)."""
    out: dict[str, tuple[str, str, str]] = {}
    src = OUT / "nerc_caps_all.csv"
    with src.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["disco"] != "EEDC" or r["service_band"] not in "ABCDE" or not r["service_band"]:
                continue
            key = _squash(r["feeder_raw"])
            month = f"{int(r['year']):04d}-{int(r['month']):02d}"
            if key not in out or month >= out[key][2]:
                out[key] = (r["feeder_raw"], r["service_band"], month)
    return out


# Misprints in EERC files, checked against the same feeder in EERC's other months.
EERC_TYPOS = {"ORBAOBLLO33KV": "ORBA OBOLLO 33KV"}  # July 2026 file

EERC_ROW = re.compile(r"^\s*(\d{1,3})\s+(\S.*?)\s{2,}(\S.*?)\s{2,}([\d,]+)\s*$")


def parse_eerc(path: Path, year: int, month: int, known: dict, spaced: dict | None = None) -> tuple[list[dict], list[str]]:
    """S/N | DISTRICT | FEEDER | CAP. The July 2026 file has its spaces stripped ('ABAKALIKIROAD11KV');
    such names are restored from EERC's own later files (`spaced`), else from NERC's printed name,
    when the squashed forms match."""
    rows, unparsed = [], []
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    reader = n.pypdf.PdfReader(str(path))
    for pno, page in enumerate(reader.pages, start=1):
        for line in (page.extract_text(extraction_mode="layout") or "").splitlines():
            m = EERC_ROW.match(line)
            if not m:
                if re.match(r"^\s*\d{1,3}\s+[A-Z]", line):
                    unparsed.append(f"{path.name}:p{pno}: {line.strip()}")
                continue
            district, feeder, cap = m.group(2).strip(), m.group(3).strip(), m.group(4)
            feeder = EERC_TYPOS.get(feeder, feeder)
            hit = known.get(_squash(feeder))
            if " " not in feeder:  # restore the spaces the PDF lost
                feeder = (spaced or {}).get(_squash(feeder)) or (hit[0] if hit else feeder)
            band, band_source = (hit[1], f"carried_from_nerc_{hit[2]}") if hit else ("?", "not_published")
            kv = re.search(r"(\d{2})\s*KV", feeder, re.I)
            rows.append({
                "disco": "EEDC", "year": year, "month": month, "state": "ENUGU", "business_unit": district,
                "voltage_kv": kv.group(1) if kv else "", "injection_substation": "", "transformer": "",
                "feeder_name": feeder, "feeder_raw": feeder, "service_band": band,
                "cap_kwh": int(cap.replace(",", "")), "source_file": path.name, "source_page": pno,
                "source_sha16": sha, "bu_inferred": 0, "extraction_method": "text",
                "regulator": "EERC", "band_source": band_source,
            })
    return rows, unparsed


def parse_laserc(path: Path, year: int, month: int, disco: str) -> tuple[list[dict], list[str]]:
    rows, unparsed = n.parse_pdf(path, year, month)
    for r in rows:
        r["disco"] = disco
        r["state"] = r["state"] or "LAGOS"
        r["regulator"] = "LASERC"
        r["band_source"] = "printed"
    return rows, unparsed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()
    listed = [] if args.no_download else download_laserc() + download_eerc()

    known = _nerc_eedc()
    # EERC's own printed names (files whose text keeps its spaces), newest last so it wins
    spaced: dict[str, str] = {}
    for path in sorted((RAW / "eerc").glob("EERC_*.pdf")):
        y, m = map(int, path.stem.split("_")[2].split("-"))
        for r in parse_eerc(path, y, m, known)[0]:
            if " " in r["feeder_raw"]:
                spaced[_squash(r["feeder_raw"])] = r["feeder_raw"]
    rows, sources, qa = [], [], []
    for path in sorted((RAW / "laserc").glob("LASERC_*.pdf")) + sorted((RAW / "eerc").glob("EERC_*.pdf")):
        reg, disco, ym = path.stem.split("_")
        y, m = map(int, ym.split("-"))
        got, unparsed = (parse_laserc(path, y, m, disco) if reg == "LASERC" else parse_eerc(path, y, m, known, spaced))
        rows += got
        qa += unparsed
        sources.append({"regulator": reg, "order_month": ym, "disco": disco, "file": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(got),
                        "unparsed_lines": len(unparsed)})
        n.log(f"{reg:6} {disco:6} {ym} {len(got):4} rows {len(unparsed)} unparsed")

    cols = list(rows[0].keys()) if rows else []
    with (OUT / "state_caps_all.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with (OUT / "state_sources.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["regulator", "order_month", "disco", "file", "sha256", "rows", "unparsed_lines"])
        w.writeheader()
        w.writerows(sources)
    if listed:
        with (OUT / "state_listed.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["regulator", "order_month", "disco", "status", "title", "url"])
            w.writeheader()
            w.writerows(sorted(listed, key=lambda r: (r["regulator"], r["order_month"], r["disco"])))
    (OUT / "state_qa.log").write_text("\n".join(qa) + "\n", encoding="utf-8")
    n.log(f"done: {len(sources)} files, {len(rows)} rows, {len(qa)} unparsed lines")


if __name__ == "__main__":
    main()
