# Data dictionary

All files are UTF-8 CSV with a header row. Empty string means "not printed in the source" or "could not be split from the source text". Text columns keep the case NERC used. Examples are real values from the September 2026 orders.

DisCo codes used throughout: `AEDC` Abuja, `APLE` Aba Power, `BEDC` Benin, `EEDC` Enugu, `EKEDC` Eko, `IBEDC` Ibadan, `IKEDC` Ikeja, `JEDC` Jos, `KAEDC` Kaduna, `KEDCO` Kano, `PHED` Port Harcourt, `YEDC` Yola. NERC's own file names use other spellings (IE, EKEDP, JED, Ikeja, Eko, APL and more); they are mapped to these codes.

## data/nerc_caps_all.csv and data/nerc_caps_YYYY-MM.csv

One row per feeder line printed in a NERC Monthly Energy Cap order. The monthly files are the same table split by `period`; `nerc_caps_all.csv` is their concatenation. `nerc_caps_all.parquet` holds the same rows with `year`, `month`, `cap_kwh` and `source_page` as integers.

| Column | Type | Example | Meaning | How it is derived |
|---|---|---|---|---|
| `disco` | string | `IKEDC` | Distribution company. | Mapped from the start of the PDF file name, or the listing title, using the code table above. |
| `year` | integer | `2026` | Year of the order. | From the PDF header, e.g. "Monthly Energy Cap (September 2026)". |
| `month` | integer | `9` | Month of the order, 1 to 12. This is the month the cap applies to, not the consumption month (usually the month before). | As `year`. |
| `period` | string | `2026-09` | `year` and `month` as YYYY-MM. | Formatted from `year` and `month`. |
| `state` | string | `OGUN` | State the feeder is in. | Leading state name of the row, only in orders that print a STATE column. Empty otherwise. |
| `business_unit` | string | `ABULE-EGBA BU` | DisCo business unit or area office. | Text up to and including "BU", or the text before a voltage prefix such as `11-` or `11kV-`. Empty when it cannot be split reliably. |
| `voltage_kv` | string | `11` | Feeder voltage, 11 or 33 kV. | From a `11-`, `33kV-` or `11KV` pattern in the feeder text. Empty when not printed. |
| `injection_substation` | string | `Abule Iroko` | Injection substation. | Ikeja style names only (`11-<substation>INJ-T1-<feeder>`). |
| `transformer` | string | `T1` | Injection substation transformer. | Ikeja style names only. |
| `feeder_name` | string | `Abule Iroko` | Feeder name with state, business unit and voltage prefixes removed. | Best effort split of `feeder_raw`. |
| `feeder_raw` | string | `11-Abule IrokoINJ-T1-Abule Iroko` | Feeder text exactly as printed, after the state and business unit. | Whitespace collapsed to single spaces, nothing else changed. |
| `location_raw` | string | `OGUN ABULE-EGBA BU 11-Abule IrokoINJ-T1-Abule Iroko` | Everything printed before the band column. | Whitespace collapsed. Rows that wrap onto two lines are joined with a space. |
| `feeder_key` | string | `ABULE EGBA BU 11 ABULE IROKOINJ T1 ABULE IROKO` | Key for following one feeder across months. | `location_raw` without the state, uppercased, every character other than letters, digits, spaces and `/` replaced by a space, whitespace collapsed. Use together with `disco`. |
| `service_band` | string | `C` | NERC service band, `A` to `E`. Band A carries a 20 hour daily supply commitment. | As printed. |
| `cap_kwh` | integer | `226` | Monthly energy cap for an unmetered non-maximum-demand customer on this feeder, in kWh. | As printed, thousands separators removed. |
| `extraction_method` | string | `text` | How the row was read: `text` (PDF text layer) or `ocr`. | `ocr` only for pages with no text layer. No published row uses OCR so far. |
| `source_file` | string | `IE-Monthly-Energy-Cap-September-2026.pdf` | PDF in `raw/pdfs/` the row came from. | NERC file name with runs of spaces replaced by `-`. |
| `source_page` | integer | `1` | Page of `source_file`, starting at 1. | Page the row's last line was read from. |
| `source_sha16` | string | `83accdacd39277dc` | First 16 hex characters of the SHA-256 of `source_file`. | Full hash in `data/sources.csv`. |

## data/sources.csv

One row per PDF found in NERC's document library.

