#!/usr/bin/env python3
"""
NERC Monthly Energy Cap orders -> one feeder-level table.

Usage:
  python3 scripts/nerc_caps.py                       # current and previous month (what CI runs)
  python3 scripts/nerc_caps.py --month 2026-09
  python3 scripts/nerc_caps.py --from 2022-01 --to 2026-10
  python3 scripts/nerc_caps.py --reparse             # rebuild every CSV from raw/pdfs, no network
  python3 scripts/nerc_caps.py --parse-only raw/pdfs/IE-Monthly-Energy-Cap-September-2026.pdf

Discovery: the NERC document library search, paginated as
  https://nerc.gov.ng/resources/page/<n>/?doc_term=monthly+energy+cap+<year>&ins=1
Every result is a publication card with a title, a date and a PDF link.

The order month is read from the PDF header ("Monthly Energy Cap (September 2026)"),
then from the listing title, then from the file name, in that order. File names on
the NERC site are unreliable (one Kano file is named January 2024 but is the
January 2025 order).

Only stdlib + pypdf are required. OCR (pytesseract + tesseract) is used only for
pages that carry no extractable text, and only if it is installed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmllib
import json
import re
import site
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.append(site.getusersitepackages())
import pypdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "raw" / "pdfs"
OUT_DIR = ROOT / "data"
SOURCES_CSV = OUT_DIR / "sources.csv"
UNPARSED_LOG = OUT_DIR / "nerc_caps_unparsed.log"
BASE = "https://nerc.gov.ng/resources/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 naija-grid-open-data (+https://github.com/Godzilla-lab/naija-grid)")
SLEEP = 1.5

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
# Longest first so "september" wins over "sep". "augus" is a real NERC typo (Aba, August 2024).
MONTH_TOKENS = sorted(
    {m: i + 1 for i, m in enumerate(MONTHS)}.items()
    | {m[:3]: i + 1 for i, m in enumerate(MONTHS)}.items()
    | {"sept": 9, "augus": 8}.items(),
    key=lambda kv: -len(kv[0]))
MONTH_NUM = dict(MONTH_TOKENS)
MONTH_YEAR_RE = re.compile(
    r"(" + "|".join(t for t, _ in MONTH_TOKENS) + r")[\s\-_.,()]*(20\d\d)", re.I)

STATES = sorted([
    "ABIA", "ADAMAWA", "AKWA IBOM", "ANAMBRA", "BAUCHI", "BAYELSA", "BENUE", "BORNO",
    "CROSS RIVER", "DELTA", "EBONYI", "EDO", "EKITI", "ENUGU", "FCT", "ABUJA", "GOMBE", "IMO",
    "JIGAWA", "KADUNA", "KANO", "KATSINA", "KEBBI", "KOGI", "KWARA", "LAGOS", "NASARAWA",
    "NIGER", "OGUN", "ONDO", "OSUN", "OYO", "PLATEAU", "RIVERS", "SOKOTO", "TARABA", "YOBE",
    "ZAMFARA",
], key=len, reverse=True)

# Canonical DisCo codes. Keys are matched against the start of the file name and the title.
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
    "PHED": "PHED", "PHEDC": "PHED", "PORT": "PHED", "PORTHARCOURT": "PHED",
    "YEDC": "YEDC", "YOLA": "YEDC",
    "APLE": "APLE", "APL": "APLE", "ABA": "APLE",
}
DISCO_NAMES = {
    "AEDC": "Abuja", "BEDC": "Benin", "EEDC": "Enugu", "EKEDC": "Eko", "IBEDC": "Ibadan",
    "IKEDC": "Ikeja", "JEDC": "Jos", "KAEDC": "Kaduna", "KEDCO": "Kano", "PHED": "Port Harcourt",
    "YEDC": "Yola", "APLE": "Aba Power",
}

ROW_RE = re.compile(r"^(?P<location>.+?)\s+(?P<band>[A-E])\s+(?P<cap>\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*$")
HEADER_RE = re.compile(
    r"^(P\s*a\s*g\s*e\s*\||Page \||Page \d+|\d+\s*\|\s*P\s*a\s*g\s*e|NIGERIAN ELECTRICITY|Order No|.*Monthly Energy Cap|"
    r".*Energy Consumed in|Consumed in|Monthly Energy Caps of|Energy Caps of|Unmetered Customers|"
    r"in the Nigerian Electricity|Nigerian Electricity|Electricity Supply Industry|SCHEDULE\b|"
    r"STATE\b.*BUSINESS|BUSINESS UNIT|SERVICE\s*(BAND)?\s*$|BAND\s*$|CAP\s*(\(kWh\))?\s*$|\(kWh\)|"
    r"NON-?\s*MD\s*$|FEEDER NAME|Feeder\s*$|S/?N\b.*FEEDER)", re.I)

FIELDS = ["disco", "year", "month", "period", "state", "business_unit", "voltage_kv",
          "injection_substation", "transformer", "feeder_name", "feeder_raw", "location_raw",
          "feeder_key", "service_band", "cap_kwh", "extraction_method",
          "source_file", "source_page", "source_sha16"]
SOURCE_FIELDS = ["disco", "year", "month", "period", "period_from", "status", "url", "filename",
                 "title", "published", "sha256", "pages", "bytes", "feeders_parsed",
                 "extraction_method", "text_pages", "image_only_pages", "unparsed_lines"]


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- network

_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE
_tls_relaxed = False


def http(url: str, method: str = "GET", timeout: int = 90, retries: int = 3):
    """Return (status, headers, body). Retries timeouts and refused connections, never 404s."""
    global _tls_relaxed
    url = urllib.parse.quote(url, safe=":/?&=%#+,;@!$'()*~")  # some NERC file names contain spaces
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
            ctx = _INSECURE if _tls_relaxed else None
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.status, dict(r.headers), (r.read() if method == "GET" else b"")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 403):
                return e.code, dict(e.headers or {}), b""
            last = e
        except (ssl.SSLError, urllib.error.URLError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
                if not _tls_relaxed:
                    log("  TLS verification failed for nerc.gov.ng, retrying without verification")
                    _tls_relaxed = True
                    continue
            if "nodename nor servname" in str(e) or "Name or service not known" in str(e):
                raise RuntimeError(f"DNS failure {url}: {e}") from e
            last = e
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3 + attempt * 5)
    raise RuntimeError(f"{method} failed {url}: {last}")


def get_text(url: str) -> str:
    status, _, body = http(url)
    if status != 200:
        raise RuntimeError(f"HTTP {status} {url}")
    return body.decode("utf-8", "ignore")


# ---------------------------------------------------------------- discovery

CARD_RE = re.compile(r'<div class="publication">.*?btn-download" download>', re.S)


def parse_listing(page_html: str) -> list[dict]:
    docs = []
    for blk in CARD_RE.findall(page_html):
        t = re.search(r'<h6 class="title">(.*?)</h6>', blk, re.S)
        d = re.search(r'<li><a [^>]*title="([^"]+)"', blk)
        u = re.search(r'href="(https?://nerc\.gov\.ng/wp-content/uploads/[^"]+?\.pdf)"', blk, re.I)
        if not u:
            continue
        title = htmllib.unescape(re.sub(r"\s+", " ", t.group(1)).strip()) if t else ""
        docs.append({"url": htmllib.unescape(u.group(1)), "title": title,
                     "published": d.group(1) if d else ""})
    return docs


def list_documents(term: str, max_pages: int = 40) -> list[dict]:
    q = urllib.parse.urlencode({"doc_term": term, "ins": 1})
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}?{q}" if page == 1 else f"{BASE}page/{page}/?{q}"
        page_html = get_text(url)
        docs = parse_listing(page_html)
        total = re.search(r"(\d+) results", page_html)
        out.extend(docs)
        if page == 1:
            log(f"  listing '{term}': {total.group(1) if total else '?'} results")
        if not docs or f"page/{page + 1}/" not in page_html:
            break
        time.sleep(SLEEP)
    seen, uniq = set(), []
    for d in out:
        if d["url"] not in seen:
            seen.add(d["url"])
            uniq.append(d)
    return uniq


def is_cap_doc(doc: dict) -> bool:
    name = urllib.parse.unquote(Path(urllib.parse.urlparse(doc["url"]).path).name)
    blob = f"{doc.get('title', '')} {name}"
    return bool(re.search(r"ener\w*[\s\-_]*caps?|\bcaps?\b", blob, re.I)) and not re.search(
        r"methodology|consultation|review of|amendment", doc.get("title", ""), re.I)


def period_from_text(text: str) -> tuple[int, int] | None:
    m = MONTH_YEAR_RE.search(text or "")
    if not m:
        return None
    return int(m.group(2)), MONTH_NUM[m.group(1).lower()]


def guess_period(doc: dict) -> tuple[tuple[int, int] | None, str]:
    p = period_from_text(doc.get("title", ""))
    if p:
        return p, "title"
    name = urllib.parse.unquote(Path(urllib.parse.urlparse(doc["url"]).path).name)
    p = period_from_text(name)
    return (p, "filename") if p else (None, "")


def disco_from(name: str, title: str = "") -> str:
    for text in (Path(name).stem, title):
        up = re.sub(r"[^A-Z]", "", text.upper().split(" ")[0]) if text else ""
        first = re.split(r"[-_ ]", text.strip())[0].upper() if text else ""
        if first in DISCO_ALIASES:
            return DISCO_ALIASES[first]
        for key in sorted(DISCO_ALIASES, key=len, reverse=True):
            if up.startswith(key) or re.sub(r"[^A-Z]", "", text.upper()).startswith(key):
                return DISCO_ALIASES[key]
    return Path(name).stem.split()[0].upper()


def local_name(url: str) -> str:
    name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    name = re.sub(r"\s+", "-", name.strip())
    return re.sub(r"-{2,}", "-", name)


# ---------------------------------------------------------------- registry

def load_sources() -> dict[str, dict]:
    if not SOURCES_CSV.exists():
        return {}
    with SOURCES_CSV.open(encoding="utf-8") as f:
        return {r["url"]: r for r in csv.DictReader(f)}


def save_sources(reg: dict[str, dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(reg.values(), key=lambda r: (r.get("period", ""), r.get("disco", ""), r["filename"]))
    with SOURCES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SOURCE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SOURCE_FIELDS})


def download(url: str, known_bytes: str = "") -> Path | None:
    """Download once. A file on disk is kept if its size matches the registry or the server."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / local_name(url)
    if dest.exists():
        size = dest.stat().st_size
        if known_bytes and str(size) == str(known_bytes):
            return dest
        try:
            status, headers, _ = http(url, method="HEAD", timeout=30, retries=2)
            remote = headers.get("Content-Length") or headers.get("content-length")
            if status != 200 or not remote or int(remote) == size:
                return dest
            log(f"  size changed on server ({size} -> {remote}), re-downloading {dest.name}")
        except Exception:  # noqa: BLE001
            return dest
    status, _, body = http(url)
    time.sleep(SLEEP)
    if status != 200 or not body.startswith(b"%PDF"):
        log(f"  skip {url}: HTTP {status}, {len(body)} bytes")
        return None
    dest.write_bytes(body)
    return dest


