# Data dictionary

Every column of every published CSV. `data/clean/caps_long.csv` is the main table. Generated from the published files; the tests check that no column is missing here.

## `data/clean/band_history_wide.csv`

| Column | Meaning |
|---|---|
| feeder_id, disco, state, feeder_raw | As in `data/clean/feeders.csv` |
| YYYY-MM (one column per order month) | The feeder's band that month; blank when not listed |

## `data/clean/caps_long.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| feeder_id | text | 00016b03ec5f | Stable id for a feeder across months (12 hex characters). Links the same feeder through renames. |
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| disco_name | text | Abuja | Distribution company short name. |
| state | text | FCT | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| order_month | text | 2023-04 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| consumption_month | text | 2023-03 | Month whose consumption the cap covers: the month before order_month, as stated in each order's title. |
| band | text | A | Service band A to E. A promises at least 20 hours of supply a day; E the least. '?' only in data/parsed, where a scanned band letter could not be read. |
| cap_kwh | number | 150 | Maximum kWh a DisCo may bill an unmetered non-MD customer on this feeder for the month (Order NERC/307/2022). |
| state_source | text | learned | Where state comes from: printed (in the order), learned (from the same business unit in later orders), manual (data/reference/bu_state_manual.csv), unknown. |
| extraction_method | text | text | text (PDF text layer) or ocr (scanned page read with Apple Vision; text in raw/ocr_text). |
| id_link | text | exact | How the row was linked to its feeder: exact, fuzzy_ocr (scanned name matched to a text-month feeder at similarity 0.88 or more), fuzzy_ocr_conflict (a second scanned row matched the same feeder in the same month; kept as its own id). |
| source_file | text | AEDC-Monthly-Energy-Cap-for-April-2023.p | File name of the NERC PDF in raw/pdfs. |
| source_page | number | 19 | Page of the PDF the row is on (1-based). |
| regulator | text | NERC | Who set the cap: NERC, or the state regulator for states that took over (LASERC Lagos, EERC Enugu). |
| band_source | text | printed | printed (band printed in the order); carried_from_nerc_YYYY-MM (Enugu: EERC prints no band, so the band is the one NERC last printed for the feeder, in that month); not_published (no band anywhere, band left blank). Only printed bands count in band statistics. |

## `data/clean/feeders.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| feeder_id | text | 3db4455cbb6d | Stable id for a feeder across months (12 hex characters). Links the same feeder through renames. |
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| disco_name | text | Abuja | Distribution company short name. |
| state | text | FCT | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| business_unit | text | FCT | Business unit, district or area office as printed by the DisCo. |
| voltage_kv | number |  | Feeder voltage in kV when printed (11 or 33). |
| injection_substation | number |  | Injection substation, Ikeja-style names only ('11-<substation>INJ-T<n>-<feeder>'). |
| feeder_name | text | APO AT3_H37_S26_K10 | Feeder name without the Ikeja substation prefix. |
| feeder_raw | text | APO AT3_H37_S26_K10 | Feeder name exactly as printed in the order. |
| first_seen | text | 2023-01 | First order month the feeder appears in. |
| last_seen | text | 2026-09 | Last order month the feeder appears in. |
| months_listed | number | 7 | Number of order months the feeder appears in. |
| latest_band | text | A | Band in the feeder's last month. |
| latest_cap_kwh | number | 207 | Cap in the feeder's last month. |
| best_band_ever | text | A | Highest band the feeder ever had (A is highest). |
| worst_band_ever | text | A | Lowest band the feeder ever had. |
| band_changes | number | 0 | Number of times the feeder's band changed between consecutive listings. |
| regulator | text | NERC | Regulator of the feeder's latest row (NERC, LASERC or EERC). |
| latest_band_source | text | printed | band_source of the latest row (see caps_long). |

