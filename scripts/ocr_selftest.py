#!/usr/bin/env python3
"""Prove OCR works on this machine before a refresh relies on it.

Reads page 1 of a committed scanned order (Aba Power, December 2025) fresh, without the committed
OCR text, and checks for rows we know are on it. Exits 1 if Vision is missing or reads it wrong.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PDF = ROOT / "raw" / "pdfs" / "APLE-monthly-energy-caps-December-2025.pdf"
EXPECT = [("7-UP 1", "52"), ("7-UP 2", "247"), ("ABA BARRACKS", "117"), ("ABA TOWNSHIP", "647")]

try:
    import ocr_vision
except ImportError as e:
    print(f"OCR self-test FAILED: Vision OCR not available here ({e})")
    sys.exit(1)

lines = ocr_vision._table_lines(str(PDF), 0)  # bypasses raw/ocr_text on purpose
text = "\n".join(lines)
missing = [f"{f} {c}" for f, c in EXPECT if not any(f in l and l.rstrip().endswith(c) for l in lines)]
if len(lines) < 10 or missing:
    print(f"OCR self-test FAILED: {len(lines)} lines read; missing {missing}")
    print(text[:1500])
    sys.exit(1)
print(f"OCR self-test passed: {len(lines)} lines read, all {len(EXPECT)} known rows found.")
