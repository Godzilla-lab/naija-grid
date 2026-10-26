# naija-grid

Feeder level monthly energy caps and service bands for Nigeria's electricity distribution companies, parsed from the Nigerian Electricity Regulatory Commission (NERC) monthly orders, {{FIRST_PERIOD}} to {{LATEST_PERIOD}}.

[![Code licence: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data licence: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](data/LICENSE)
[![refresh](https://github.com/Godzilla-lab/naija-grid/actions/workflows/refresh.yml/badge.svg)](https://github.com/Godzilla-lab/naija-grid/actions/workflows/refresh.yml)
[![ci](https://github.com/Godzilla-lab/naija-grid/actions/workflows/ci.yml/badge.svg)](https://github.com/Godzilla-lab/naija-grid/actions/workflows/ci.yml)
[![Months covered](https://img.shields.io/badge/months-{{N_MONTHS}}-informational.svg)](data/)
[![Feeder rows](https://img.shields.io/badge/feeder%20rows-{{N_ROWS_BADGE}}-informational.svg)](data/nerc_caps_all.csv)

<!-- MAINTAINER: every {{PLACEHOLDER}} in this file must be filled from the published data
     (data/nerc_caps_all.csv, data/sources.csv, data/derived/band_counts_by_disco_month.csv)
     before release. grep -n '{{' README.md must return nothing. -->

## What this is

Every month NERC publishes one PDF per distribution company (DisCo) listing, for each feeder, its service band (A to E) and its monthly energy cap in kWh, the most an unmetered customer on that feeder can be billed for the month. This repository downloads those PDFs, keeps them unmodified as provenance, and turns them into one table with a row per feeder per month. A scheduled job adds each new month as NERC publishes it.

## Quick start

Download the full table:

```bash
curl -LO https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/nerc_caps_all.csv
```

Load it in pandas:

```python
import pandas as pd

url = "https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/nerc_caps_all.csv"
caps = pd.read_csv(url, dtype=str).astype({"cap_kwh": int})
latest = caps[caps.period == caps.period.max()]
print(latest.groupby(["disco", "service_band"]).size().unstack(fill_value=0))
```

Band A feeders per DisCo in the latest month, with DuckDB straight from GitHub:

```bash
duckdb -c "WITH c AS (SELECT * FROM read_csv_auto('https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/nerc_caps_all.csv', all_varchar=true)) SELECT disco, count(*) AS band_a_feeders FROM c WHERE service_band = 'A' AND period = (SELECT max(period) FROM c) GROUP BY disco ORDER BY band_a_feeders DESC"
```

## Headline numbers

Band A feeders per DisCo, {{LATEST_PERIOD}} against {{YEAR_EARLIER_PERIOD}}. Source: `data/derived/band_counts_by_disco_month.csv`.

| DisCo | {{YEAR_EARLIER_PERIOD}} | {{LATEST_PERIOD}} | Change |
|---|---:|---:|---:|
| AEDC (Abuja) | {{AEDC_PREV}} | {{AEDC_NOW}} | {{AEDC_DELTA}} |
| APLE (Aba Power) | {{APLE_PREV}} | {{APLE_NOW}} | {{APLE_DELTA}} |
| BEDC (Benin) | {{BEDC_PREV}} | {{BEDC_NOW}} | {{BEDC_DELTA}} |
| EEDC (Enugu) | {{EEDC_PREV}} | {{EEDC_NOW}} | {{EEDC_DELTA}} |
| EKEDC (Eko) | {{EKEDC_PREV}} | {{EKEDC_NOW}} | {{EKEDC_DELTA}} |
| IBEDC (Ibadan) | {{IBEDC_PREV}} | {{IBEDC_NOW}} | {{IBEDC_DELTA}} |
| IKEDC (Ikeja) | {{IKEDC_PREV}} | {{IKEDC_NOW}} | {{IKEDC_DELTA}} |
| JEDC (Jos) | {{JEDC_PREV}} | {{JEDC_NOW}} | {{JEDC_DELTA}} |
| KAEDC (Kaduna) | {{KAEDC_PREV}} | {{KAEDC_NOW}} | {{KAEDC_DELTA}} |
| KEDCO (Kano) | {{KEDCO_PREV}} | {{KEDCO_NOW}} | {{KEDCO_DELTA}} |
| PHED (Port Harcourt) | {{PHED_PREV}} | {{PHED_NOW}} | {{PHED_DELTA}} |
| YEDC (Yola) | {{YEDC_PREV}} | {{YEDC_NOW}} | {{YEDC_DELTA}} |
| **All** | {{ALL_PREV}} | {{ALL_NOW}} | {{ALL_DELTA}} |

The Ikeja, Eko and Enugu rows are not comparable across years. See [Known limitations](#known-limitations).

### Why this matters

NERC reports 4.8 million unmetered electricity customers at June 2026 and 708,699 customer complaints to DisCos in 2025. <!-- MAINTAINER: link the NERC report for each figure. --> For an unmetered customer, the energy cap on their feeder is the legal maximum they can be billed for the month, so the published cap is the figure to check an estimated bill against. The band matters too: a Band A feeder carries a commitment of 20 hours of supply a day. A feeder by feeder history shows which feeders moved into or out of Band A, and when.

## Data

| File | What it holds |
|---|---|
| `data/nerc_caps_all.csv` | Every feeder, every month. One row per feeder per order. |
| `data/nerc_caps_all.parquet` | The same table as Parquet. |
| `data/nerc_caps_YYYY-MM.csv` | One file per month. |
| `data/sources.csv` | One row per source PDF: URL, SHA-256, pages, bytes, rows parsed, extraction method. |
| `data/derived/band_counts_by_disco_month.csv` | Feeders per band, per DisCo, per month. |
| `data/derived/band_changes.csv` | Feeders whose band changed between two consecutive orders of the same DisCo. |
| `data/derived/feeder_first_last_seen.csv` | First and last month each feeder appears. |
| `data/nerc_caps_unparsed.log` | Lines in the PDFs that the parser could not read as a row. |
| `raw/pdfs/` | The NERC PDFs exactly as downloaded. |
| `datapackage.json` | Frictionless Data descriptor for the main table and the sources table. |

Every column, its type, an example and how it is derived: [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).

## How it is built

1. **Discovery.** NERC's document library search (`https://nerc.gov.ng/resources/?doc_term=monthly+energy+cap+<year>&ins=1`) returns 12 results per page, paginated as `/resources/page/<n>/?doc_term=...`. Every page is read, and each result's title and PDF link are kept. NERC's file names change style from year to year, so documents are selected by their listed title, not by file name.
2. **Download.** Each PDF is saved under `raw/pdfs/`, with 1.5 seconds between downloads. A PDF already on disk with the expected size is never downloaded again.
3. **Parse.** `scripts/nerc_caps.py` reads the text layer of each page with pypdf and matches rows of the form `location, band, cap`. Rows that wrap onto two lines are joined. The order month is read from the PDF header ("Monthly Energy Cap (September 2026)").
4. **Provenance.** Every row carries `source_file`, `source_page` and the first 16 characters of the PDF's SHA-256. `data/sources.csv` gives the full SHA-256 and the NERC URL of each file, so any row can be traced to a page of an official document.
5. **Derive.** `scripts/derive.py` builds the tables in `data/derived/`. Feeders are matched across months on `(disco, feeder_key)`.
6. **Refresh.** `.github/workflows/refresh.yml` runs at 07:00 UTC on the 1st and 3rd of every month (and on demand), fetches the new orders, rebuilds the derived tables, and commits `data: NERC caps <YYYY-MM>` if anything changed.

Run it yourself (Python 3.10 or newer, no package install needed):

```bash
pip install -r requirements.txt
python scripts/nerc_caps.py --month 2026-10              # one month
python scripts/nerc_caps.py --from 2022-01 --to 2026-10  # back-fill
python scripts/derive.py
python -m pytest -q
```

The methodology behind the caps is NERC Order NERC/307/2022 on the determination of monthly energy caps for unmetered customers: a feeder's cap is derived from metered consumption on the same feeder.

## Known limitations

- **Short 2026 orders for Ikeja, Eko and Enugu.** In 2026 the NERC orders for Ikeja (IKEDC), Eko (EKEDC) and Enugu (EEDC) list far fewer feeders: 34, 17 and 17 in September 2026, against {{IKEDC_2025_09}}, {{EKEDC_2025_09}} and {{EEDC_2025_09}} in September 2025. The files are not scanned. Every page has a full text layer, and the only image on each page is a 100 by 55 pixel logo, so OCR adds nothing. The orders are short by content: the September 2026 Ikeja order covers only Ogun state (Abule-Egba business unit), Eko only Ogun state (Agbara), and Enugu only Ebonyi state (Abakaliki). Feeders inside Lagos and Enugu states are no longer in NERC's orders. This fits the move of those state electricity markets from NERC to state regulators under the Electricity Act 2023, but we have not found a NERC notice that says so, and caps for those feeders would have to come from the state regulators. The first short month is {{SHORT_FROM_PERIOD}}. Page counts per file are in `data/sources.csv`.
- **Unparsed lines.** {{N_UNPARSED}} lines across all PDFs could not be read as rows. They are listed in `data/nerc_caps_unparsed.log` with file and page.
- **Feeder matching across layout changes is approximate.** NERC changed the table layout several times (a STATE column, business unit names, feeder naming). `feeder_key` matches the same feeder across months within one layout, but a feeder can get a new key when the layout changes. `band_changes.csv` compares consecutive orders only and skips keys that appear twice in one order.
- **Repeated rows.** Some orders print the same feeder twice, sometimes with identical values. Rows are kept as printed.
- **Business unit and state are best effort.** They are split from free text. `location_raw` always holds the printed text.
- **Misdated files.** At least one NERC file name disagrees with its content (a Kano file named January 2024 is the January 2025 order). The PDF header decides the month; `data/sources.csv` records where each month came from.
- **Missing months.** Months where NERC published no order for a DisCo have no rows for it. Coverage per DisCo and month is in `data/derived/band_counts_by_disco_month.csv`.

## Citation

If you use this data, please cite it. GitHub shows a "Cite this repository" button generated from [CITATION.cff](CITATION.cff).

> Busari, O. (2026). naija-grid: NERC monthly energy caps for Nigeria, by feeder (Version 0.1.0) [Data set]. https://github.com/Godzilla-lab/naija-grid. Source: Nigerian Electricity Regulatory Commission.

## Licence

- Code (`scripts/`, `tests/`, workflows): [MIT](LICENSE).
- Data (`data/`): [CC BY 4.0](data/LICENSE). Attribute as "naija-grid, from NERC Monthly Energy Cap orders".
- The PDFs in `raw/pdfs/` are public documents of the Nigerian Electricity Regulatory Commission, kept unmodified as provenance.

## Contributing

Found a row that does not match its PDF? Open a [data error issue](https://github.com/Godzilla-lab/naija-grid/issues/new?template=data_error.yml) with the PDF name and page. [CONTRIBUTING.md](CONTRIBUTING.md) covers running the scripts and proposing fixes. This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Related

- [t.me/naijagridbot](https://t.me/naijagridbot): a Telegram bot that serves the same data.

## Acknowledgements

All data comes from the [Nigerian Electricity Regulatory Commission](https://nerc.gov.ng), which publishes the Monthly Energy Cap orders in its document library. This project is independent and is not affiliated with or endorsed by NERC.
