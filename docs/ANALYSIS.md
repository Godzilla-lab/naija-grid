# What four years of NERC energy cap orders show

Analysis of every Monthly Energy Cap order the Nigerian Electricity Regulatory Commission (NERC) has published online, October 2022 to October 2026. Every number below is computed by `scripts/analyze.py` from the tables in `data/`, and is stored in `data/findings.json`.

## The data in one paragraph

Since 2022, NERC has published a monthly order for each distribution company (DisCo) that lists every feeder with unmetered customers, the feeder's service band (A to E), and the maximum kWh a DisCo may bill an unmetered customer on that feeder that month (Order NERC/307/2022). Band A carries a promise of at least 20 hours of supply a day; bands B to E promise progressively fewer. We collected 520 of these orders, extracted 146,108 feeder-month records covering 7,813 distinct feeders across 45 months, and linked each feeder across time.

| | |
|---|---|
| Orders (PDFs) | 520, all 11 DisCos plus Aba Power |
| Months covered | 45, October 2022 to October 2026 |
| Feeder-month records | 146,108 |
| Distinct feeders | 7,813 |
| Feeders in the latest order (October 2026) | 2,296 |
| State identified | 97.6 percent of records |

---

## Key findings

### 1. The biggest re-banding happened in July 2024

The July 2024 orders changed the band of 747 feeders in a single month, 442 upgrades and 305 downgrades. No other month comes close: the next largest are February 2023 (194 changes) and February 2025 (166).

The most common single move was Band A to Band B (185 feeders). Among the states that are still in NERC's orders today, the share of feeders in Band A fell from 30.1 percent in June 2024 to 24.1 percent in July 2024, while Band B rose from 12.2 to 18.8 percent. This followed NERC's April 2024 decision to charge Band A customers a much higher tariff than other bands, which put the 20-hour promise under scrutiny. Band A has since recovered to 28.0 percent.

Over the whole record, 628 feeders moved into Band A and 529 moved out of it.

![Band changes per month](charts/05_band_changes_by_month.png)

### 2. Caps per unmetered customer have risen by about 29 percent

The median monthly cap, for states that are in the orders at both ends of the period, rose from 159 kWh in October 2022 to 204.5 kWh in October 2026. For Band A feeders it rose from 232 to 289 kWh; for Band E from 144.5 to 176.5 kWh. Because caps are derived from what metered neighbours on the same feeder actually consume, a higher cap means either more supply or more consumption on that feeder, and a higher maximum bill for unmetered households.

![Median cap by band over time](charts/08_median_cap_by_band_over_time.png)

### 3. Caps follow bands at the top, but not at the bottom

In the October 2026 orders the median cap is 289 kWh for Band A, 204 for B, 189 for C, 176 for D and 176.5 for E. Band A is clearly higher, but Bands D and E are indistinguishable. A band is a promise of hours; a cap is a measure of consumption. The two diverge at the bottom.

102 feeders in Bands D or E have a cap above their own DisCo's Band A median. Ibadan (37), Kaduna (25) and Port Harcourt (22) account for most of them; the highest is a Band D feeder in Delta (Benin DisCo) capped at 908 kWh, nearly double Benin's Band A median of 478 kWh. These are the feeders where a low supply promise sits next to a high billing ceiling, and they are listed in `data/rankings/anomaly_low_band_high_cap_latest.csv`.

![Cap by band](charts/04_cap_by_band_latest.png)

### 4. Abuja has the most Band A feeders; Benin and Kano the fewest

Share of each DisCo's listed feeders in Band A, October 2026 order, highest to lowest:

| DisCo | Feeders listed | Band A | Band E | Median cap (kWh) |
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

Kaduna is the most polarised: 29 percent of its feeders in Band A and 30.5 percent in Band E. It also re-banded 107 feeders in the October 2026 order alone (74 down, 33 up). Yola has the worst net record over four years, with 123 downgrades against 38 upgrades.

![DisCo band mix](charts/03_discos_band_mix_latest.png)

By state (at least 10 feeders listed), the FCT leads with 53 percent of feeders in Band A. Katsina has none, Edo 4 percent, Kwara 7 percent, and Delta, Yobe and Jigawa about 9 percent.

![States ranked by Band A share](charts/07_states_band_A_ranking.png)

### 5. Seventeen states have taken over regulation; NERC's orders track it unevenly

Under the Electricity Act 2023, NERC has issued transfer orders to 17 states (table in `data/reference/state_regulators.csv`, with the order number, date and source for each). Comparing those orders with what NERC actually published:

