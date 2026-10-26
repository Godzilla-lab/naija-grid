# Contributing

Thank you for helping keep this dataset accurate. The most useful contribution is a precise report of a row that does not match the NERC PDF.

## Report a parsing error

Every row in `data/nerc_caps_all.csv` carries `source_file` and `source_page`, and every source PDF is committed under `raw/pdfs/`. To report an error:

1. Open the PDF named in `source_file` and go to `source_page`.
2. Open an issue with the **Data error** template and fill in: DisCo, month (YYYY-MM), PDF file name, page, the row exactly as the PDF prints it, and the row as the CSV has it (or "missing").

A feeder that is in the PDF but missing from the CSV is also a data error. Check `data/nerc_caps_unparsed.log` first: lines the parser could not read are listed there with file and page.

## Run the scripts locally

Python 3.10 or newer. Nothing to install as a package; the scripts run as plain files.

```bash
git clone https://github.com/Godzilla-lab/naija-grid.git
cd naija-grid
pip install -r requirements-dev.txt          # pypdf, pyarrow (optional), pytest

python scripts/nerc_caps.py --parse-only raw/pdfs/IE-Monthly-Energy-Cap-September-2026.pdf   # one PDF, no network
python scripts/nerc_caps.py --reparse        # rebuild every CSV from raw/pdfs, no network
python scripts/nerc_caps.py --month 2026-10  # fetch one month from NERC
python scripts/derive.py                     # rebuild data/derived/
python -m pytest -q
```

Network runs wait 1.5 seconds between downloads and never download a PDF that is already on disk with the expected size. Please keep it that way.

## Propose a fix

1. Fork, branch, and change `scripts/nerc_caps.py` (parser) or `scripts/derive.py` (derived tables).
2. Add a test in `tests/` that fails before your change and passes after it, using a PDF from `raw/pdfs/`.
3. Run `python scripts/nerc_caps.py --reparse && python scripts/derive.py && python -m pytest -q`.
4. Open a pull request. Say which months changed and by how many rows; the template asks for this.

Rules for changes:

- `feeder_raw` and `location_raw` stay exactly as printed (whitespace collapsed). Clean-up goes in other columns.
- Never edit files in `data/` by hand. They are outputs of the scripts.
- No em or en dashes in code, docs or data written by this project.

## Code of conduct

This project follows the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md).