## `data/parsed/nerc_caps_all.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| year | number | 2022 | Order year. |
| month | number | 10 | Order month number. |
| state | number |  | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| business_unit | text | Abaji Area | Business unit, district or area office as printed by the DisCo. |
| voltage_kv | number |  | Feeder voltage in kV when printed (11 or 33). |
| injection_substation | number |  | Injection substation, Ikeja-style names only ('11-<substation>INJ-T<n>-<feeder>'). |
| transformer | number |  | Transformer at the injection substation, Ikeja-style names only. |
| feeder_name | text | GW_L35_L3_FD2 | Feeder name without the Ikeja substation prefix. |
| feeder_raw | text | GW_L35_L3_FD2 | Feeder name exactly as printed in the order. |
| service_band | text | E | Band as extracted (A to E, or ? when unreadable in a scan). |
| cap_kwh | number | 127 | Maximum kWh a DisCo may bill an unmetered non-MD customer on this feeder for the month (Order NERC/307/2022). |
| source_file | text | AEDC-Monthly-Energy-Cap-for-October-2022 | File name of the NERC PDF in raw/pdfs. |
| source_page | number | 1 | Page of the PDF the row is on (1-based). |
| source_sha16 | text | aee479b3125874c9 | First 16 hex characters of the source PDF's SHA-256. |
| bu_inferred | number | 1 | 1 when the business unit was printed once for a group of rows (merged cells) and filled for this row from the nearest label. |
| extraction_method | text | text | text (PDF text layer) or ocr (scanned page read with Apple Vision; text in raw/ocr_text). |

## `data/parsed/sources.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| order_month | text | 2022-10 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| file | text | AEDC-Monthly-Energy-Cap-for-October-2022 | Source PDF file name. |
| sha256 | text | aee479b3125874c9a40f19a7726f171c097a775d | SHA-256 of the source PDF. |
| bytes | number | 1107535 | PDF size in bytes. |
| pages | number | 23 | PDF page count. |
| rows | number | 683 | Rows extracted (sources.csv) or records affected (qa table). |
| unparsed_lines | number | 1 | Lines that looked like data but could not be parsed. |
| extraction | text | text | Extraction methods used in the file: text, ocr or text+ocr. |

## `data/qa/unmapped_business_units.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| bu_core | text | OFFICE | Business unit name normalised (upper case, words like BU, DISTRICT, AREA OFFICE removed). |
| rows | number | 289 | Rows extracted (sources.csv) or records affected (qa table). |

## `data/rankings/anomaly_low_band_high_cap_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco_name | text | Benin | Distribution company short name. |
| state | text | DELTA | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| business_unit | text | KOKA | Business unit, district or area office as printed by the DisCo. |
| feeder_raw | text | SIO | Feeder name exactly as printed in the order. |
| band | text | D | Service band A to E. A promises at least 20 hours of supply a day; E the least. '?' only in data/parsed, where a scanned band letter could not be read. |
| cap_kwh | number | 908 | Maximum kWh a DisCo may bill an unmetered non-MD customer on this feeder for the month (Order NERC/307/2022). |
| disco_band_A_median | number | 478.0 | Median cap of Band A feeders in the same DisCo and month. |

## `data/rankings/cap_distribution_by_band_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| band | text | A | Service band A to E. A promises at least 20 hours of supply a day; E the least. '?' only in data/parsed, where a scanned band letter could not be read. |
| count | number | 644.0 | Number of feeders. |
| 10% | number | 119.0 | 10th percentile of cap_kwh. |
| 50% | number | 289.0 | Median cap_kwh. |
| 90% | number | 774.7 | 90th percentile of cap_kwh. |
| max | number | 1890.0 | Maximum cap_kwh. |

## `data/rankings/discos_by_band_A_share_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| disco_name | text | Abuja | Distribution company short name. |
| feeders | number | 635.0 | Number of distinct feeders listed. |
| band_A | number | 327.0 | Feeders in Band A. |
| share_A_pct | number | 51.5 | Percent of feeders in Band A. |
| band_B | number | 168.0 | Feeders in Band B. |
| share_B_pct | number | 26.5 | Percent of feeders in Band B. |
| band_C | number | 78.0 | Feeders in Band C. |
| share_C_pct | number | 12.3 | Percent of feeders in Band C. |
| band_D | number | 62.0 | Feeders in Band D. |
| share_D_pct | number | 9.8 | Percent of feeders in Band D. |
| band_E | number | 0.0 | Feeders in Band E. |
| share_E_pct | number | 0.0 | Percent of feeders in Band E. |
| median_cap_kwh | number | 260.0 | Median cap across all listed feeders. |
| median_cap_A | number | 390.0 | Median cap of Band A feeders (kWh). |
| median_cap_B | number | 238.5 | Median cap of Band B feeders (kWh). |
| median_cap_C | number | 121.5 | Median cap of Band C feeders (kWh). |
| median_cap_D | number | 132.5 | Median cap of Band D feeders (kWh). |
| median_cap_E | number | 284.0 | Median cap of Band E feeders (kWh). |