# ---------------------------------------------------------------- parsing

def feeder_key(text: str) -> str:
    s = text.upper()
    s = re.sub(r"[^\w/\s]|_", " ", s)
    return " ".join(s.split())


def split_location(loc: str, has_state: bool) -> dict:
    s = loc.strip()
    out = {"state": "", "business_unit": "", "location_raw": s, "voltage_kv": "",
           "injection_substation": "", "transformer": "", "feeder_name": ""}
    if has_state:
        up = s.upper()
        for st in STATES:
            if up.startswith(st + " "):
                out["state"] = st
                s = s[len(st):].strip()
                break
    no_state = s
    m = re.match(r"^(?P<bu>.+?\bBU)\s+(?P<rest>.+)$", s)
    if m:
        out["business_unit"] = m.group("bu").strip()
        s = m.group("rest").strip()
    else:
        m = re.match(r"^(?P<bu>[A-Za-z][A-Za-z .\-/&']+?)\s+(?P<rest>\d{1,2}\s*(?:kV)?-.+)$", s, re.I)
        if m:
            out["business_unit"] = m.group("bu").strip()
            s = m.group("rest").strip()
    out["feeder_raw"] = s
    m = re.match(r"^(?P<kv>\d{1,2})-(?P<inj>.+?)\s*INJ-?\s*T(?P<tx>\d+)-(?P<feeder>.+)$", s, re.I)
    if m:
        out["voltage_kv"] = m.group("kv")
        out["injection_substation"] = m.group("inj").strip()
        out["transformer"] = "T" + m.group("tx")
        out["feeder_name"] = m.group("feeder").strip()
    else:
        m = re.match(r"^(?P<kv>11|33)\s*(?:KV)?\s*-\s*(?P<feeder>.+)$", s, re.I)
        if m:
            out["voltage_kv"] = m.group("kv")
            out["feeder_name"] = m.group("feeder").strip()
        else:
            out["feeder_name"] = s
            kv = re.search(r"\b(11|33)\s*KV\b", s, re.I)
            if kv:
                out["voltage_kv"] = kv.group(1)
    # Key = business unit + feeder, state dropped (only some years print a state column).
    out["feeder_key"] = feeder_key(no_state)
    return out


