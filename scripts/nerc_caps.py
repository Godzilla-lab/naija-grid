#!/usr/bin/env python3
"""
NERC Monthly Energy Cap orders -> one feeder-level table.

NERC publishes one PDF per DisCo each month ("<DisCo> Monthly Energy Cap <Month> <Year>")
in its document library. Each PDF lists every feeder with its service band (A to E) and the
monthly kWh cap for unmetered non-MD customers. This script finds the PDFs for a month,
downloads them, parses the tables and writes CSV + JSONL.

Usage:
  python3 scripts/nerc_caps.py --month 2026-09            # one month, all DisCos
  python3 scripts/nerc_caps.py --from 2024-01 --to 2026-10 # back-fill
  python3 scripts/nerc_caps.py --parse-only .tmp/grid/pdfs/IE-Monthly-Energy-Cap-September-2026.pdf

Outputs:
  .tmp/grid/pdfs/<file>.pdf                 raw downloads (kept, hashed)
  output/grid/nerc_caps_<YYYY-MM>.csv       parsed rows for the month
  output/grid/nerc_caps_all.csv             every month parsed so far, rebuilt
  output/grid/nerc_caps_unparsed.log        lines the parser could not read, for review

No API keys. Only stdlib + pypdf.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import site
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pypdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "raw" / "pdfs"
OUT_DIR = ROOT / "data" / "parsed"
UA = "Mozilla/5.0 (naija-grid; open data; contact via github.com/Godzilla-lab)"

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# Nigerian states, longest first so two-word names match before one-word ones.
STATES = sorted([
    "ABIA", "ADAMAWA", "AKWA IBOM", "ANAMBRA", "BAUCHI", "BAYELSA", "BENUE", "BORNO",
    "CROSS RIVER", "DELTA", "EBONYI", "EDO", "EKITI", "ENUGU", "FCT", "ABUJA", "GOMBE", "IMO",
    "JIGAWA", "KADUNA", "KANO", "KATSINA", "KEBBI", "KOGI", "KWARA", "LAGOS", "NASARAWA",
    "NIGER", "OGUN", "ONDO", "OSUN", "OYO", "PLATEAU", "RIVERS", "SOKOTO", "TARABA", "YOBE",
    "ZAMFARA",
], key=len, reverse=True)

# Known DisCo short names seen in NERC file names, mapped to a canonical code.
DISCO_ALIASES = {
    "AEDC": "AEDC", "ABUJA": "AEDC",
    "BEDC": "BEDC", "BENIN": "BEDC",
    "EEDC": "EEDC", "ENUGU": "EEDC",
    "EKEDP": "EKEDC", "EKEDC": "EKEDC", "EKO": "EKEDC",
    "IBEDC": "IBEDC", "IBADAN": "IBEDC",
    "IE": "IKEDC", "IKEDC": "IKEDC", "IKEJA": "IKEDC",
    "JED": "JEDC", "JEDC": "JEDC", "JOS": "JEDC",
    "KAEDC": "KAEDC", "KAEDCO": "KAEDC", "KADUNA": "KAEDC",
    "KEDCO": "KEDCO", "KANO": "KEDCO",
    "PHED": "PHED", "PHEDC": "PHED", "PORT": "PHED", "PH": "PHED",
    "YEDC": "YEDC", "YOLA": "YEDC",
    "APLE": "APLE", "APL": "APLE", "ABA": "APLE",
}

ROW_RE = re.compile(r"^(?P<location>.+?)\s+(?P<band>[A-E])\s+(?P<cap>\d{1,3}(?:,\d{3})*|\d+)\s*$")
# Lines that are never data rows. Checked only after a line fails the row pattern.
HEADER_RE = re.compile(
    r"^(P\s*a\s*g\s*e\s*\||Page \||NIGERIAN ELECTRICITY|Order No|.*Monthly Energy Cap|.*Energy Consumed in|"
    r"Consumed in|Monthly Energy Caps of|in the Nigerian Electricity|STATE\b.*BUSINESS|BUSINESS UNIT|SERVICE\s*$|"
    r"BAND\s*$|CAP\s*$|\(kWh\)|NON-MD\s*$|FEEDER NAME)", re.I)


def log(msg: str) -> None:
    print(msg, flush=True)


def http_get(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    """GET with retries. NERC's TLS chain is incomplete and Python sometimes rejects it, so after the
    urllib attempts fail we fall back to curl (present on macOS and Linux runners)."""
    import subprocess
    safe = urllib.parse.quote(url, safe=":/?&=%#+,")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(safe, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + attempt * 3)
    for extra in ([], ["-k"]):  # verified first; unverified only if the chain itself is the problem
        try:
            out = subprocess.run(["curl", "-sSL", "--max-time", str(timeout * 2), "--retry", "2", "-A", UA, *extra, safe],
                                 capture_output=True, check=True)
            if out.stdout:
                return out.stdout
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"GET failed {url}: {last}")


MONTH_ABBR = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}
_year_cache: dict[int, list[dict]] = {}


def _library_page(term: str, page: int) -> str:
    base = "https://nerc.gov.ng/resources/" + (f"page/{page}/" if page > 1 else "")
    url = base + "?" + urllib.parse.urlencode({"doc_term": term, "ins": 1})
    return http_get(url).decode("utf-8", "ignore")


def list_year(year: int) -> list[dict]:
    """Every cap document NERC lists for a year: [{title, url, year, month}].

    Reads titles like 'Ikeja Electricity Distribution Plc - Monthly Energy Cap, December 2022'
    or 'IE Monthly Energy Cap September 2026' and the Download link after each one, across all
    result pages. Titles are far more stable than file names, which changed style every year.
    """
    import html as _html
    if year in _year_cache:
        return _year_cache[year]
    docs: list[dict] = []
    seen: set[str] = set()
    for page in range(1, 40):
        try:
            h = _library_page(f"monthly energy cap {year}", page)
        except RuntimeError:
            break
        # Each result: title text ... View ... Download link. Split on download anchors.
        anchors = list(re.finditer(r'href="(https?://nerc\.gov\.ng/wp-content/uploads/[^"]+)"[^>]*>\s*Download', h, re.I))
        if not anchors:
            break
        prev = 0
        for a in anchors:
            seg = h[prev:a.start()]
            prev = a.end()
            text = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", seg)))
            m = re.search(r"([A-Za-z][^.]{2,120}?Energy Caps?[^.]{0,40}?(?:[A-Za-z]{3,9})[ ,.-]*\d{4})", text)
            title = m.group(1).strip() if m else text.strip()[-140:]
            url = _html.unescape(a.group(1))
            if url in seen:
                continue
            seen.add(url)
            low = (title + " " + url.rsplit("/", 1)[-1]).lower()
            mo = None
            for name in MONTHS:
                if name in low:
                    mo = MONTHS.index(name) + 1
                    break
            if mo is None:
                mm = re.search(r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)(?![a-z])", low)
                if mm:
                    mo = MONTH_ABBR[mm.group(1)[:3]]
            yy = re.findall(r"(20\d{2})", title) or re.findall(r"(20\d{2})", url.rsplit("/", 1)[-1])
            docs.append({"title": title, "url": url, "year": int(yy[-1]) if yy else year, "month": mo})
        if f"page/{page + 1}/" not in h:
            break
        time.sleep(1.0)
    _year_cache[year] = docs
    return docs


ACCEPTED = (".pdf", ".jpg", ".jpeg", ".png", ".zip")


def find_month_pdfs(year: int, month: int) -> list[str]:
    """URLs of the cap orders for one month: PDFs, images (JPG, PNG) and ZIP bundles.
    If a month has both a ZIP and the individual files, the ZIP is skipped."""
    docs = [d for d in list_year(year) + (list_year(year + 1) if month == 12 else [])
            if d["year"] == year and d["month"] == month and d["url"].lower().endswith(ACCEPTED)]
    urls = sorted({d["url"] for d in docs})
    singles = [u for u in urls if not u.lower().endswith(".zip")]
    return singles if singles else urls


DISCO_TITLE = [("ABA POWER", "APLE"), ("ABUJA", "AEDC"), ("BENIN", "BEDC"), ("ENUGU", "EEDC"), ("EKO", "EKEDC"),
               ("IBADAN", "IBEDC"), ("IKEJA", "IKEDC"), ("JOS", "JEDC"), ("KADUNA", "KAEDC"), ("KANO", "KEDCO"),
               ("PORT HARCOURT", "PHED"), ("YOLA", "YEDC")]


def disco_from_text(text: str) -> str:
    """DisCo from an order's opening lines, e.g. 'Ikeja Electricity Distribution Plc - Monthly Energy Cap'."""
    up = " ".join(str(text or "").upper().split())
    i = up.find("MONTHLY ENERGY CAP")
    head = up[max(0, i - 120):i] if i > 0 else up[:250]
    for key, code in DISCO_TITLE:
        if re.search(rf"\b{key}\b", head):
            return code
    return ""


