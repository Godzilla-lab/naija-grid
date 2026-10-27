# Changelog

Versions follow [Semantic Versioning](https://semver.org/). A new month of data is not a version change; a change to columns, file layout or parsing that alters existing rows is.

## [Unreleased]

### Added

- Caps set by state regulators: Lagos (LASERC, IE Energy Lagos and Excel feeders) and Enugu (EERC, MainPower), July to October 2026, from `scripts/state_caps.py`; files in `raw/state/`.
- Columns `regulator` and `band_source` in `data/clean/caps_long.csv`; `regulator` and `latest_band_source` in `data/clean/feeders.csv`.
- `data/reference/state_regulators.csv`: whether each state regulator publishes caps, bands and tariffs, and when it was checked.
- `data/summary/state_regulator_caps.csv` and `state_vs_nerc_year_on_year.csv`; `data/qa/state_nerc_overlap.csv`; `data/parsed/state_caps_all.csv`, `state_sources.csv`, `state_listed.csv`.
- The refresh fetches state regulator files each month and reports a newly listed file it could not download.
- The lookup page says who set each cap and where an Enugu band comes from.
- Naira caps: `data/reference/tariffs_non_md.csv` (allowed Non-MD tariffs for all 11 DisCos, LASERC and EERC, each value read from the order; checked pages in `raw/tariff_pages/`) and columns `tariff_naira_per_kwh`, `max_bill_naira` (cap x tariff x 1.075 VAT) and `tariff_source` in `caps_long`; `latest_tariff_naira_per_kwh` and `latest_max_bill_naira` in `feeders`; `data/summary/max_bill_by_disco_band_latest.csv`.
- Feeder to area: `data/reference/feeder_areas.csv`, each feeder's location and major streets from the September 2026 tariff orders (`scripts/feeder_areas.py`), linked to feeder ids only where the match is safe. The lookup page searches streets and shows the naira maximum.
- `docs/KNOWN_EXTRACTION_ERRORS.md`: every extraction mistake found so far, its correction and the test that guards it.

### Fixed

- Three Port Harcourt orders (December 2025, March and April 2026) had never been extracted: one row with no readable name crashed the reader and the whole order was dropped. They are now in the data (523 orders, was 520), and any failed order in any month fails the tests and opens an issue.
- Downloads are checked for a complete PDF (`%%EOF`) and retried; a truncated file on disk is fetched again.
- OCR letter confusions corrected automatically on scanned pages: `lNJ`/`lN` for `INJ` (327 Ikeja rows), `lj` for `Ij`.
- Feeder names that differ only by spaces (`11KV AJI YA` / `11KV AJIYA`) are one feeder; existing ids are kept.
- An Ikeja business unit that wraps onto the next line (`AKOWONJO` / `BU`) is joined back to its row.

### Changed

- Distinct NERC feeders 6,309 (was 6,458) and feeder-month records 147,815 (was 147,079), from the fixes above. Headline findings are unchanged; NERC findings stay NERC-only.

## [0.1.0] - 2026-10-26

First public release.

### Data

- `data/clean/caps_long.csv` and `.parquet`: 147,815 feeder-month records, October 2022 to October 2026, 6,309 feeders linked across months, with quality flags (`state_source`, `extraction_method`, `id_link`).
- `data/clean/feeders.csv` and `data/clean/band_history_wide.csv`: one row per feeder.
- `data/summary/` and `data/rankings/`: monthly summaries by DisCo and state, the like-for-like trend, every band change, state jurisdiction, and latest-month rankings.
- `data/reference/state_regulators.csv`: the 17 NERC transfer orders to state regulators, 15 read from the order PDFs.
- `data/parsed/`: the raw extraction from 520 NERC PDFs, before cleaning, with `sources.csv`.
- `raw/pdfs/` (the orders as downloaded) and `raw/ocr_text/` (recognised text of every scanned page).
- `docs/ANALYSIS.md`: findings, method and limitations, with eight charts in `docs/charts/`.

### Method

- Discovery reads every page of NERC's paginated library search and selects documents by title, so every file naming style from 2022 to 2026 is found.
- Each order's month comes from its own title; two files whose name and title disagree are placed in the month where their DisCo has no other order.
- Text PDFs are read with pypdf layout mode; 108 scanned orders (November 2025 to August 2026) with Apple Vision, row by row, words placed by the table's ruling lines.
- Feeders are linked across months by a stable form of their name; 500 scanned rows by close-name matching.
- State is printed (21.8 percent), learned from business units (68.0), mapped by hand (9.6) or unknown (0.6).
- 645 rows that NERC printed twice in the same order are removed.
- A feeder name that wraps onto the line below its row is joined to that row, not to the next one (7,028 rows corrected).
- Band letters that Apple Vision skips when shown alone (mostly a lone C) are re-read in the context of their whole row; Ikeja's `A - Bilateral` cells are read as Band A. This recovered 488 bands, checked by eye against the scans.

### Known limitations

- 18 scanned records have an unreadable band, marked `?` in `data/parsed/` and excluded from `data/clean/`.
- In some scanned Ikeja orders the injection substation and feeder run together in the name (for example `IlupejuNJ-T4`), as printed by the OCR.
- No orders online for January to September 2022 or September to December 2023; Ikeja December 2022 is a dead link on NERC's site.

### Project

- Refresh on the 1st and 3rd of each month on a macOS runner; tests on every push.
- Mirrored on Kaggle (`godzilla1215/naija-grid`); the refresh pushes a new Kaggle version whenever the data changes.
- A feeder lookup page, `docs/index.html`, served by GitHub Pages.
- MIT for code, CC BY 4.0 for data.
