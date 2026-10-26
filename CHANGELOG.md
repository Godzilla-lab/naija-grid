# Changelog

All notable changes to this project are recorded here. Versions follow [Semantic Versioning](https://semver.org/): a new month of data is not a version change; a change to columns, file layout or parsing that alters existing rows is.

## [0.1.0] - 2026-10-26

First public release.

### Data

- `data/nerc_caps_all.csv` and `.parquet`: NERC Monthly Energy Cap orders, one row per feeder per month, {{FIRST_PERIOD}} to {{LATEST_PERIOD}}, {{N_ROWS}} rows from {{N_PDFS_USED}} PDFs.
- `data/nerc_caps_YYYY-MM.csv`: the same rows split by month.
- `data/sources.csv`: every source PDF with NERC URL, SHA-256, pages, bytes, rows parsed and extraction method.
- `data/derived/`: band counts per DisCo per month, band changes between consecutive orders, first and last month each feeder is seen.
- `raw/pdfs/`: the source PDFs, unmodified.
- `datapackage.json`: Frictionless Data descriptor.

### Parser

- Discovery reads every page of NERC's paginated library search and selects documents by title, so all file naming styles from 2022 to 2026 are found.
- The order month comes from the PDF header, not the file name.
- Wrapped rows are joined, including when the second half looks like a row on its own.
- Pages without a text layer are counted in `sources.csv` and sent to OCR when tesseract is installed. None of the published files needed it.
- September 2026 parses to 2,309 feeders across 11 DisCos with no unparsed lines (checked in `tests/`).

### Known limitations

- From 2026, NERC's Ikeja, Eko and Enugu orders cover only feeders outside Lagos and Enugu states (Ogun and Ebonyi), so those DisCos are not comparable across years. The files are text PDFs, not scans.
- {{N_UNPARSED}} unparsed lines, listed in `data/nerc_caps_unparsed.log`.

### Project

- Scheduled refresh on the 1st and 3rd of each month (`.github/workflows/refresh.yml`) and tests on every push (`.github/workflows/ci.yml`).
- Licences: MIT for code, CC BY 4.0 for data.
- Data dictionary, citation file, contributing guide, code of conduct, issue and pull request templates.