def disco_from_filename(name: str) -> str:
    stem = Path(name).stem
    first = re.split(r"[-_ ]", stem)[0].upper()
    if first in DISCO_ALIASES:
        return DISCO_ALIASES[first]
    up = stem.upper()
    for key, code in DISCO_ALIASES.items():
        if up.startswith(key):
            return code
    return first


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", urllib.parse.unquote(name))


def _ensure_month_in_name(name: str, year: int | None, month: int | None) -> str:
    """Converted files must carry the month in their name, because an image has no title text."""
    if not year or not month:
        return name
    low = name.lower()
    if str(year) in low and (MONTHS[month - 1] in low or MONTHS[month - 1][:3] in low):
        return name
    stem, ext = name.rsplit(".", 1)
    return f"{stem}-{MONTHS[month - 1].capitalize()}-{year}.{ext}"


def _image_to_pdf(img_bytes: bytes, dest: Path) -> Path:
    import pymupdf as fitz
    img = fitz.open(stream=img_bytes)
    pdf = fitz.open("pdf", img.convert_to_pdf())
    pdf.save(dest)
    return dest


def download_all(url: str, year: int | None = None, month: int | None = None) -> list[Path]:
    """Download one listed document and return the PDF(s) to parse.

    PDF: saved as is. Image: original kept in raw/images, wrapped in a one-page PDF (scanned, so OCR
    reads it). ZIP: every PDF or image inside is handled the same way, names prefixed by the ZIP."""
    import io
    import zipfile
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe(Path(urllib.parse.urlparse(url).path).name)
    low = name.lower()
    if low.endswith(".pdf"):
        dest = PDF_DIR / name
        if not (dest.exists() and dest.stat().st_size > 1000):
            dest.write_bytes(http_get(url))
        return [dest]
    img_dir = ROOT / "raw" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    data = http_get(url)
    out = []
    if low.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                m = _safe(Path(member).name)
                ml = m.lower()
                if ml.endswith(".pdf"):
                    dest = PDF_DIR / _ensure_month_in_name(f"{m[:-4]}__from-{name[:-4]}.pdf", year, month)
                    dest.write_bytes(z.read(member))
                    out.append(dest)
                elif ml.endswith((".jpg", ".jpeg", ".png")):
                    raw = z.read(member)
                    (img_dir / f"{m.rsplit('.', 1)[0]}__from-{name[:-4]}.{m.rsplit('.', 1)[1]}").write_bytes(raw)
                    pdf_name = _ensure_month_in_name(f"{m.rsplit('.', 1)[0]}__from-{name[:-4]}.pdf", year, month)
                    out.append(_image_to_pdf(raw, PDF_DIR / pdf_name))
        return out
    (img_dir / name).write_bytes(data)  # image
    pdf_name = _ensure_month_in_name(name.rsplit(".", 1)[0] + ".pdf", year, month)
    return [_image_to_pdf(data, PDF_DIR / pdf_name)]


