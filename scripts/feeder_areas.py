#!/usr/bin/env python3
"""
Feeder to area: where each feeder is and the main streets it serves, from the regulators' own tariff orders.

Every monthly supplementary tariff order has a "Service Level Commitment" appendix listing each feeder with
its band, location, the major streets it serves and its minimum hours of supply:
  LASERC (Lagos, IE Energy Lagos and Excel):  text PDFs; the table is read from its drawn ruling lines.
  NERC (the other DisCos and Ogun):           scanned; the appendix pages were read with Apple Vision OCR
                                               (scripts/ocr_vision.page_lines) and committed in raw/area_text/.

Each listed feeder is matched to a feeder_id in data/clean/feeders.csv of the same DisCo: first by exact
name (letters and digits only), then by close match (similarity 0.88 or more, flagged). Unmatched rows are
kept with a blank feeder_id so nothing published by the regulator is lost.

Writes data/reference/feeder_areas.csv. Run: python scripts/feeder_areas.py [--download]
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import nerc_caps as n  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LASERC_DIR = ROOT / "raw" / "state" / "laserc_orders"
AREA_TEXT = ROOT / "raw" / "area_text"
OUT = ROOT / "data" / "reference" / "feeder_areas.csv"
LASERC_ORDERS = "https://larsec-bk-epeak.ondigitalocean.app/api/content/order/documents"
LAGOS_ENTITY = [(r"(?<![A-Z])(IE|IEEL|IKEJA)(?![A-Z])", "IKEDC"), (r"(?<![A-Z])(EKO|EKEDP|EXCEL|EEDL|EPL)(?![A-Z])", "EKEDC")]
NERC_FILE_DISCO = {"AEDC": "AEDC", "BEDC": "BEDC", "EEDC": "EEDC", "EKEDP": "EKEDC", "IBEDC": "IBEDC", "IE": "IKEDC",
                   "JED": "JEDC", "KAEDC": "KAEDC", "KEDCO": "KEDCO", "PHED": "PHED", "YEDC": "YEDC"}
FIELDS = ["feeder_id", "regulator", "disco", "source_feeder_name", "band_in_source", "location", "streets",
          "min_hours", "match", "match_score", "source_file", "source_month"]


# ---------- Lagos (text PDFs) ----------

def _merge(vals: list[float], tol: float = 2.0) -> list[float]:
    out: list[float] = []
    for v in sorted(vals):
        if out and v - out[-1] < tol:
            out[-1] = (out[-1] + v) / 2
        else:
            out.append(v)
    return out


def ruled_rows(page) -> list[list[str]]:
    """Cells of a ruled table on a text page, delimited by the drawn lines. Cell text is often vertically
    centred, so a long name starts above its row number; ruling lines, not text lines, decide the row."""
    hs, vs = [], []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 1 and abs(a.x - b.x) > 40:
                    hs.append(a.y)
                if abs(a.x - b.x) < 1 and abs(a.y - b.y) > 8:
                    vs.append(a.x)
            elif it[0] == "re":
                r = it[1]
                if r.height < 2 and r.width > 40:
                    hs.append(r.y0)
                if r.width < 2 and r.height > 8:
                    vs.append(r.x0)
                if r.height >= 2 and r.width >= 2:
                    hs += [r.y0, r.y1]
                    vs += [r.x0, r.x1]
    hs, vs = _merge(hs), _merge(vs)
    if len(hs) < 3 or len(vs) < 3:
        return []
    words = page.get_text("words")
    rows = []
    for y0, y1 in zip(hs, hs[1:]):
        if y1 - y0 < 4:
            continue
        cells: list[list] = [[] for _ in range(len(vs) - 1)]
        for w in words:
            cy, cx = (w[1] + w[3]) / 2, (w[0] + w[2]) / 2
            if y0 <= cy < y1:
                for i, (x0, x1) in enumerate(zip(vs, vs[1:])):
                    if x0 <= cx < x1:
                        cells[i].append(w)
                        break
        txt = [" ".join(w[4] for w in sorted(c, key=lambda w: (round(w[1] / 3), w[0]))) for c in cells]
        txt = [t for t in txt if t]
        if txt:
            rows.append(txt)
    return rows


def laserc_rows(path: Path, disco: str, month: str) -> list[dict]:
    """Service-level appendix rows: S/N | feeder | band | location | streets | minimum hours (6 cells).
    The compensation appendix has 8 cells and is skipped."""
    import pymupdf as fitz
    out, on = [], False
    for page in fitz.open(path):
        text = page.get_text().upper()
        if "SERVICE LEVEL COMMITMENT" in text:
            on = True  # the heading is on the appendix's first page only
        elif on and re.search(r"APPENDIX\s*[-:\u2013]?\s*\d", text):
            on = False
        if not on:
            continue
        for r in ruled_rows(page):
            if len(r) == 6 and r[0].isdigit() and r[2] in ("A", "B", "C", "D", "E") and r[5].isdigit():
                out.append({"regulator": "LASERC", "disco": disco, "source_feeder_name": r[1], "band_in_source": r[2],
                            "location": r[3], "streets": r[4], "min_hours": r[5], "source_file": path.name,
                            "source_month": month})
    return out


def download_laserc() -> None:
    """Keep the latest LASERC order per Lagos company (text PDFs, a few MB)."""
    items = json.loads(n.http_get(LASERC_ORDERS))
    latest: dict[str, tuple[str, str, str]] = {}
    for it in items:
        title = (it.get("title") or "").upper()
        mm = re.search(r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\W+(20\d\d)", title)
        disco = next((d for pat, d in LAGOS_ENTITY if re.search(pat, title)), None)
        url = it.get("pdfUrl") or ""
        if not (mm and disco and url and "TARIFF" in title):
            continue
        ym = f"{mm.group(2)}-{n.MONTHS.index(mm.group(1).lower()) + 1:02d}"
        if disco not in latest or ym > latest[disco][0]:
            latest[disco] = (ym, url, title)
    LASERC_DIR.mkdir(parents=True, exist_ok=True)
    for disco, (ym, url, _title) in latest.items():
        dest = LASERC_DIR / f"LASERC_TARIFF_{disco}_{ym}.pdf"
        if not (dest.exists() and n.pdf_complete(dest.read_bytes())):
            dest.write_bytes(n.get_pdf(url))


# ---------- NERC (OCR text of scanned appendices) ----------

def nerc_rows(path: Path, disco: str, month: str) -> list[dict]:
    """Rows from OCR text of a NERC order's service-level appendix. OCR joins cells with four spaces but
    sometimes drops the row number or repeats the band letter, so everything after the feeder name is
    kept as location and streets."""
    out, on = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        up = line.upper()
        if "SERVICE LEVEL COMMITMENT" in up:
            on = True
            continue
        if on and re.match(r"^APPENDIX\s*\d", up) and "SERVICE LEVEL" not in up:
            on = False
        if not on or "FEEDER NAME" in up or line.startswith("====="):
            continue
        s = re.sub(r"^\s*\d{1,3}\s+", "", line).strip()
        cells = [c.strip() for c in re.split(r"\s{2,}", s) if c.strip()]
        if len(cells) < 2:
            continue
        hours = cells.pop() if re.fullmatch(r"\d{1,2}", cells[-1]) else ""
        bands = [c for c in cells if re.fullmatch(r"[A-E]", c)]
        cells = [c for c in cells if not re.fullmatch(r"[A-E]", c)]
        if not cells or not re.search(r"[A-Za-z]{2}", cells[0]):
            continue
        rest = cells[1:]
        out.append({"regulator": "NERC", "disco": disco, "source_feeder_name": cells[0],
                    "band_in_source": bands[-1] if bands else "",
                    "location": rest[0] if len(rest) >= 2 else "", "streets": " ".join(rest[1:]) if len(rest) >= 2 else " ".join(rest),
                    "min_hours": hours, "source_file": re.sub(r"^[A-Z]+_\d{4}-\d{2}_", "", path.name).replace("_ocr.txt", ".pdf"),
                    "source_month": month})
    return out


# ---------- matching ----------

def squash(s: str, keep_kv: bool = False) -> str:
    s = n.fix_ocr_name(s.upper()) if s else ""
    s = re.sub(r"\bFEEDER\b|\bFDR\b", " ", s)
    s = re.sub(r"\b(11|33)\s*K\s*V\b", (lambda m: f" {m.group(1)}KV ") if keep_kv else " ", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def kv_of(s: str) -> str:
    m = re.search(r"\b(11|33)\s*K\s*V\b", s.upper())
    return m.group(1) if m else ""


def code_tail(s: str) -> str:
    """Abuja feeder code: last three parts, e.g. 'APO AT3_H37_S26_K10' and
    '132KV APO TS_33KV FDR H37_S26_K10' both give 'H37 S26 K10'."""
    parts = [p for p in re.split(r"[_\s]+", n.fix_ocr_name(s.upper()).strip()) if p]
    return " ".join(parts[-3:]) if len(parts) >= 3 else ""


MARKERS = re.compile(r"\b(?:\d+|[IVX]{1,4}|[A-Z]|NEW|OLD|NORTH|SOUTH|EAST|WEST|EXPRESS|DEDICATED)\b")


def markers(name: str) -> list[str]:
    """Tokens that tell two similarly named feeders apart: numbers (kV, transformer, 1/2), roman numerals,
    single letters (LEOPARD B), and words such as NEW. Close matches must agree on all of them."""
    up = re.sub(r"(\d)", r" \1 ", re.sub(r"[^A-Z0-9]+", " ", n.fix_ocr_name(name).upper()))
    up = re.sub(r"(?<=\d) (?=\d)", "", up)  # keep multi-digit numbers whole
    return sorted(MARKERS.findall(up))


def eko_tail(name: str) -> str:
    """LASERC prints Eko feeders as 'STATION TS_SOURCE_BUS_FEEDER'; NERC as '11kV-FEEDER'."""
    return squash(name.split("_")[-1]) if "_" in name else ""


def match(rows: list[dict]) -> list[dict]:
    """Exact name; for Eko, the last segment of LASERC's name; else a close match (0.90 or more) that
    agrees on every distinguishing marker. Anything else stays unmatched: a wrong match would send a
    reader to the wrong feeder, an unmatched row is still searchable by its area."""
    with (ROOT / "data" / "clean" / "feeders.csv").open(encoding="utf-8") as fh:
        feeders = list(csv.DictReader(fh))
    by_disco: dict[str, dict[str, list]] = {}
    for f in feeders:
        if f["last_seen"] < "2025-01":
            continue  # match to feeders that are still listed
        names = by_disco.setdefault(f["disco"], {})
        for nm in {f["feeder_raw"], f["feeder_name"]}:
            if nm:
                names.setdefault(squash(nm), []).append((f["feeder_id"], nm))
                names.setdefault("KV|" + squash(nm, keep_kv=True), []).append((f["feeder_id"], nm))
                if f["disco"] == "AEDC" and code_tail(nm):
                    names.setdefault("CODE|" + code_tail(nm), []).append((f["feeder_id"], nm))
    for r in rows:
        names = by_disco.get(r["disco"], {})
        src = r["source_feeder_name"]
        key = squash(src)
        r["feeder_id"], r["match"], r["match_score"] = "", "none", ""
        done = False
        for k in ("KV|" + squash(src, keep_kv=True), key):  # with the voltage first: 11KV AJIYA vs 33KV AJIYA
            hit = names.get(k)
            if hit and k == key and kv_of(src) and kv_of(hit[0][1]) and kv_of(src) != kv_of(hit[0][1]):
                continue  # both name a voltage and they differ: 33KV NUMAN is not 11KV NUMAN
            if hit and len({h[0] for h in hit}) == 1:
                r["feeder_id"], r["match"], r["match_score"] = hit[0][0], "exact", "1.00"
                done = True
                break
        if done:
            continue
        if r["disco"] == "AEDC" and code_tail(src):
            hit = names.get("CODE|" + code_tail(src))
            if hit and len({h[0] for h in hit}) == 1:
                r["feeder_id"], r["match"], r["match_score"] = hit[0][0], "aedc_code", "1.00"
                continue
        if r["disco"] == "EKEDC" and r["regulator"] == "LASERC":
            tail = eko_tail(src)
            cand = names.get(tail) if len(tail) >= 4 else None
            if cand and len({h[0] for h in cand}) == 1:
                r["feeder_id"], r["match"], r["match_score"] = cand[0][0], "eko_tail", "1.00"
                continue
        best, score = None, 0.0
        for k, hs in names.items():
            if "|" in k:
                continue
            s = difflib.SequenceMatcher(None, key, k).ratio()
            if s > score:
                best, score = (k, hs), s
        last_ok = True
        if best and "-" in src and "-" in best[1][0][1]:
            # Ikeja style 'TS-SOURCE-FEEDER': the shared prefix inflates similarity (OPEBI vs OPIC)
            last_ok = difflib.SequenceMatcher(None, squash(src.split("-")[-1]), squash(best[1][0][1].split("-")[-1])).ratio() >= 0.8
        if best and score >= 0.90 and last_ok and len({h[0] for h in best[1]}) == 1 and markers(src) == markers(best[1][0][1]):
            r["feeder_id"], r["match"], r["match_score"] = best[1][0][0], "fuzzy", f"{score:.2f}"
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="fetch the latest LASERC orders first")
    args = ap.parse_args()
    if args.download:
        try:
            download_laserc()
        except Exception as e:  # noqa: BLE001
            n.log(f"LASERC orders not refreshed: {e}")
    rows: list[dict] = []
    for p in sorted(LASERC_DIR.glob("LASERC_TARIFF_*.pdf")):
        _, _, disco, ym = p.stem.split("_")
        rows += laserc_rows(p, disco, ym)
    for p in sorted(AREA_TEXT.glob("*_ocr.txt")):
        code = p.name.split("_")[0]
        mm = re.search(r"_(20\d\d)-(\d\d)_", p.name)
        if code in NERC_FILE_DISCO and mm:
            rows += nerc_rows(p, NERC_FILE_DISCO[code], f"{mm.group(1)}-{mm.group(2)}")
    rows = match(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["disco"], r["regulator"], r["source_feeder_name"])))
    from collections import Counter
    c = Counter((r["regulator"], r["disco"], r["match"]) for r in rows)
    for k in sorted(c):
        n.log(f"{k[0]:6} {k[1]:6} {k[2]:6} {c[k]}")
    n.log(f"done: {len(rows)} rows, {sum(1 for r in rows if r['feeder_id'])} matched to a feeder")


if __name__ == "__main__":
    main()
