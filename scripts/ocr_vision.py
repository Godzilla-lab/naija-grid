"""
Local OCR for scanned NERC cap orders, using Apple's Vision framework (macOS only, no API, no cost).

page_lines(pdf_path, page_index) -> list[str]
    Renders the page at 300 dpi with PyMuPDF, runs VNRecognizeTextRequest (accurate mode, no
    language correction so numbers are not "fixed"), then rebuilds table rows from the text boxes:
    boxes are grouped into rows by vertical position and joined left to right, with a double space
    wherever the horizontal gap looks like a column break. The output matches pypdf's layout-mode
    lines closely enough for nerc_caps.parse_pdf to parse them unchanged.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median

import pymupdf as fitz  # PyMuPDF
import re
import Quartz
import Vision
from Foundation import NSData


# Vision sometimes returns Cyrillic look-alikes for Latin capitals in tables (АТ3 for AT3).
CYRILLIC_TO_LATIN = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M", "О": "O", "Р": "P",
    "Т": "T", "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S", "а": "a", "е": "e", "о": "o",
    "р": "p", "с": "c", "у": "y", "х": "x", "к": "k", "м": "m", "т": "t", "н": "h", "в": "b",
})


def _grid_lines(page, dpi: int = 150) -> tuple[list[float], list[float]]:
    """Find the table's horizontal and vertical ruling lines from pixel darkness.

    Returns (row_lines_y, col_lines_x) as fractions of the page, sorted. A pixel row counts as a
    ruling line when more than 45 percent of it is dark; neighbouring hits merge into one line.
    """
    import numpy as np
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    dark = a < 140

    def lines(frac, n):
        idx = np.where(frac > 0.45)[0]
        out, start = [], None
        for i, v in enumerate(idx):
            if start is None:
                start = prev = v
            elif v - prev > 2:
                out.append((start + prev) / 2 / n); start = v
            prev = v
        if start is not None:
            out.append((start + prev) / 2 / n)
        return out

    rows = lines(dark.mean(axis=1), pix.height)
    if len(rows) < 3:
        return [], []
    top, bot = int(rows[0] * pix.height), int(rows[-1] * pix.height)
    cols = lines(dark[top:bot].mean(axis=0), pix.width)
    merged = []
    for c in cols:  # thick borders register as two lines a few pixels apart
        if merged and c - merged[-1] < 0.015:
            merged[-1] = (merged[-1] + c) / 2
        else:
            merged.append(c)
    return rows, merged


CACHE = Path(__file__).resolve().parents[1] / "raw" / "ocr_text"


def table_lines(pdf_path: str, page_index: int, dpi: int = 300) -> list[str]:
    """Cached wrapper: OCR output is stored per file hash and page, so re-runs cost nothing."""
    import hashlib
    h = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()[:16]
    f = CACHE / f"{h}_p{page_index + 1}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").splitlines()
    lines = _table_lines(pdf_path, page_index, dpi)
    if not lines:
        # No ruled table found (for example a last page holding a single row): read the whole page.
        lines = page_lines(pdf_path, page_index, dpi)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines), encoding="utf-8")
    return lines


def _table_lines(pdf_path: str, page_index: int, dpi: int = 300) -> list[str]:
    """Row-by-row OCR for ruled tables.

    Pass 1 reads every table row as its own strip with word-level boxes.
    The band column position is then taken from the page itself (median x of single A to E words).
    Pass 2 builds each row from words left to right; any row that has a cap but no band gets its band
    cell re-read alone at high zoom, and if that still fails the band is written as '?', so the row is
    kept (and later excluded from band statistics) instead of being glued onto its neighbour.
    """
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    rows, cols = _grid_lines(page)
    if len(rows) < 3:
        doc.close()
        return []
    R = page.rect
    x0 = cols[0] if cols else 0.03
    x1 = cols[-1] if cols else 0.97
    gaps = [b - a for a, b in zip(rows, rows[1:])]
    gmed = sorted(gaps)[len(gaps) // 2]
    strips = []
    for y0, y1 in zip(rows, rows[1:]):
        if y1 - y0 < gmed * 0.4:
            continue
        clip = fitz.Rect(R.width * x0, R.height * y0, R.width * x1, R.height * y1)
        words = _recognise(page.get_pixmap(dpi=dpi, clip=clip).tobytes("png"), words=True)
        # convert to page coordinates
        pw = [(t.strip(), x0 + x * (x1 - x0), y0 + y * (y1 - y0), w * (x1 - x0), h * (y1 - y0)) for t, x, y, w, h in words if t.strip()]
        strips.append((y0, y1, pw))

    band_x = [x + w / 2 for _, _, pw in strips for t, x, y, w, h in pw if re.fullmatch(r"[A-E]", t)]
    bx = median(band_x) if len(band_x) >= 3 else None
    out = []
    for y0, y1, pw in strips:
        if not pw:
            continue
        # split the strip into text lines (a faint ruling line can hide a row boundary)
        hb = median(h for *_, h in pw) or 0.005
        pw.sort(key=lambda b: b[2] + b[4] / 2)
        sub: list[list[tuple]] = []
        for b in pw:
            yc = b[2] + b[4] / 2
            if sub and abs(yc - sub[-1][-1][-1]) < hb * 0.6:
                sub[-1].append(b + (yc,))
            else:
                sub.append([b + (yc,)])
        lines = []
        for g in sub:
            g.sort(key=lambda b: b[1])
            has_cap = bool(re.fullmatch(r"\d[\d,]*", g[-1][0]))
            lines.append([g, has_cap, median(b[-1] for b in g)])
        if not any(l[1] for l in lines):
            out.append(_join_words([b for l in lines for b in l[0]], hb, cols))
            continue
        row_lines = [l for l in lines if l[1]]
        for l in lines:
            if l[1]:
                continue
            k = min(row_lines, key=lambda r: abs(r[2] - l[2]))
            # wrapped name text: attach to the nearest row, never in the band or cap positions
            k[0] = sorted(k[0] + [b for b in l[0] if bx is None or b[1] + b[3] / 2 < bx - 0.02], key=lambda b: (b[1], b[2]))
        for g, _, yc in row_lines:
            cap = g[-1]
            if len(g) >= 3 and g[-2][0] == "-" and re.fullmatch(r"[A-E]", g[-3][0]):
                g = g[:-2] + [g[-1]]  # Ikeja's "A - Bilateral" band cell
            has_band = len(g) >= 2 and re.fullmatch(r"[A-E]", g[-2][0]) and (bx is None or abs(g[-2][1] + g[-2][3] / 2 - bx) < 0.04)
            body = g[:-2] if has_band else g[:-1]
            band = g[-2][0] if has_band else ""
            if not band and bx is not None:
                bounds = (y0, y1) if len(row_lines) == 1 else (yc - hb * 1.1, yc + hb * 1.1)
                band = _read_band_cell(page, bx, yc, rows=bounds, cols=cols) or "?"
            elif not band:
                band = "?"
            out.append(_join_words(body, hb, cols) + "    " + band + "    " + cap[0])
    doc.close()
    return out


def _join_words(words: list[tuple], hb: float, cols: list[float] | None = None) -> str:
    """Join words left to right. A column break (four spaces) goes wherever a ruling line lies between
    two words, or, without ruling lines, wherever the horizontal gap is wide."""
    words = sorted(words, key=lambda b: b[1])
    if not words:
        # A row where OCR found only the band and the cap (PHED Dec 2025, Mar and Apr 2026): return an
        # empty name so the row is logged as unparsed, instead of crashing and losing the whole order.
        return ""
    parts = [words[0][0]]
    for prev, cur in zip(words, words[1:]):
        end, start = prev[1] + prev[3], cur[1]
        if cols:
            brk = any(end - 0.004 <= c <= start + 0.004 for c in cols)
        else:
            brk = (start - end) > 0.02
        parts.append(("    " if brk else " ") + cur[0])
    return "".join(parts)


def _cgimage_from_png(png: bytes):
    data = NSData.dataWithBytes_length_(png, len(png))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def _recognise(png: bytes, words: bool = False) -> list[tuple[str, float, float, float, float]]:
    """Return (text, x, y, w, h) with y measured from the TOP, all normalised 0..1.

    words=True splits every recognised line into words and asks Vision for each word's own box.
    Slightly tilted scans make Vision chain the end of one table row onto the start of the next;
    word boxes let us place each word in its true row and column regardless.
    """
    from Foundation import NSMakeRange
    img = _cgimage_from_png(png)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    req.setRecognitionLanguages_(["en-US"])
    try:
        req.setAutomaticallyDetectsLanguage_(False)
    except AttributeError:
        pass
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed: {err}")
    out = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        c0 = cand[0]
        text = str(c0.string())
        if not words or " " not in text.strip():
            bb = obs.boundingBox()
            out.append((text.translate(CYRILLIC_TO_LATIN), bb.origin.x, 1.0 - (bb.origin.y + bb.size.height),
                        bb.size.width, bb.size.height))
            continue
        for m in re.finditer(r"\S+", text):
            box, _err = c0.boundingBoxForRange_error_(NSMakeRange(m.start(), m.end() - m.start()), None)
            if box is None:
                continue
            bb = box.boundingBox()
            out.append((m.group(0).translate(CYRILLIC_TO_LATIN), bb.origin.x, 1.0 - (bb.origin.y + bb.size.height),
                        bb.size.width, bb.size.height))
    return out


BAND_CELL_RE = re.compile(r"^([A-E])(?:\s*-\s*(?:BILATERAL)?)?$")


def _band_from_text(text: str) -> str:
    """'B' -> 'B'; Ikeja's 'A -' / 'A - Bilateral' cells -> 'A'."""
    m = BAND_CELL_RE.match(text.strip().upper().translate(CYRILLIC_TO_LATIN))
    return m.group(1) if m else ""