def starts_with_state(text: str) -> bool:
    up = text.upper()
    return any(up.startswith(st + " ") for st in STATES)


_OCR_STATE: dict = {}


def ocr_page(path: Path, pno: int) -> str:
    """OCR one page. Needs pytesseract, tesseract and pdftoppm (poppler). Returns '' if unavailable."""
    if _OCR_STATE.get("unavailable"):
        return ""
    try:
        import subprocess
        import tempfile

        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdftoppm", "-r", "300", "-f", str(pno), "-l", str(pno), "-png",
                            str(path), f"{td}/p"], check=True, capture_output=True)
            pngs = sorted(Path(td).glob("p*.png"))
            return pytesseract.image_to_string(Image.open(pngs[0]), config="--psm 6") if pngs else ""
    except Exception as e:  # noqa: BLE001
        _OCR_STATE["unavailable"] = True
        log(f"  OCR unavailable ({e.__class__.__name__}); image-only pages are counted, not parsed")
        return ""


def page_has_image(page) -> bool:
    try:
        xo = (page.get("/Resources") or {}).get("/XObject") or {}
        for v in xo.values():
            o = v.get_object()
            if o.get("/Subtype") == "/Image" and int(o.get("/Width", 0)) > 400:
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def parse_pdf(path: Path, disco: str | None = None, period: tuple[int, int] | None = None) -> dict:
    """Parse one cap order. Returns rows, unparsed lines and file facts."""
    data = path.read_bytes()
    reader = pypdf.PdfReader(str(path))
    disco = disco or disco_from(path.name)
    sha = hashlib.sha256(data).hexdigest()
    rows: list[dict] = []
    unparsed: list[str] = []
    header_period = None
    text_pages = image_only = 0
    methods = set()
    page_texts = []
    for pno, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        method = "text"
        body = [l for l in (" ".join(x.split()) for x in text.splitlines()) if l and not HEADER_RE.match(l)]
        if len(body) == 0 and page_has_image(page):
            image_only += 1
            o = ocr_page(path, pno)
            if o.strip():
                text, method = o, "ocr"
        elif text.strip():
            text_pages += 1
        page_texts.append((pno, text, method))
    first_text = page_texts[0][1] if page_texts else ""
    header_period = period_from_text(first_text[:1200])
    has_state = bool(re.search(r"\bSTATE\b", first_text[:2500]))
    yr, mo = (period or header_period or (None, None))
    for pno, text, method in page_texts:
        lines = [" ".join(raw.split()) for raw in text.splitlines()]
        lines = [l for l in lines if l]
        carry = ""
        for line in lines:
            m = ROW_RE.match(line)
            if m and carry and not HEADER_RE.match(carry) and len(carry) < 160:
                # A wrapped row whose second half also looks like a row on its own:
                # "FCT APO AT3_H37_S26_BEHIND" + "TRANSMISSION A 838". Join it rather than drop
                # the first half. In files with a STATE column, only when the first half starts
                # with a state and the second half does not.
                if not has_state or (starts_with_state(carry) and not starts_with_state(line)):
                    joined = carry + " " + line
                    mj = ROW_RE.match(joined)
                    if mj:
                        m, line = mj, joined
                    else:
                        unparsed.append(f"{path.name}:p{pno}: {carry}")
                else:
                    unparsed.append(f"{path.name}:p{pno}: {carry}")
                carry = ""
            if not m and carry:
                joined = carry + " " + line
                m = ROW_RE.match(joined)
                if m:
                    line = joined
                    carry = ""
                elif len(carry) < 160 and not HEADER_RE.match(line):
                    carry = joined
                    continue
            if not m:
                if HEADER_RE.match(line):
                    carry = ""
                    continue
                if carry:
                    unparsed.append(f"{path.name}:p{pno}: {carry}")
                carry = line
                continue
            carry = ""
            loc = split_location(m.group("location"), has_state)
            methods.add(method)
            rows.append({
                "disco": disco, "year": yr or "", "month": mo or "",
                "period": f"{yr}-{mo:02d}" if yr else "", **loc,
                "service_band": m.group("band"),
                "cap_kwh": int(m.group("cap").replace(",", "")),
                "extraction_method": method,
                "source_file": path.name, "source_page": pno, "source_sha16": sha[:16],
            })
        if carry and not HEADER_RE.match(carry):
            unparsed.append(f"{path.name}:p{pno}: {carry}")
    return {
        "rows": rows, "unparsed": unparsed, "sha256": sha, "pages": len(reader.pages),
        "bytes": len(data), "header_period": header_period, "text_pages": text_pages,
        "image_only_pages": image_only,
        "extraction_method": "+".join(sorted(methods)) if methods else "",
    }