def download(url: str) -> Path:
    """Backward compatible: first file only."""
    return download_all(url)[0]


def split_location(loc: str) -> dict:
    """'OGUN ABULE-EGBA BU 11-Abule IrokoINJ-T1-Abule Iroko' -> state, business unit, feeder parts."""
    out = {"state": "", "business_unit": "", "feeder_raw": loc.strip(),
           "voltage_kv": "", "injection_substation": "", "transformer": "", "feeder_name": ""}
    s = loc.strip()
    up = s.upper()
    for st in STATES:
        if up.startswith(st + " "):
            out["state"] = st
            s = s[len(st):].strip()
            break
    # Business unit usually ends with "BU"; otherwise take up to the first token containing a digit-dash.
    m = re.match(r"^(?P<bu>.+?\bBU)\s+(?P<rest>.+)$", s)
    if m:
        out["business_unit"] = m.group("bu").strip()
        s = m.group("rest").strip()
    else:
        m = re.match(r"^(?P<bu>[A-Z][A-Z .\-/&']+?)\s+(?P<rest>\d{1,2}-.+)$", s)
        if m:
            out["business_unit"] = m.group("bu").strip()
            s = m.group("rest").strip()
    out["feeder_raw"] = s
    # Feeder pattern used by Ikeja: "11-<Injection>INJ-T<n>-<Feeder>"
    m = re.match(r"^(?P<kv>\d{1,2})-(?P<inj>.+?)\s*INJ-?\s*T(?P<tx>\d+)-(?P<feeder>.+)$", s, re.I)
    if m:
        out["voltage_kv"] = m.group("kv")
        out["injection_substation"] = m.group("inj").strip()
        out["transformer"] = "T" + m.group("tx")
        out["feeder_name"] = m.group("feeder").strip()
    else:
        m = re.match(r"^(?P<kv>\d{1,2})\s*(?:KV)?-?\s*(?P<feeder>.+)$", s, re.I)
        if m:
            out["voltage_kv"] = m.group("kv")
            out["feeder_name"] = m.group("feeder").strip()
        else:
            out["feeder_name"] = s
    return out