def _padded_png(page, clip, dpi: int, pad: int = 60) -> bytes:
    """Render a clip and centre it on a white canvas; Vision reads lone letters far better with margin."""
    pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csRGB, alpha=False)
    canvas = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, pix.width + 2 * pad, pix.height + 2 * pad), False)
    canvas.clear_with(255)
    pix.set_origin(pad, pad)
    canvas.copy(pix, pix.irect)
    return canvas.tobytes("png")


def _read_band_cell(page, xb: float, yc: float, dpi: int = 600,
                    rows: tuple[float, float] | None = None, cols: list[float] | None = None) -> str:
    """OCR one band cell, cropped tight and zoomed; single letters survive this, unlike full pages.

    Tries, in order: the old fixed crop; the cell between its own ruling lines, inset so the lines
    themselves are left out, on a white margin, at two zoom levels. The first A to E found wins.
    """
    r = page.rect
    clips = [fitz.Rect(r.width * (xb - 0.03), r.height * (yc - 0.012), r.width * (xb + 0.03), r.height * (yc + 0.012))]
    left, right = xb - 0.03, xb + 0.03
    if cols:
        lo = [c for c in cols if c < xb]
        hi = [c for c in cols if c > xb]
        if lo and hi and hi[0] - lo[-1] < 0.2:
            left, right = lo[-1], hi[0]
    top, bot = (rows if rows else (yc - 0.009, yc + 0.009))
    w, h = right - left, bot - top
    inner = fitz.Rect(r.width * (left + w * 0.08), r.height * (top + h * 0.12),
                      r.width * (right - w * 0.08), r.height * (bot - h * 0.12))
    for i, clip in enumerate(clips + [inner, inner]):
        png = page.get_pixmap(dpi=dpi, clip=clip).tobytes("png") if i == 0 else _padded_png(page, clip, (400, 800)[i - 1])
        texts = [t for t, *_ in _recognise(png)]
        for text in texts + [" ".join(texts)]:
            band = _band_from_text(text)
            if band:
                return band
    # Vision often skips a lone letter it is shown alone but reads it in the context of its whole
    # row, at some zoom levels and not others; take the A to E word whose centre sits in the band column.
    xa, xz = (cols[0], cols[-1]) if cols and len(cols) >= 2 else (0.03, 0.97)
    strip = fitz.Rect(r.width * xa, r.height * top, r.width * xz, r.height * bot)
    for zoom in (200, 600, 400, 250):
        for text, x, _y, w, _h in _recognise(_padded_png(page, strip, zoom), words=True):
            band = _band_from_text(text)
            if not band:
                continue
            # x is relative to the padded canvas; map back to the page
            pw = strip.width * zoom / 72
            pad = 60
            cx = xa + ((x + w / 2) * (pw + 2 * pad) - pad) / pw * (xz - xa)
            if abs(cx - xb) < 0.03:
                return band
    return ""


