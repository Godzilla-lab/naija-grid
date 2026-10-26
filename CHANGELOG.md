# Changelog

Versions follow [Semantic Versioning](https://semver.org/). A new month of data is not a version change; a change to columns, file layout or parsing that alters existing rows is.

## [0.1.0] - 2026-10-26

First public release.

### Data

- `data/clean/caps_long.csv` and `.parquet`: 145,795 feeder-month records, October 2022 to October 2026, 7,813 feeders linked across months, with quality flags (`state_source`, `extraction_method`, `id_link`).
- `data/clean/feeders.csv` and `data/clean/band_history_wide.csv`: one row per feeder.
- `data/summary/` and `data/rankings/`: monthly summaries by DisCo and state, the like-for-like trend, every band change, state jurisdiction, and latest-month rankings.
- `data/reference/state_regulators.csv`: the 17 NERC transfer orders to state regulators, 15 read from the order PDFs.
- `data/parsed/`: the raw extraction from 519 NERC PDFs, before cleaning, with `sources.csv`.
- `raw/pdfs/` (the orders as downloaded) and `raw/ocr_text/` (recognised text of every scanned page).
- `docs/ANALYSIS.md`: findings, method and limitations, with eight charts in `docs/charts/`.

### Method

- Discovery reads every page of NERC's paginated library search and selects documents by title, so every file naming style from 2022 to 2026 is found.
- Each order's month comes from its own title; two mislabeled files are placed by title.
- Text PDFs are read with pypdf layout mode; 105 scanned orders (November 2025 to August 2026) with Apple Vision, row by row, words placed by the table's ruling lines.
- Feeders are linked across months by a stable form of their name; 592 scanned rows by close-name matching.
- State is printed (21.1 percent), learned from business units (63.4), mapped by hand (13.1) or unknown (2.4).
- 652 rows that NERC printed twice in the same order are removed.

### Known limitations

- 506 scanned records have an unreadable band, marked `?` in `data/parsed/` and excluded from `data/clean/`.
- No orders online for January to September 2022 or September to December 2023; Ikeja December 2022 is a dead link on NERC's site.

### Project

- Refresh on the 1st and 3rd of each month on a macOS runner; tests on every push.
- MIT for code, CC BY 4.0 for data.