CELL_SPLIT = re.compile(r"\s{2,}")
TAIL_RE = re.compile(r"^(?P<band>[A-E?])$")
WRAP_BELOW_INDENT = 12  # characters of leading space: the line starts past the first column
BILATERAL_RE = re.compile(r"^[A-E]\s*-\s*(?:BILATERAL)?$", re.I)
CAP_RE = re.compile(r"^\d{1,3}(?:,\d{3})*$|^\d+$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in CELL_SPLIT.split(line.strip()) if c.strip()]


def _is_row(cells: list[str]) -> bool:
    if len(cells) < 3:
        # band and cap may share a cell when spacing is tight: "... C 226"
        return False
    return bool(TAIL_RE.match(cells[-2])) and bool(CAP_RE.match(cells[-1]))


def _split_tail(cells: list[str]) -> list[str]:
    """Handle 'FEEDER C' + '226' or 'FEEDER C 226' squeezed into one cell, and Ikeja's 'A -' band."""
    if len(cells) >= 2 and BILATERAL_RE.match(cells[-2]) and CAP_RE.match(cells[-1]):
        cells = cells[:-2] + [cells[-2].strip()[0].upper(), cells[-1]]  # "A -" / "A - Bilateral" is Band A
    if len(cells) >= 1:
        m = re.match(r"^(?P<rest>.*?)\s+(?P<band>[A-E])\s+(?P<cap>\d[\d,]*)$", cells[-1])
        if m and not _is_row(cells):
            cells = cells[:-1] + ([m.group("rest")] if m.group("rest") else []) + [m.group("band"), m.group("cap")]
    if len(cells) >= 2 and not _is_row(cells):
        m = re.match(r"^(?P<rest>.*?)\s+(?P<band>[A-E?])$", cells[-2])
        if m and CAP_RE.match(cells[-1]):
            cells = cells[:-2] + [m.group("rest"), m.group("band"), cells[-1]]
    return cells


def parse_pdf(path: Path, year: int | None = None, month: int | None = None) -> tuple[list[dict], list[str]]:
    """Parse a cap order using pypdf layout mode so column gaps survive.

    Two layouts exist:
      older (to mid 2024): BUSINESS UNIT | FEEDER NAME | BAND | CAP
      newer (2025 on):     STATE | BUSINESS UNIT | FEEDER NAME | BAND | CAP
    The layout is detected from the header (a STATE column) and confirmed by cell counts.
    """
    reader = pypdf.PdfReader(str(path))
    disco = disco_from_filename(path.name)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    known = {v for v in DISCO_ALIASES.values()}
    pages = [(pg.extract_text(extraction_mode="layout") or "") for pg in reader.pages]
    methods = ["text"] * len(pages)
    if any(len(t.strip()) < 20 for t in pages):
        # Scanned pages: use the committed OCR text when present (works on any OS); otherwise run
        # Apple Vision OCR (macOS only), which also writes that text for next time.
        ocr_dir = ROOT / "raw" / "ocr_text"
        h16 = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        ocr_mod = None
        for i, t in enumerate(pages):
            if len(t.strip()) >= 20:
                continue
            cached = ocr_dir / f"{h16}_p{i + 1}.txt"
            if cached.exists():
                pages[i] = cached.read_text(encoding="utf-8")
                methods[i] = "ocr"
                continue
            if ocr_mod is None:
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    import ocr_vision as ocr_mod  # noqa: F401
                except ImportError:
                    ocr_mod = False
            if ocr_mod:
                lines = ocr_mod.table_lines(str(path), i) or ocr_mod.page_lines(str(path), i)
                pages[i] = "\n".join(lines)
                methods[i] = "ocr"
    head = "\n".join(pages[:1]).upper()
    if disco not in known:  # file name did not say (e.g. a file from a ZIP bundle): read the title
        disco = disco_from_text(head) or disco
    has_state = bool(re.search(r"\bSTATE\b", head))
    n_lead = 2 if has_state else 1  # cells before the feeder name
    rows: list[dict] = []
    unparsed: list[str] = []
    last_lead = [""] * n_lead
    wrapped_below = 0
    for pno, text in enumerate(pages, start=1):
        carry: list[str] = []
        prev_was_row = False
        for raw in text.splitlines():
            if not raw.strip():
                continue
            flat = " ".join(raw.split())
            if (HEADER_RE.match(flat)
                    or re.match(r"^(STATE|BUSINESS|FEEDER|SE?R?VICE|BAND|CAP|\(KWH\)|NON-?\s*MD|SCHEDULE)\b", flat, re.I)
                    or re.match(r"^\d+\s*\|?\s*P\s*a\s*g\s*e\b", flat, re.I)):
                carry = []
                continue
            if flat.upper() == "BILATERAL":
                continue  # second line of Ikeja's "A - Bilateral" band cell
            cells = [c for c in _split_tail(_cells(raw)) if c.upper() != "BILATERAL"]
            if not _is_row(cells):
                indent = len(raw) - len(raw.lstrip())
                if prev_was_row and not carry and rows and indent >= WRAP_BELOW_INDENT and len(cells) == 1:
                    # The feeder name wrapped onto the line below its row ("ISAAC" / "JOHN"):
                    # nothing in the first column, so it belongs to the row above, not the next one.
                    rows[-1]["feeder_raw"] += " " + cells[0]
                    rows[-1]["feeder_name"] += " " + cells[0]
                    wrapped_below += 1
                    prev_was_row = False
                    continue
                prev_was_row = False
                if len(flat) > 2:
                    carry = carry + cells
                continue
            prev_was_row = True
            body = cells[:-2]
            band, cap = cells[-2], cells[-1]
            if carry:
                # wrapped row: the previous line(s) hold the start of the lead cells and feeder name
                body = carry + body
                carry = []
            if body and BILATERAL_RE.match(body[-1]):
                body = body[:-1]  # Ikeja's "A - Bilateral" band cell, read by OCR as an extra "A-" cell
            if has_state and 0 < len(body) < 3:
                # OCR ran state, business unit and feeder together: "LAGOS IKEJA BU 11-PTCINJ-T3-Awuse"
                m3 = re.match(r"^(?P<st>[A-Z][A-Z ]+?)\s+(?P<bu>[A-Z][A-Za-z .'-]*?\bBU)\s+(?P<f>.+)$", " ".join(body))
                if m3 and m3.group("st").upper() in STATES:
                    body = [m3.group("st"), m3.group("bu"), m3.group("f")]
            if len(body) >= n_lead + 1:
                lead = body[:n_lead]
                feeder = " ".join(body[n_lead:])
            elif len(body) == n_lead and n_lead == 2:
                # state present, business unit missing or merged: treat second cell as feeder
                lead = [body[0], last_lead[1]]
                feeder = body[1]
            else:
                lead = None  # merged cell: business unit printed once mid-group, fill after the page
                feeder = " ".join(body)
            if lead is not None:
                last_lead = lead
            state = (lead[0] if has_state else "") if lead else ""
            bu = lead[-1] if lead else ""
            loc = split_location(feeder) if False else {}
            m = re.match(r"^(?P<kv>\d{1,2})-(?P<inj>.+?)\s*INJ-?\s*T(?P<tx>\d+)-(?P<f>.+)$", feeder, re.I)
            kvm = re.search(r"(\d{2})\s*KV", feeder, re.I)
            rows.append({
                "disco": disco, "year": year or "", "month": month or "",
                "state": state.upper(), "business_unit": bu,
                "voltage_kv": (m.group("kv") if m else (kvm.group(1) if kvm else "")),
                "injection_substation": m.group("inj").strip() if m else "",
                "transformer": ("T" + m.group("tx")) if m else "",
                "feeder_name": m.group("f").strip() if m else feeder,
                "feeder_raw": feeder,
                "service_band": band, "cap_kwh": int(cap.replace(",", "")),
                "source_file": path.name, "source_page": pno, "source_sha16": sha,
                "bu_inferred": 0 if lead else 1,
                "extraction_method": methods[pno - 1],
            })
        if carry:
            unparsed.append(f"{path.name}:p{pno}: {' | '.join(carry)}")
    _fill_merged_cells(rows)
    return rows, unparsed


def _fill_merged_cells(rows: list[dict]) -> None:
    """Rows without a business unit take the nearest labelled row, split at the midpoint.

    Merged cells print the label once, vertically centred on its group, so a blank row belongs
    to whichever label is closer. State follows the same rule when it was blank too.
    """
    labelled = [i for i, r in enumerate(rows) if not r.get("bu_inferred")]
    if not labelled:
        return
    for i, r in enumerate(rows):
        if not r.get("bu_inferred"):
            continue
        before = [j for j in labelled if j < i]
        after = [j for j in labelled if j > i]
        cands = ([before[-1]] if before else []) + ([after[0]] if after else [])
        j = min(cands, key=lambda k: abs(k - i))
        r["business_unit"] = rows[j]["business_unit"]
        if not r["state"]:
            r["state"] = rows[j]["state"]


FIELDS = ["disco", "year", "month", "state", "business_unit", "voltage_kv", "injection_substation",
          "transformer", "feeder_name", "feeder_raw", "service_band", "cap_kwh",
          "source_file", "source_page", "source_sha16", "bu_inferred", "extraction_method"]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


FAILED_DOWNLOADS: list[str] = []
LISTED: dict[str, int] = {}


def run_month(year: int, month: int, sleep: float = 1.5) -> list[dict]:
    urls = find_month_pdfs(year, month)
    log(f"{year}-{month:02d}: {len(urls)} cap documents listed")
    LISTED[f"{year:04d}-{month:02d}"] = len(urls)
    all_rows: list[dict] = []
    all_unparsed: list[str] = []
    files: list[Path] = []
    for u in urls:
        try:
            files.extend(download_all(u, year, month))
        except Exception as e:  # noqa: BLE001
            log(f"  download failed {u}: {e}")
            FAILED_DOWNLOADS.append(u)
        time.sleep(sleep)
    for p in files:
        rows, unparsed = parse_pdf(p, year, month)
        bands = {}
        for r in rows:
            bands[r["service_band"]] = bands.get(r["service_band"], 0) + 1
        log(f"  {p.name}: {len(rows)} feeders, bands {dict(sorted(bands.items()))}, unparsed {len(unparsed)}")
        all_rows.extend(rows)
        all_unparsed.extend(unparsed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_DIR / f"nerc_caps_{year}-{month:02d}.csv", all_rows)
    if all_unparsed:
        with (OUT_DIR / "nerc_caps_unparsed.log").open("a", encoding="utf-8") as f:
            f.write("\n".join(all_unparsed) + "\n")
    return all_rows


def write_heartbeat() -> None:
    """data/last_checked.json changes on every run. It records what was found, and the commit it
    causes keeps the scheduled workflow alive (GitHub disables schedules after 60 idle days)."""
    from datetime import datetime, timezone
    hb = {"checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "documents_listed": LISTED, "failed_downloads": FAILED_DOWNLOADS}
    (ROOT / "data" / "last_checked.json").write_text(json.dumps(hb, indent=1))


def rebuild_all() -> None:
    rows: list[dict] = []
    for f in sorted(OUT_DIR.glob("nerc_caps_????-??.csv")):
        with f.open(encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    write_csv(OUT_DIR / "nerc_caps_all.csv", rows)
    log(f"nerc_caps_all.csv: {len(rows)} rows across {len(list(OUT_DIR.glob('nerc_caps_????-??.csv')))} months")


def month_range(a: str, b: str):
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    y, m = ya, ma
    while (y, m) <= (yb, mb):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="YYYY-MM")
    ap.add_argument("--from", dest="from_", help="YYYY-MM")
    ap.add_argument("--to", help="YYYY-MM")
    ap.add_argument("--parse-only", nargs="+", help="parse local PDFs and print a summary")
    args = ap.parse_args()

    if args.parse_only:
        for p in args.parse_only:
            rows, unparsed = parse_pdf(Path(p))
            log(f"{p}: {len(rows)} rows, {len(unparsed)} unparsed")
            for r in rows[:5]:
                log("  " + json.dumps({k: r[k] for k in ("state", "business_unit", "feeder_name", "service_band", "cap_kwh")}))
            for u in unparsed[:8]:
                log("  ? " + u)
        return

    if args.month:
        y, m = map(int, args.month.split("-"))
        run_month(y, m)
    elif args.from_ and args.to:
        for y, m in month_range(args.from_, args.to):
            run_month(y, m)
    else:
        t = date.today()
        run_month(t.year, t.month)
    rebuild_all()
    write_heartbeat()


if __name__ == "__main__":
    main()
