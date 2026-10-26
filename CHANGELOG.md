# Changelog

Versions follow [Semantic Versioning](https://semver.org/). A new month of data is not a version change; a change to columns, file layout or parsing that alters existing rows is.

## [0.1.0] - 2026-10-26

First public release.

### Data

- `data/clean/caps_long.csv` and `.parquet`: 147,079 feeder-month records, October 2022 to October 2026, 6,458 feeders linked across months, with quality flags (`state_source`, `extraction_method`, `id_link`).
- `data/clean/feeders.csv` and `data/clean/band_history_wide.csv`: one row per feeder.
- `data/summary/` and `data/rankings/`: monthly summaries by DisCo and state, the like-for-like trend, every band change, state jurisdiction, and latest-month rankings.
- `data/reference/state_regulators.csv`: the 17 NERC transfer orders to state regulators, 15 read from the order PDFs.
- `data/parsed/`: the raw extraction from 520 NERC PDFs, before cleaning, with `sources.csv`.
- `raw/pdfs/` (the orders as downloaded) and `raw/ocr_text/` (recognised text of every scanned page).
- `docs/ANALYSIS.md`: findings, method and limitations, with eight charts in `docs/charts/`.

### Method

- Discovery reads every page of NERC's paginated library search and selects documents by title, so every file naming style from 2022 to 2026 is found.
- Each order's month comes from its own title; two files whose name and title disagree are placed in the month where their DisCo has no other order.
- Text PDFs are read with pypdf layout mode; 105 scanned orders (November 2025 to August 2026) with Apple Vision, row by row, words placed by the table's ruling lines.
- Feeders are linked across months by a stable form of their name; 741 scanned rows by close-name matching.
- State is printed (21.4 percent), learned from business units (68.3), mapped by hand (9.7) or unknown (0.6).
- 634 rows that NERC printed twice in the same order are removed.
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