## `data/rankings/discos_by_downgrades.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco_name | text | Abuja | Distribution company short name. |
| downgrade | number | 173 | Band changes to a lower band. |
| upgrade | number | 252 | Band changes to a higher band. |
| net_upgrades | number | 79 | upgrade minus downgrade. |

## `data/rankings/highest_caps_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco_name | text | Abuja | Distribution company short name. |
| state | text | FCT | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| business_unit | text | ASOKORO | Business unit, district or area office as printed by the DisCo. |
| feeder_raw | text | AT5_ FDR4_B33_6A | Feeder name exactly as printed in the order. |
| band | text | A | Service band A to E. A promises at least 20 hours of supply a day; E the least. '?' only in data/parsed, where a scanned band letter could not be read. |
| cap_kwh | number | 1890 | Maximum kWh a DisCo may bill an unmetered non-MD customer on this feeder for the month (Order NERC/307/2022). |

## `data/rankings/lowest_caps_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco_name | text | Kaduna | Distribution company short name. |
| state | text | SOKOTO | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| business_unit | text | SOKOTO NORTH | Business unit, district or area office as printed by the DisCo. |
| feeder_raw | text | 11KV WURNO | Feeder name exactly as printed in the order. |
| band | text | D | Service band A to E. A promises at least 20 hours of supply a day; E the least. '?' only in data/parsed, where a scanned band letter could not be read. |
| cap_kwh | number | 52 | Maximum kWh a DisCo may bill an unmetered non-MD customer on this feeder for the month (Order NERC/307/2022). |

## `data/rankings/most_volatile_feeders.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco_name | text | Abuja | Distribution company short name. |
| state | text | NASARAWA | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| feeder_raw | text | AT7_FDR 1 (AKWANGA FDR)_PL_PL | Feeder name exactly as printed in the order. |
| months_listed | number | 43 | Number of order months the feeder appears in. |
| band_changes | number | 12 | Number of times the feeder's band changed between consecutive listings. |
| best_band_ever | text | A | Highest band the feeder ever had (A is highest). |
| worst_band_ever | text | D | Lowest band the feeder ever had. |
| latest_band | text | A | Band in the feeder's last month. |

## `data/rankings/states_by_band_A_share_latest.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| state | text | FCT | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| feeders | number | 601.0 | Number of distinct feeders listed. |
| band_A | number | 320.0 | Feeders in Band A. |
| share_A_pct | number | 53.2 | Percent of feeders in Band A. |
| band_B | number | 159.0 | Feeders in Band B. |
| share_B_pct | number | 26.5 | Percent of feeders in Band B. |
| band_C | number | 78.0 | Feeders in Band C. |
| share_C_pct | number | 13.0 | Percent of feeders in Band C. |
| band_D | number | 44.0 | Feeders in Band D. |
| share_D_pct | number | 7.3 | Percent of feeders in Band D. |
| band_E | number | 0.0 | Feeders in Band E. |
| share_E_pct | number | 0.0 | Percent of feeders in Band E. |
| median_cap_kwh | number | 274.0 | Median cap across all listed feeders. |
| median_cap_A | number | 395.0 | Median cap of Band A feeders (kWh). |
| median_cap_B | number | 269.0 | Median cap of Band B feeders (kWh). |
| median_cap_C | number | 121.5 | Median cap of Band C feeders (kWh). |
| median_cap_D | number | 132.5 | Median cap of Band D feeders (kWh). |
| median_cap_E | number | 100.5 | Median cap of Band E feeders (kWh). |

