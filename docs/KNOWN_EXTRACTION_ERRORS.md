# Known extraction errors

Every mistake we have seen OCR, PDF text extraction or downloading make on these documents, what corrects it now, and what guards against it coming back. When the monthly refresh runs unattended, these are the corrections it applies. Add a row whenever a new mistake is found, with a real example and a test.

Status: **fixed** (corrected automatically and tested), **flagged** (cannot be corrected safely, so the row is marked and kept out of statistics), **open** (still needs a person).

## Scanned cap orders (Apple Vision OCR, November 2025 to August 2026)

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 1 | A lone band letter in its own cell is skipped, most often C (it looks like a bracket) | YEDC July 2026 p2, `GRA MUBI`: band missing | Re-read the cell inset between its ruling lines on a white margin at 400 and 800 dpi; if still missing, re-read the whole row at 200, 600, 400 and 250 dpi and take the A to E word sitting in the band column (`ocr_vision._read_band_cell`). Recovered 488 of 506 | `test_recovered_band_letters`, `test_unreadable_bands_stay_rare` (under 0.5 percent) | fixed; 18 remain as `?` |
| 2 | Cyrillic look-alikes returned for Latin capitals | `АТ3` for `AT3` | `CYRILLIC_TO_LATIN` map on every recognised word | parser tests on scanned pages | fixed |
| 3 | On a slightly tilted scan, the end of one row is chained onto the start of the next | Kaduna Jan 2026 | Read each table row as its own strip and place every word by its own box (`_recognise(words=True)`) | `ocr_selftest.py` (runs before every refresh) | fixed |
| 4 | Thick borders register as two ruling lines, leaving an empty last column and merged rows | Ikeja Feb 2026 | Merge column lines closer than 1.5 percent of the page width | `ocr_selftest.py` | fixed |
| 5 | Business unit and state run together in one cell | `LAGOS IKEJA BU 11-PTCINJ-T3-Awuse` | Split words at the table's ruling lines; when still joined, split `STATE  ... BU  feeder` by pattern | `test_business_units_are_not_feeder_fragments` | fixed |
| 6 | A last page with a single row, or no ruled table, is read as empty | PHED May 2026, `UPTH C 258` | Fall back to whole-page reading when no grid is found | parser tests | fixed |
| 7 | Ikeja's `A - Bilateral` band cell read as an extra `A-` cell, so the feeder name moved into the business unit | `SHOMOLU BU 11-MagodoINJ-T1-Shangisha / A-` | `BILATERAL_RE` drops the extra cell; the band is A | `test_recovered_band_letters` (Shangisha is A) | fixed |
| 8 | Capital I read as lowercase l in Ikeja's injection tag | `AgegelNJ-T1`, `MagodolN-T1` (327 rows) | `fix_ocr_name`: `lNJ` / `lN` before `-T<n>` becomes `INJ` (scanned pages only) | `test_ocr_name_fixes` | fixed |
| 9 | Capital I read as lowercase l at the start of a word | `ljaiye Ojokoro` | `fix_ocr_name`: a word starting `lj` becomes `Ij` (no Nigerian name starts with lj) | `test_ocr_name_fixes` | fixed |
| 10 | Noise around state names | `ILAGOS`, `[SOKOTO`, `ADAMAWAR` | `clean_state`: strip stray characters, then match to the 37 states at similarity 0.86 or more | `test_main_table_values` (state in the list) | fixed |
| 11 | Two-word states split across two columns | `AKWA` / `IBOM`, `CROSS` / `RIVER` | Rejoin when state plus business unit spell a two-word state | `test_main_table_values` | fixed |
| 12 | Other letter misreads in feeder names | `TUPTH` for `UPTH`; `IlupejuNJ` | Not corrected in the name; the row is linked to its feeder by close-name matching (similarity 0.88 or more) and flagged `id_link = fuzzy_ocr` | `test_few_one_month_feeders` | flagged |
| 13a | A table row where OCR finds only the band and the cap crashed the reader, and the whole order was dropped. Three orders were missing from every release until 2026-10-27 | PHED Dec 2025, Mar 2026, Apr 2026 (249 rows in Apr 2026 alone) | An empty name is returned and the row logged as unparsed; the rest of the order is kept | `test_no_order_failed_to_extract`, `test_every_pdf_is_in_sources`, and the health check now reports any failed order in any month | fixed |
| 13b | A word split by a space, which made a second, one-month copy of the feeder | `11KV AJI YA` beside `11KV AJIYA` (Yola, Jun 2025) | Names that differ only by spaces within a DisCo are folded into their most common spelling, keeping that spelling's feeder_id | `test_few_one_month_feeders` | fixed |
| 13 | Injection substation and feeder run together with no `INJ` at all | `IlupejuNJ-T4` style names where the tag is damaged beyond rule 8 | none | none | open |

