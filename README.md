# naija-grid

Open data on Nigeria's electricity distribution grid: every feeder's service band and its legal monthly billing cap for unmetered customers, from every NERC Monthly Energy Cap order published online, October 2022 to October 2026, with analysis.

![code: MIT](https://img.shields.io/badge/code-MIT-blue) ![data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green) ![months: 45](https://img.shields.io/badge/months-45-informational) ![feeders: 7,813](https://img.shields.io/badge/feeders-7%2C813-informational) [![refresh](https://github.com/Godzilla-lab/naija-grid/actions/workflows/refresh.yml/badge.svg)](https://github.com/Godzilla-lab/naija-grid/actions/workflows/refresh.yml)

## What this is

The Nigerian Electricity Regulatory Commission (NERC) publishes a monthly order for each distribution company (DisCo) that lists every feeder with unmetered customers, its service band (A to E, where Band A promises at least 20 hours of supply a day) and the most kWh an unmetered customer on that feeder may be billed that month. NERC publishes these as PDFs, eleven or twelve a month, some of them scanned. This repository turns all of them into clean tables that link each feeder across time, and analyses what they show.

| | |
|---|---|
| Source orders | 520 PDFs, all 11 DisCos plus Aba Power |
| Months | 45, October 2022 to October 2026 |
| Feeder-month records | 146,108 |
| Distinct feeders | 7,813 |
| Feeders in the October 2026 orders | 2,296 |

## Headline findings

Full report with charts: **[docs/ANALYSIS.md](docs/ANALYSIS.md)**.

1. **July 2024 was the biggest re-banding on record.** 747 feeders changed band in one month. Band A's share of feeders fell from 30.1 to 24.1 percent, mostly through moves from A to B.
2. **Caps per unmetered customer rose about 29 percent** in four years, from a median of 159 kWh (October 2022) to 204.5 kWh (October 2026).
3. **Bands D and E have the same median cap** (176 and 176.5 kWh), and 102 Band D or E feeders have a cap above their own DisCo's Band A median.
4. **Abuja has the most Band A feeders (51.5 percent); Benin the fewest (7.0 percent).** Kaduna is the most split, with 29 percent of feeders in Band A and 30.5 percent in Band E.
5. **Seventeen states have taken over electricity regulation from NERC.** Eleven have dropped out of NERC's cap orders, each months after its transfer deadline. Six are still listed after theirs, including Oyo, Edo and Ogun.

| DisCo (October 2026 order) | Feeders | Band A | Band E | Median cap (kWh) |
|---|---:|---:|---:|---:|
| Abuja | 635 | 51.5% | 0.0% | 260 |
| Enugu (Ebonyi only) | 17 | 41.2% | 0.0% | 127 |
| Port Harcourt | 236 | 31.4% | 7.2% | 390 |
| Kaduna | 200 | 29.0% | 30.5% | 121.5 |
| Jos | 98 | 28.6% | 6.1% | 126.5 |
| Ikeja (Ogun only) | 34 | 17.6% | 0.0% | 362 |
| Eko (Ogun only) | 17 | 17.6% | 0.0% | 289 |
| Yola | 149 | 17.4% | 0.0% | 139 |
| Ibadan | 509 | 16.1% | 21.8% | 192 |
| Kano | 158 | 10.1% | 4.4% | 176 |
| Benin | 243 | 7.0% | 23.0% | 300 |

## Quick start

Download the main table:

```bash
curl -LO https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/clean/caps_long.csv
```

Load it in pandas and get the latest band mix by DisCo:

```python
import pandas as pd
df = pd.read_csv("https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/clean/caps_long.csv")
latest = df[df.order_month == df.order_month.max()]
print(latest.groupby("disco_name").band.value_counts(normalize=True).unstack().round(3))
```

Query it with DuckDB without downloading anything:

```sql
SELECT disco_name, count(*) AS feeders,
       round(100 * avg(CASE WHEN band = 'A' THEN 1 ELSE 0 END), 1) AS band_a_pct
FROM 'https://raw.githubusercontent.com/Godzilla-lab/naija-grid/main/data/clean/caps_long.csv'
WHERE order_month = '2026-10'
GROUP BY 1 ORDER BY 3 DESC;
```

Look up one feeder over time: open `data/clean/band_history_wide.csv` in Excel or Google Sheets and search for its name.

## Data

| Path | Contents |
|---|---|
| `data/clean/caps_long.csv` (+ `.parquet`) | **Main table.** One row per feeder per month: feeder id, DisCo, state, order month, consumption month, band, cap |
| `data/clean/feeders.csv` | One row per feeder: name, business unit, first and last month listed, latest band and cap, best and worst band, number of band changes |
| `data/clean/band_history_wide.csv` | Feeders down, months across, band letters |
| `data/summary/` | Coverage by month; band mix and caps by DisCo and by state per month; the like-for-like trend; every band change; state jurisdiction |
| `data/rankings/` | Latest-month rankings, highest to lowest: DisCos and states by Band A share, highest and lowest caps, low-band feeders with high caps, most volatile feeders, DisCos by downgrades |
| `data/reference/state_regulators.csv` | The 17 NERC transfer orders to state regulators: order number, dates, status, successor company, sources |
| `data/reference/bu_state_manual.csv` | Hand-made map from business unit to state for older orders without a state column |
| `data/parsed/` | Raw extraction, one CSV per month, before cleaning; `sources.csv` lists every PDF with its hash and extraction method |
| `data/findings.json` | Every number quoted in the analysis |
| `raw/pdfs/` | The NERC orders as downloaded |
| `raw/ocr_text/` | Recognised text of every scanned page |

Column definitions: [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).

The order for month M caps energy consumed in month M minus 1; both are in the main table (`order_month`, `consumption_month`).

## How it is built

1. `scripts/nerc_caps.py` finds each month's orders in NERC's document library and downloads them.
2. `scripts/reparse.py` extracts every table: text PDFs with pypdf in layout mode; scanned PDFs (November 2025 to August 2026) with Apple Vision OCR via `scripts/ocr_vision.py`, one table row at a time. Each order's month comes from its own title, or its file name when the two disagree in a way the data resolves.
3. `scripts/analyze.py` cleans, links feeders across months, infers state for older orders, builds the tables and rankings, and draws the charts.

### Automatic updates

A GitHub Action runs on the 1st and 3rd of every month on a macOS runner and needs no one at a keyboard:

1. **OCR self-test.** Reads a known scanned page from scratch and checks four known rows, so a broken OCR setup stops the run before any data is touched.
2. **Download.** Finds the current and previous month's orders by title in NERC's library and downloads them. PDFs, JPG or PNG images and ZIP bundles are all accepted; images are wrapped as PDFs and read by OCR. If Python's downloader rejects NERC's certificate chain, it falls back to curl.
3. **Extract, rebuild, test.** Text pages are read directly, scanned pages and images by OCR; the clean tables, rankings, charts and findings are rebuilt and the tests run.
4. **Commit.** New data is committed. `data/last_checked.json` changes on every run, which also stops GitHub from switching off the schedule after 60 quiet days.
5. **Alert.** A health check opens a GitHub issue (which emails the repository owner) if a download failed, an order produced 0 rows, a DisCo's feeder count fell by more than 40 percent or vanished, or more than 10 percent of bands could not be read. A failed run also opens an issue.

The Telegram bot reloads `data/clean/feeders.csv` every morning, so it follows the repository within a day.

```bash
pip install -r requirements.txt          # macOS also needs requirements-ocr.txt for scanned orders
python scripts/nerc_caps.py --month 2026-10
python scripts/reparse.py --only 2026-10
python scripts/analyze.py
python -m pytest -q
```

## Known limitations

- Scanned months (November 2025 to August 2026) are less certain: 506 records have an unreadable band (`?`), and feeder linking is 79 to 92 percent month to month against 93 to 98 percent for text months.
- A state appearing in NERC's orders is what NERC published, not a statement of who legally regulates it.
- A cap is the legal maximum bill for an unmetered customer, not an actual bill.
- NERC has not put January to September 2022 or September to December 2023 online. Ikeja's December 2022 order is a dead link on NERC's site.

Details in [docs/ANALYSIS.md](docs/ANALYSIS.md#limitations).

## Related

[@naijagridbot](https://t.me/naijagridbot) on Telegram looks up a feeder's latest band and cap from this data.

## Citation

See [CITATION.cff](CITATION.cff). Suggested: *Busari, O. (2026). naija-grid: NERC monthly energy caps and service bands for every Nigerian feeder, 2022 to 2026. https://github.com/Godzilla-lab/naija-grid*

## Licence

Code: MIT ([LICENSE](LICENSE)). Data: CC BY 4.0 ([data/LICENSE](data/LICENSE)). Source documents are published by NERC; credit NERC as the original source.

## Contributing

Found a wrong row? Open a [data error issue](../../issues/new?template=data_error.yml) with the DisCo, month, PDF name and page. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgements

All source data is published by the [Nigerian Electricity Regulatory Commission](https://nerc.gov.ng).