def page_lines(pdf_path: str, page_index: int, dpi: int = 300) -> list[str]:
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    boxes = _recognise(pix.tobytes("png"))
    if not boxes:
        doc.close()
        return []
    hmed = median(b[4] for b in boxes) or 0.01
    boxes.sort(key=lambda b: (b[2] + b[4] / 2))
    rows: list[list[tuple]] = []
    for b in boxes:
        yc = b[2] + b[4] / 2
        if rows and abs(yc - rows[-1][-1][-1]) < hmed * 0.6:
            rows[-1].append(b + (yc,))
        else:
            rows.append([b + (yc,)])

    # Second pass for band letters the first pass dropped (single isolated characters).
    band_x = [b[1] + b[3] / 2 for b in boxes if re.fullmatch(r"[A-E]", b[0].strip())]
    xb = median(band_x) if len(band_x) >= 3 else None

    lines = []
    for r in rows:
        r.sort(key=lambda b: b[1])
        cells = [b[0].strip() for b in r]
        yc = median(b[-1] for b in r)
        has_cap = bool(re.fullmatch(r"\d[\d,]*", cells[-1])) if cells else False
        has_band = len(cells) >= 2 and bool(re.fullmatch(r"[A-E]", cells[-2]))
        if has_cap and not has_band and xb is not None and len(cells) >= 3:
            letter = _read_band_cell(page, xb, yc)
            if letter:
                r.insert(len(r) - 1, (letter, r[-1][1] - 0.05, r[-1][2], 0.01, r[-1][4], yc))
        parts = [r[0][0]]
        for prev, cur in zip(r, r[1:]):
            gap = cur[1] - (prev[1] + prev[3])
            parts.append(("    " if gap > hmed * 0.9 else " ") + cur[0])
        lines.append("".join(parts))
    doc.close()
    return lines


def needs_ocr(page_text: str) -> bool:
    return len((page_text or "").strip()) < 20