# ---------------------------------------------------------------- outputs

def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def pub_order(r: dict) -> tuple:
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", r["url"])
    return (m.group(1), m.group(2)) if m else ("", "")


def resolve_duplicates(reg: dict[str, dict], periods: set[str]) -> None:
    """One file per DisCo per month. If NERC posted two, keep the later upload."""
    groups: dict[tuple, list[dict]] = {}
    for r in reg.values():
        if r.get("period") in periods and r.get("status") in ("used", "duplicate"):
            groups.setdefault((r["period"], r["disco"]), []).append(r)
    for key, rs in groups.items():
        rs.sort(key=lambda r: (pub_order(r), int(r.get("feeders_parsed") or 0)), reverse=True)
        rs[0]["status"] = "used"
        for r in rs[1:]:
            r["status"] = "duplicate"
            log(f"  duplicate for {key}: keeping {rs[0]['filename']}, dropping {r['filename']}")


def write_period(reg: dict[str, dict], period: str, cache: dict[str, dict]) -> int:
    rows: list[dict] = []
    for r in sorted(reg.values(), key=lambda r: (r["disco"], r["filename"])):
        if r.get("period") != period or r.get("status") != "used":
            continue
        res = cache.get(r["filename"])
        if res is None:
            y, m = map(int, period.split("-"))
            res = parse_pdf(PDF_DIR / r["filename"], r["disco"], (y, m))
            cache[r["filename"]] = res
        rows.extend(res["rows"])
    out = OUT_DIR / f"nerc_caps_{period}.csv"
    if rows:
        write_csv(out, rows)
    elif out.exists():
        out.unlink()
    return len(rows)