## Text cap orders (pypdf layout mode)

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 14 | A feeder name too long for its cell continues on the line below, and was glued onto the next row (7,028 rows) | `11-SECRETARIATINJ-T1-LATEEF` / `JAKANDE` | A line with text only in the feeder column (indented 12 or more characters) straight after a row is joined to that row | `test_few_one_month_feeders` (one-month feeders were 20.5 percent, now about 15) | fixed |
| 15 | `A - Bilateral` band printed over two lines, so the row was not recognised and merged into its neighbours (about 465 rows) | Ikeja Jul 2023 `HILLTOP  A -  617` / `BILATERAL` | `A -` and `A - Bilateral` read as Band A; a line holding only `BILATERAL` is skipped | `test_business_units_are_not_feeder_fragments` | fixed |
| 16 | Business unit wraps onto the next line | `AKOWONJO` / `BU` | A line starting `BU` straight after a row completes that row's business unit | `test_business_units_are_not_feeder_fragments` | fixed |
| 17 | Merged business-unit cells printed once, mid-group | Eko Oct 2022 | Fill blank units from the nearest label by row position | parser test on Eko Oct 2022 | fixed |
| 18 | NERC prints the same row twice in one order | 634 rows | Exact repeats dropped and counted | `test_one_row_per_feeder_month` | fixed |

## State regulator files

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 19 | Spaces stripped from the whole PDF text | EERC July 2026, `ABAKALIKIROAD11KV` | Restore the name from EERC's own later files, else from NERC's printed name, when the space-free forms match | state parse tests | fixed |
| 20 | Misprint in the regulator's own file | EERC July 2026 `ORBAOBLLO33KV` | `EERC_TYPOS` map, checked against the same feeder in EERC's other months | state parse tests | fixed |
| 21 | Cap cell printed as `-` (no cap) | EERC Aug and Sep 2026, `GOVERNMENT HOUSE 11KV` | Row not created; logged in `data/parsed/state_qa.log` | health check warns above 10 lines | flagged |

## Tariff orders (naira caps)

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 22 | Typeset text stored as drawn outlines, so the PDF has no text | NERC Sep 2026 HoldCo orders | Render the page and read it with OCR | values read by eye | fixed |
| 23 | OCR drops whole columns from scanned multi-column tables | JED MYTO 2024 Table 10: only the cost-reflective column came out | Each value read from the rendered table image by eye; `checked` column in `data/reference/tariffs_non_md.csv` | none automatic | open |
| 24 | Order prints a wrong period label | JED Sep 2026: `Jul 2024 - Aug 2026` in an order effective September 2026 | Treated as still in force; noted in the row | note in the table | flagged |
| 25 | Order skips a month | IBEDC and KEDCO: `May - Jun 2024` then `Aug 2024 - Sep 2026` | July 2024 Band A left blank, never guessed | note in the table | flagged |

## Feeder to area (service-level appendices of tariff orders)

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 29 | Text is vertically centred in tall cells, so a long feeder name starts above its row number and reading by text line splits it between rows | LASERC Eko Sep 2026, `AJAH TS_AJAH LOCAL T1_AJAH LOCAL_AJIWE` | Rows are cut at the table's drawn ruling lines, not at text lines (`feeder_areas.ruled_rows`) | `test_feeder_areas` | fixed |
| 30 | The appendix heading is on its first page only, so later pages were skipped | LASERC Ikeja, 37 of 333 rows read | Read from the heading until the next appendix heading | `test_feeder_areas` (row counts) | fixed |
| 31 | The compensation appendix has the same first columns | `COMPENSATE CUSTOMER` rows | Keep only six-cell rows whose band cell is A to E and last cell is hours | `test_feeder_areas` | fixed |
| 32 | OCR repeats the band letter or drops the row number in NERC appendices | KAEDC `11KV NACB  A  DAWAKI ... A  20` | Everything after the feeder name is kept as area text; band letters are taken out wherever they appear | none | fixed |
| 33 | Close-name matching attached the wrong feeder | `NEW GOVERNMENT HOUSE` to `GOVERNMENT HOUSE`; `AGO II` to `AGO I`; `OPEBI` to `OPIC`; `33KV NUMAN` to `11KV NUMAN`; `COMMERCIAL` to `SAGAMU SABO COMMERCIAL` | A close match must reach 0.90 and agree on every number, roman numeral, single letter and word such as NEW; for dashed names the last part must also be similar; names stating different voltages never match; tail matching only for Eko's `..._FEEDER` scheme. Unmatched rows stay searchable by area but are never attached to a feeder | `test_feeder_area_matching` | fixed |
| 34 | Naming schemes that do not match at all | Abuja: `132KV APO TS_33KV FDR H37_S26_K10` against `APO AT3_H37_S26_K10` | Abuja matched on the last three parts of its feeder code | `test_feeder_area_matching` | fixed |

## Downloads

| # | Mistake | Real example | Correction | Guard | Status |
|---|---|---|---|---|---|
| 26 | A cut-off download still starts with `%PDF` and opens, with blank pages where the table is | Five NERC tariff orders and one LASERC order, 2026-10-27 (sizes ending in 961) | `pdf_complete` requires `%%EOF` at the end; `get_pdf` retries with longer timeouts; a truncated file already on disk is downloaded again | `test_truncated_pdf_is_refused`, `test_every_committed_pdf_is_complete` | fixed |
| 27 | Python rejects NERC's incomplete certificate chain | 22 cap orders in October 2026 | Fall back to curl, then curl without verification | refresh health check lists failed downloads | fixed |
| 27a | A search for one DisCo's file name also matched another's, so two addresses went to the downloader and both failed | `BEDC_HOLDCO` also matched `IBEDC_HOLDCO` | Match the whole file name after the slash | none (one-off script) | fixed |
| 28 | A regulator lists a file but its storage refuses it | LASERC Oct 2025 to Jun 2026 (403) | Recorded as `unavailable` in `data/parsed/state_listed.csv` | health check opens an issue for a newly listed month that cannot be downloaded | flagged |