## `data/reference/bu_state_manual.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco | text | JEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| bu_core | text | BUKURU | Business unit name normalised (upper case, words like BU, DISTRICT, AREA OFFICE removed). |
| state | text | PLATEAU | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| source | text | manual: business unit or area office nam | Reason for the manual mapping. |

## `data/reference/state_regulators.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| state | text | Enugu | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| regulator_name | text | Enugu State Electricity Regulatory Commi | State electricity regulator. |
| regulator_acronym | text | EERC | Regulator acronym as used in NERC's order. |
| nerc_order_no | text | NERC/2024/039 | NERC transfer order number(s). |
| order_date | text | 2024-04-22 | Date the transfer order was signed. |
| effective_date | text | 2024-10-22 | Completion deadline written in the order (or NERC's transition date, see effective_date_type). |
| effective_date_type | text | completion_deadline | completion_deadline or transition_date_per_NERC. |
| status | text | completed | completed, in transition, or not transferred. |
| successor_entity | text | MainPower Electricity Distribution Limit | Company licensed by the state regulator to take over distribution, where known. |
| parent_disco | text | EEDC | DisCo the successor was carved out of. |
| sources | text | https://nerc.gov.ng/wp-content/uploads/2 | Source URLs, space separated. |
| notes | text | Order commenced 2024-05-01. NERC lists t | Conflicts and caveats. |
| publishes_caps | text | yes | Whether the state regulator publishes its own monthly energy caps: yes, no or unverified (site could not be checked). |
| publishes_bands | text | no | Whether it publishes feeder service bands. |
| publishes_tariffs | text | yes | Whether it publishes its own tariff orders. |
| publishing_notes | text | Interim order follows NERC tariffs. | What was found and where. |
| checked_on | date | 2026-10-26 | Date the regulator's website and news coverage were checked. |

## `data/summary/band_transitions.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| feeder_id | text | 0007c605d90e | Stable id for a feeder across months (12 hex characters). Links the same feeder through renames. |
| disco | text | EKEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| disco_name | text | Eko | Distribution company short name. |
| state | text | LAGOS | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| feeder_raw | text | 11kV-ALAKIJA | Feeder name exactly as printed in the order. |
| prev_month | text | 2023-01 | Order month of the previous listing. |
| month | text | 2023-02 | Order month number. |
| prev_band | text | E | Band at the previous listing. |
| new_band | text | C | Band at this listing. |
| direction | text | upgrade | upgrade (to a higher band) or downgrade. |
| steps | number | 2 | Number of bands moved. |

## `data/summary/coverage_by_month.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| order_month | text | 2022-10 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| pdfs | number | 11 | Source PDFs for the month. |
| discos | number | 11 | DisCos with an order that month (comma list in state_jurisdiction). |
| states | number | 35 | States with at least one feeder that month. |
| feeders | number | 3130 | Number of distinct feeders listed. |

## `data/summary/disco_month.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| disco | text | AEDC | Distribution company code: AEDC Abuja, BEDC Benin, EEDC Enugu, EKEDC Eko, IBEDC Ibadan, IKEDC Ikeja, JEDC Jos, KAEDC Kaduna, KEDCO Kano, PHED Port Harcourt, YEDC Yola, APLE Aba Power. |
| disco_name | text | Abuja | Distribution company short name. |
| order_month | text | 2022-10 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| feeders | number | 680.0 | Number of distinct feeders listed. |
| band_A | number | 355.0 | Feeders in Band A. |
| share_A_pct | number | 52.2 | Percent of feeders in Band A. |
| band_B | number | 77.0 | Feeders in Band B. |
| share_B_pct | number | 11.3 | Percent of feeders in Band B. |
| band_C | number | 92.0 | Feeders in Band C. |
| share_C_pct | number | 13.5 | Percent of feeders in Band C. |
| band_D | number | 114.0 | Feeders in Band D. |
| share_D_pct | number | 16.8 | Percent of feeders in Band D. |
| band_E | number | 42.0 | Feeders in Band E. |
| share_E_pct | number | 6.2 | Percent of feeders in Band E. |
| median_cap_kwh | number | 144.5 | Median cap across all listed feeders. |
| median_cap_A | number | 281.0 | Median cap of Band A feeders (kWh). |
| median_cap_B | number | 135.0 | Median cap of Band B feeders (kWh). |
| median_cap_C | number | 99.5 | Median cap of Band C feeders (kWh). |
| median_cap_D | number | 99.5 | Median cap of Band D feeders (kWh). |
| median_cap_E | number | 93.5 | Median cap of Band E feeders (kWh). |

## `data/summary/like_for_like_trend.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| order_month | text | 2022-10 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| feeders | number | 2140.0 | Number of distinct feeders listed. |
| band_A | number | 565.0 | Feeders in Band A. |
| share_A_pct | number | 26.4 | Percent of feeders in Band A. |
| band_B | number | 278.0 | Feeders in Band B. |
| share_B_pct | number | 13.0 | Percent of feeders in Band B. |
| band_C | number | 467.0 | Feeders in Band C. |
| share_C_pct | number | 21.8 | Percent of feeders in Band C. |
| band_D | number | 432.0 | Feeders in Band D. |
| share_D_pct | number | 20.2 | Percent of feeders in Band D. |
| band_E | number | 398.0 | Feeders in Band E. |
| share_E_pct | number | 18.6 | Percent of feeders in Band E. |
| median_cap_kwh | number | 159.0 | Median cap across all listed feeders. |
| median_cap_A | number | 232.0 | Median cap of Band A feeders (kWh). |
| median_cap_B | number | 181.0 | Median cap of Band B feeders (kWh). |
| median_cap_C | number | 141.0 | Median cap of Band C feeders (kWh). |
| median_cap_D | number | 136.5 | Median cap of Band D feeders (kWh). |
| median_cap_E | number | 144.5 | Median cap of Band E feeders (kWh). |

## `data/summary/state_jurisdiction.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| state | text | EKITI | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| first_month | text | 2022-10 | First order month the state appears in. |
| last_month | text | 2025-09 | Last order month the state appears in. |
| months_present | number | 32 | Order months the state appears in. |
| discos | text | BEDC | DisCos with an order that month (comma list in state_jurisdiction). |
| feeders_peak | number | 28 | Distinct feeders ever listed in the state. |
| still_in_nerc_caps | text | False | True when the state appears in the latest month's orders. |
| regulator_acronym | text | EERB | Regulator acronym as used in NERC's order. |
| nerc_order_no | text | NERC/2024/041; NERC/2024/042 | NERC transfer order number(s). |
| order_date | text | 2024-04-22 | Date the transfer order was signed. |
| transfer_deadline | text | 2024-10-22 | Completion deadline of the state's NERC transfer order. |
| transfer_status | text | completed | Status of the transfer. |
| transferred | text | True | True when a transfer is completed or in transition. |
| published_after_transfer_deadline | text | True | True when NERC still listed the state after the transfer deadline. |

## `data/summary/state_month.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| state | text | ABIA | Nigerian state of the feeder (36 states plus FCT), UNKNOWN when it could not be established. |
| order_month | text | 2022-10 | Month of the NERC order (YYYY-MM). The cap applies to bills for this month. |
| feeders | number | 49.0 | Number of distinct feeders listed. |
| band_A | number | 5.0 | Feeders in Band A. |
| share_A_pct | number | 10.2 | Percent of feeders in Band A. |
| band_B | number | 2.0 | Feeders in Band B. |
| share_B_pct | number | 4.1 | Percent of feeders in Band B. |
| band_C | number | 17.0 | Feeders in Band C. |
| share_C_pct | number | 34.7 | Percent of feeders in Band C. |
| band_D | number | 19.0 | Feeders in Band D. |
| share_D_pct | number | 38.8 | Percent of feeders in Band D. |
| band_E | number | 6.0 | Feeders in Band E. |
| share_E_pct | number | 12.2 | Percent of feeders in Band E. |
| median_cap_kwh | number | 110.0 | Median cap across all listed feeders. |
| median_cap_A | number | 132.0 | Median cap of Band A feeders (kWh). |
| median_cap_B | number | 228.0 | Median cap of Band B feeders (kWh). |
| median_cap_C | number | 121.0 | Median cap of Band C feeders (kWh). |
| median_cap_D | number | 105.0 | Median cap of Band D feeders (kWh). |
| median_cap_E | number | 82.0 | Median cap of Band E feeders (kWh). |

## `data/summary/transitions_by_month.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| month | text | 2022-11 | Order month number. |
| downgrade | number | 1 | Band changes to a lower band. |
| upgrade | number | 7 | Band changes to a higher band. |

## `data/parsed/nerc_caps_YYYY-MM.csv`

Same columns as `data/parsed/nerc_caps_all.csv`, one file per order month.

## `data/parsed/state_caps_all.csv`

Raw extraction of state regulators' cap files (`scripts/state_caps.py`), before cleaning. Same columns as `data/parsed/nerc_caps_all.csv`, plus:

| Column | Type | Example | Meaning |
|---|---|---|---|
| regulator | text | LASERC | LASERC (Lagos State Electricity Regulatory Commission) or EERC (Enugu Electricity Regulatory Commission). |
| band_source | text | printed | As in `data/clean/caps_long.csv`. |

## `data/parsed/state_sources.csv`

| Column | Type | Example | Meaning |
|---|---|---|---|
| regulator | text | LASERC | State regulator that published the file. |
| order_month, disco, file, sha256, rows, unparsed_lines | | | As in `data/parsed/sources.csv`; files are in raw/state/. |

## `data/parsed/state_listed.csv`

Every cap file a state regulator lists, and whether it could be downloaded.

| Column | Type | Example | Meaning |
|---|---|---|---|
| regulator | text | LASERC | State regulator. |
| order_month | text | 2026-10 | Month of the cap order. |
| disco | text | IKEDC | DisCo code of the feeders in the file (Lagos successors map back: IE Energy Lagos to IKEDC, Excel to EKEDC). |
| status | text | have | have or downloaded (in raw/state), unavailable (listed but the regulator's storage refuses it). |
| title | text | Lagos State_IE Monthly Energy Cap, October 2026 | Title as listed by the regulator. |
| url | text | https://eerc.en.gov.ng/... | Where it is listed or stored. |

## `data/qa/state_nerc_overlap.csv`

Feeder-months published by both NERC and a state regulator (Ogun feeders that LASERC's Ikeja file also lists). The NERC row is kept in the clean tables.

| Column | Type | Example | Meaning |
|---|---|---|---|
| regulator | text | LASERC | State regulator that also listed the feeder. |
| nerc_state | text | OGUN | State in NERC's order. |
| nerc_band | text | C | Band in NERC's order. |
| nerc_cap_kwh | number | 357 | Cap in NERC's order. |
| nerc_source_file | text | IE-monthly-energy-caps-Aug-2026.pdf | NERC PDF. |

## `data/summary/state_regulator_caps.csv`

One row per state regulator file month: how its caps compare with the last cap NERC set for the same feeders.

| Column | Type | Example | Meaning |
|---|---|---|---|
| regulator | text | EERC | State regulator. |
| linked_to_nerc | number | 70 | Feeders in the month that link to a feeder in NERC's orders. |
| nerc_last_month | text | 2025-09 | NERC's last order month for those feeders. |
| median_nerc_last_cap_kwh | number | 165.5 | Median of the last NERC cap for the linked feeders. |
| median_change_vs_nerc_pct | number | -27.4 | Median percent change from the last NERC cap to the state regulator's cap, same feeder. |


## `data/summary/state_vs_nerc_year_on_year.csv`

Caps follow metered consumption and move with the seasons, so state caps are compared with NERC's cap for the same feeder twelve months earlier, next to the same comparison for the states NERC still covers.

| Column | Type | Example | Meaning |
|---|---|---|---|
| group | text | LASERC | LASERC, EERC, or NERC (all feeders still in NERC's orders). |
| disco | text | IKEDC | DisCo code, or all for the NERC group. |
| order_month | text | 2026-08 | Month compared. |
| vs_month | text | 2025-08 | The same month a year earlier (a NERC order). |
| feeders_compared | number | 278 | Feeders present in both months. |
| median_change_pct | number | -11.4 | Median percent change in the feeder's cap over the year; blank when no feeder could be compared. |