- **Eleven states dropped out of NERC's cap orders, all of them late.** Ekiti, Enugu and Ondo had transfer deadlines in October 2024 but stayed in NERC's orders until September 2025, eleven months later. Imo, Kogi, Niger and Plateau also left in September 2025. Lagos (deadline June 2025) stayed until February 2026, having disappeared in late 2025 and reappeared in January and February 2026. Abia, Bayelsa and Anambra left in February to April 2026.
- **Six transferred states are still in NERC's orders.** Oyo and Edo (deadlines February 2025), Ogun (June 2025), Nasarawa (February 2026) and Gombe (July 2026) are all past their transfer deadlines but still listed in the October 2026 orders. Akwa Ibom is still within its transition period.
- **The Ibadan footprint is shrinking inside the same states.** In the same states, NERC listed 858 Ibadan feeders in October 2025 and 509 in October 2026.

For anyone living in Lagos, Enugu, Imo, Ondo, Ekiti, Kogi, Niger, Plateau, Abia, Bayelsa or Anambra, the federal cap no longer appears in NERC's orders. We found no published caps from the state regulators for those markets.

![State presence by month](charts/06_state_presence.png)

### 6. Some feeders never settle

Some feeders change band again and again. The most volatile is Abuja's Akwanga feeder in Nasarawa (AT7_FDR 1), which changed band 12 times in 43 months, swinging between A and D. Minna's Maikunkele feeder changed 11 times in 31 months. The full list is in `data/rankings/most_volatile_feeders.csv`.

---

## How the data was built

1. **Collection.** NERC's document library was searched year by year and page by page. 22 files that timed out were fetched again; one (Ikeja, December 2022) is a dead link on NERC's own site. NERC has not put January to September 2022 or September to December 2023 online.
2. **Extraction.** 415 orders have a text layer and were read with pypdf in layout mode, which keeps the table columns apart. 105 orders from November 2025 to August 2026 are scanned images; they were read with Apple's Vision text recognition, one table row at a time, placing every word in its column from the table's ruling lines. The recognised text of every scanned page is committed in `raw/ocr_text/` so it can be checked and never needs to be re-run.
3. **Month.** Each order's month is read from its own title, with the file name as fallback. Two files disagree with themselves: a Kano order named January 2024 whose title says January 2025, and an Enugu order named January 2025 whose title still says January 2024 (its caps match December 2024 and February 2025, not early 2024). Each is placed in the month where that DisCo has no other order; both land in January 2025, and the decision is logged in `data/parsed/reparse_qa.log`.
4. **Feeder identity.** A feeder is matched across months by its DisCo and a stable form of its name (voltage tags, "FEEDER", case and punctuation removed), which links the same feeder through renames such as FESTAC 2, AJELE FESTAC 2 and AJELE 33kV-FESTAC 2. Where that stable name would merge two different feeders in the same month, the full printed name, business unit and position in the order are used instead. 592 scanned records were linked to their feeder by close-name matching (similarity at least 0.88) and are flagged `fuzzy_ocr`.
5. **State.** The orders only print a state column from 2025. For earlier orders, state is learned from the business unit using the later orders (63.5 percent of records), or taken from a hand-written map of business units to states (13.0 percent, in `data/reference/bu_state_manual.csv`). 21.0 percent have the state printed; 2.4 percent remain unknown.
6. **Cleaning.** 652 rows that NERC printed twice in the same order were removed.

## Limitations

- **Scanned months are less certain.** For November 2025 to August 2026, 506 records have a band that could not be read and are marked `?`; they are excluded from band statistics. Month-to-month feeder linkage is 93 to 98 percent for text months and 79 to 92 percent for scanned months.
- **Coverage is not jurisdiction.** A state's presence in NERC's orders is what NERC published, not a legal statement of who regulates it.
- **Caps are not bills.** A cap is the legal maximum for an unmetered customer, not what anyone was actually billed. The dataset says nothing about metered customers.
- **Gaps.** No orders for January to September 2022 or September to December 2023 are online; December 2022 lacks Ikeja.
- **Business unit names are as printed.** In older orders, some feeder-name fragments appear in the business unit column; they are kept as printed and flagged where the state could not be inferred.

## Files

| File | What it holds |
|---|---|
| `data/clean/caps_long.csv` | One row per feeder per month: the main table |
| `data/clean/feeders.csv` | One row per feeder: first and last month seen, latest band and cap, best and worst band, number of band changes |
| `data/clean/band_history_wide.csv` | Feeders down, months across, band letters; opens well in Excel |
| `data/summary/` | Coverage by month, DisCo and state by month, the like-for-like trend, every band change, state jurisdiction |
| `data/rankings/` | Latest-month rankings, highest to lowest |
| `data/reference/state_regulators.csv` | The 17 state transfer orders, with sources |
| `data/parsed/` | The raw extraction, one file per month, before cleaning |
| `data/parsed/sources.csv` | Every source PDF with its URL file name, SHA-256, pages, rows and extraction method |