| Column | Type | Example | Meaning | How it is derived |
|---|---|---|---|---|
| `disco` | string | `IKEDC` | Distribution company. | As in the main table. |
| `year` | integer | `2026` | Year of the order. | PDF header, else listing title, else file name. |
| `month` | integer | `9` | Month of the order. | As `year`. |
| `period` | string | `2026-09` | YYYY-MM. | From `year` and `month`. |
| `period_from` | string | `pdf_header` | Where the month came from: `pdf_header`, `title` or `filename`. | Recorded by the parser. |
| `status` | string | `used` | `used` (rows are in the main table), `duplicate` (another file for the same DisCo and month was kept), `no_rows` (no rows could be read). | When NERC posts two files for one DisCo and month, the later upload is kept. |
| `url` | string | `https://nerc.gov.ng/wp-content/uploads/2026/09/IE-Monthly-Energy-Cap-September-2026.pdf` | Where the PDF was downloaded from. | From the library listing. |
| `filename` | string | `IE-Monthly-Energy-Cap-September-2026.pdf` | File name in `raw/pdfs/`. | As `source_file`. |
| `title` | string | `IE Monthly Energy Cap September 2026` | Document title in NERC's library. | From the listing card. |
| `published` | string | `September 1, 2026` | Date shown in NERC's library. | From the listing card, as printed. |
| `sha256` | string | 64 hex characters | SHA-256 of the PDF. | Computed on the downloaded bytes. |
| `pages` | integer | `2` | Pages in the PDF. | pypdf page count. |
| `bytes` | integer | `182766` | File size. | Size on disk. |
| `feeders_parsed` | integer | `34` | Rows read from this PDF. | Count of parsed rows. |
| `extraction_method` | string | `text` | `text`, `ocr`, or `ocr+text` for a mix. | Methods used by the rows of this file. |
| `text_pages` | integer | `2` | Pages with a text layer. | pypdf extraction not empty. |
| `image_only_pages` | integer | `0` | Pages with no table text and a large embedded image (a scan). | Images narrower than 400 px, such as logos, are ignored. |
| `unparsed_lines` | integer | `0` | Lines in this PDF that could not be read as a row. | Listed in `data/nerc_caps_unparsed.log`. |

## data/derived/band_counts_by_disco_month.csv

| Column | Type | Example | Meaning | How it is derived |
|---|---|---|---|---|
| `period` | string | `2026-09` | Order month. | From the main table. |
| `disco` | string | `AEDC` | Distribution company. | From the main table. |
| `band_A` | integer | `331` | Rows in Band A. | Count of rows. |
| `band_B` | integer | `168` | Rows in Band B. | Count of rows. |
| `band_C` | integer | `79` | Rows in Band C. | Count of rows. |
| `band_D` | integer | `64` | Rows in Band D. | Count of rows. |
| `band_E` | integer | `0` | Rows in Band E. | Count of rows. |
| `total` | integer | `642` | All rows for this DisCo and month. | Sum of the band counts. |
| `band_a_share` | number | `0.5156` | Share of rows in Band A. | `band_A / total`, four decimals. |

Counts are rows as printed, so a feeder printed twice is counted twice.

## data/derived/band_changes.csv

One row per feeder whose band differs between two consecutive published orders of the same DisCo. "Consecutive" means consecutive among the months for which that DisCo has an order, so a gap month is skipped over.

| Column | Type | Example | Meaning | How it is derived |
|---|---|---|---|---|
| `disco` | string | `AEDC` | Distribution company. | Main table. |
| `feeder_key` | string | `GARKI AT3 H2 G4 7B` | Feeder match key. | Main table. Keys printed more than once in either order are skipped. |
| `business_unit` | string | `GARKI` | Business unit in the later order. | Main table. |
| `feeder_raw` | string | `AT3_H2_G4_7B` | Feeder text in the later order. | Main table. |
| `from_period` | string | `2026-08` | Earlier order. | Main table. |
| `to_period` | string | `2026-09` | Later order. | Main table. |
| `from_band` | string | `B` | Band in the earlier order. | Main table. |
| `to_band` | string | `A` | Band in the later order. | Main table. |
| `direction` | string | `up` | `up` means towards Band A, `down` towards Band E. | Compares the band letters. |
| `from_cap_kwh` | integer | `237` | Cap in the earlier order. | Main table. |
| `to_cap_kwh` | integer | `451` | Cap in the later order. | Main table. |

## data/derived/feeder_first_last_seen.csv

One row per `(disco, feeder_key)`.

| Column | Type | Example | Meaning | How it is derived |
|---|---|---|---|---|
| `disco` | string | `IKEDC` | Distribution company. | Main table. |
| `feeder_key` | string | `ABULE EGBA BU 11 YIDIINJ T1 IJOKO` | Feeder match key. | Main table. |
| `business_unit` | string | `ABULE-EGBA BU` | Business unit in the latest order. | Main table. |
| `feeder_raw` | string | `11-YidiINJ-T1-Ijoko` | Feeder text in the latest order. | Main table. |
| `first_seen` | string | `2026-09` | First order the key appears in. | Minimum `period`. |
| `last_seen` | string | `2026-09` | Last order the key appears in. | Maximum `period`. |
| `months_seen` | integer | `1` | Number of orders the key appears in. | Distinct `period` values. |
| `first_band` | string | `D` | Band in the first order. | Main table. |
| `last_band` | string | `D` | Band in the latest order. | Main table. |
| `last_cap_kwh` | integer | `217` | Cap in the latest order. | Main table. |

## data/nerc_caps_unparsed.log

Plain text, one line per PDF line that could not be read as a row: `<file>:p<page>: <text>`.

<!-- MAINTAINER: the band_changes examples are illustrative (no band change exists in a single month); replace them with a real row after the back-fill. -->