def rebuild_all() -> None:
    rows: list[dict] = []
    for f in sorted(OUT_DIR.glob("nerc_caps_????-??.csv")):
        with f.open(encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    write_csv(OUT_DIR / "nerc_caps_all.csv", rows)
    log(f"nerc_caps_all.csv: {len(rows)} rows")
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
        ints = {"year", "month", "cap_kwh", "source_page"}
        cols = {k: [(int(r[k]) if r[k] != "" else None) if k in ints else r[k] for r in rows]
                for k in FIELDS}
        pq.write_table(pa.table(cols), OUT_DIR / "nerc_caps_all.parquet", compression="zstd")
        log("nerc_caps_all.parquet written")
    except ImportError:
        log("pyarrow not installed, parquet skipped")


def write_unparsed_log(reg: dict[str, dict], cache: dict[str, dict]) -> None:
    lines = []
    for r in sorted(reg.values(), key=lambda r: (r.get("period", ""), r["filename"])):
        res = cache.get(r["filename"])
        if res and r.get("status") == "used":
            lines.extend(res["unparsed"])
    UNPARSED_LOG.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# ---------------------------------------------------------------- driver

def month_range(a: str, b: str):
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    y, m = ya, ma
    while (y, m) <= (yb, mb):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def ingest(doc: dict, reg: dict[str, dict], cache: dict[str, dict]) -> str | None:
    """Download and parse one listed document. Returns its period (YYYY-MM) or None."""
    url = doc["url"]
    prev = reg.get(url, {})
    path = download(url, prev.get("bytes", ""))
    if path is None:
        return None
    disco = disco_from(path.name, doc.get("title", ""))
    res = parse_pdf(path, disco)
    guess, guess_from = guess_period(doc)
    if res["header_period"]:
        (y, m), src = res["header_period"], "pdf_header"
        if guess and guess != res["header_period"]:
            log(f"  note: {path.name} listed as {guess[0]}-{guess[1]:02d} ({guess_from}) "
                f"but the PDF header says {y}-{m:02d}; using the header")
    elif guess:
        (y, m), src = guess, guess_from
    else:
        log(f"  cannot date {path.name}, skipped")
        return None
    period = f"{y}-{m:02d}"
    for row in res["rows"]:
        row.update(year=y, month=m, period=period)
    cache[path.name] = res
    reg[url] = {
        "disco": disco, "year": y, "month": m, "period": period, "period_from": src,
        "status": "used" if res["rows"] else "no_rows", "url": url, "filename": path.name,
        "title": doc.get("title", prev.get("title", "")),
        "published": doc.get("published", prev.get("published", "")),
        "sha256": res["sha256"], "pages": res["pages"], "bytes": res["bytes"],
        "feeders_parsed": len(res["rows"]), "extraction_method": res["extraction_method"],
        "text_pages": res["text_pages"], "image_only_pages": res["image_only_pages"],
        "unparsed_lines": len(res["unparsed"]),
    }
    return period


def run(periods: list[tuple[int, int]]) -> None:
    want = {f"{y}-{m:02d}" for y, m in periods}
    reg = load_sources()
    cache: dict[str, dict] = {}
    years = sorted({y for y, _ in periods})
    touched: set[str] = set()
    for y in years:
        docs = [d for d in list_documents(f"monthly energy cap {y}") if is_cap_doc(d)]
        log(f"{y}: {len(docs)} cap documents listed")
        for d in docs:
            g, _ = guess_period(d)
            gp = f"{g[0]}-{g[1]:02d}" if g else None
            # The listing title decides what to fetch; the PDF header then decides the month.
            if gp is not None and gp not in want:
                continue
            try:
                p = ingest(d, reg, cache)
            except Exception as e:  # noqa: BLE001
                log(f"  failed {d['url']}: {e}")
                continue
            if p:
                touched.add(p)
        time.sleep(SLEEP)
    resolve_duplicates(reg, touched)
    for y, m in periods:
        if f"{y}-{m:02d}" not in touched:
            log(f"{y}-{m:02d}: no orders found on NERC (not published yet, or never published)")
    for period in sorted(touched):
        n = write_period(reg, period, cache)
        used = [r for r in reg.values() if r.get("period") == period and r.get("status") == "used"]
        by = {r["disco"]: int(r["feeders_parsed"]) for r in used}
        unp = sum(int(r["unparsed_lines"]) for r in used)
        log(f"{period}: {len(used)} DisCo files, {n} feeders, unparsed {unp}, {dict(sorted(by.items()))}")
    save_sources(reg)
    reparse_unparsed_log(reg, cache)
    rebuild_all()


def reparse_unparsed_log(reg: dict[str, dict], cache: dict[str, dict]) -> None:
    for r in reg.values():
        if r.get("status") == "used" and r["filename"] not in cache and (PDF_DIR / r["filename"]).exists():
            if int(r.get("unparsed_lines") or 0):
                cache[r["filename"]] = parse_pdf(PDF_DIR / r["filename"], r["disco"],
                                                 (int(r["year"]), int(r["month"])))
    write_unparsed_log(reg, cache)


def reparse() -> None:
    """Rebuild every CSV and the sources table from the PDFs on disk. No network."""
    reg = load_sources()
    cache: dict[str, dict] = {}
    for url, r in list(reg.items()):
        path = PDF_DIR / r["filename"]
        if not path.exists():
            continue
        y, m = int(r["year"]), int(r["month"])
        res = parse_pdf(path, r["disco"], (y, m))
        cache[r["filename"]] = res
        r.update(sha256=res["sha256"], pages=res["pages"], bytes=res["bytes"],
                 feeders_parsed=len(res["rows"]), extraction_method=res["extraction_method"],
                 text_pages=res["text_pages"], image_only_pages=res["image_only_pages"],
                 unparsed_lines=len(res["unparsed"]))
        if r["status"] == "no_rows" and res["rows"]:
            r["status"] = "used"
    periods = {r["period"] for r in reg.values()}
    resolve_duplicates(reg, periods)
    for f in OUT_DIR.glob("nerc_caps_????-??.csv"):
        f.unlink()
    for period in sorted(periods):
        n = write_period(reg, period, cache)
        log(f"{period}: {n} feeders")
    save_sources(reg)
    write_unparsed_log(reg, cache)
    rebuild_all()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="YYYY-MM")
    ap.add_argument("--from", dest="from_", help="YYYY-MM")
    ap.add_argument("--to", help="YYYY-MM")
    ap.add_argument("--reparse", action="store_true", help="rebuild outputs from raw/pdfs only")
    ap.add_argument("--parse-only", nargs="+", metavar="PDF")
    args = ap.parse_args()
    if args.parse_only:
        for p in args.parse_only:
            res = parse_pdf(Path(p))
            log(f"{p}: {len(res['rows'])} rows, {len(res['unparsed'])} unparsed, "
                f"{res['pages']} pages, header period {res['header_period']}")
            for r in res["rows"][:5]:
                log("  " + json.dumps({k: r[k] for k in ("state", "business_unit", "feeder_raw",
                                                          "service_band", "cap_kwh")}))
            for u in res["unparsed"][:8]:
                log("  ? " + u)
        return
    if args.reparse:
        reparse()
        return
    if args.month:
        y, m = map(int, args.month.split("-"))
        periods = [(y, m)]
    elif args.from_ and args.to:
        periods = list(month_range(args.from_, args.to))
    else:
        t = date.today()
        prev = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
        periods = [prev, (t.year, t.month)]
    run(periods)


if __name__ == "__main__":
    main()
