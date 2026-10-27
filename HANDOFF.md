# Handoff: naira caps, feeder by area, state regulators (branch `state-caps-and-tariffs`)

Work in progress, 2026-10-27. Delete this file before merging to main.

## Goal (the owner asked for all three)

1. **Naira caps.** Turn each feeder-month cap (kWh) into a maximum bill in naira: cap kWh x NERC allowed Non-MD tariff for that DisCo, band and month x 1.075 VAT.
2. **Feeder by area.** People know their area, not their feeder name. Add a way to go from area or street to feeders.
3. **State regulators.** Cover the states that left NERC's orders.

## House rules

- No em or en dashes anywhere in shipped copy (grep before committing).
- Every number in docs must come from the data (`data/findings.json` or a table); recompute, never guess.
- Tests must pass (`python -m pytest -q`); add tests for every new table.
- Keep NERC findings NERC-only (the analysis is "what NERC published"); state rows add a `regulator` column.
- Do not deploy the Telegram bot (Modal). It reads `data/clean/feeders.csv` from main daily, so merged data reaches it without a deploy. If its code must change, stop and leave a note; the owner must say yes first.
- Never commit secrets. Never republish personal data (EERC's Order 002/2025 lists customer names and account numbers: do not download or commit it).

## 3. State regulators (most advanced)

Research result (checked 2026-10-26):

| State | Regulator | Caps | Bands | Tariffs |
|---|---|---|---|---|
| Lagos | LASERC, laserc.com.ng | Yes, monthly, one PDF per successor DisCo (IE Energy Lagos = IKEDC feeders; Excel/EKEDP/EEDL/LEDL = EKEDC feeders), same layout as NERC | Yes, printed | Monthly supplementary orders Apr to Sep 2026 (IE Sep 2026: A 209.50, B 62.48, C 45.80, D and E 31.24 Non-MD) |
| Enugu | EERC, eerc.en.gov.ng | Yes, monthly since Jul 2026 (Order EERC/2026/001) | No band column | Order EERC/2025/003 (eff. 1 Aug 2025): A 160.40, B 66.47, C 53.78, D 36.49, E 36.20 Non-MD; MainPower charges 209 for A in defiance (EERC decision report 31 Dec 2025) |
| Ekiti, Ondo, Imo, Kogi, Niger, Plateau, Bayelsa, Anambra | | No | No | No (Ekiti interim order follows NERC tariffs; Anambra Order ASERC/ORD/2026/002 adopts NERC instruments; Kogi tariff consultation pending, recheck monthly) |
| Abia | ASERA | unverified (site blocks scripts) | | |
| Oyo, Edo, Ogun, Nasarawa, Gombe, Akwa Ibom (still in NERC orders) | | none publish own caps | | |

- LASERC API: `https://larsec-bk-epeak.ondigitalocean.app/api/content/energy-caps` (title, date, pdfUrl). Jul to Oct 2026 files download; Oct 2025 to Jun 2026 return 403 and are not on the Wayback Machine. NERC's last Lagos order is Feb 2026, so Mar to Jun 2026 is a gap. Tariff orders: `.../api/content/order/documents` (their appendices list feeders with streets: useful for goal 2).
- EERC: list page `https://eerc.en.gov.ng/estimated-billing-caps`, detail pages link `/storage/estimated-billing-caps/documents/*.pdf`. July 2026 PDF has spaces stripped ("ABAKALIKIROAD11KV"); Aug to Oct are clean. Oct 2024 to May 2026 EERC adopted NERC's EEDC caps by order (EERC/2025/001 and 004), so NERC's EEDC files are the legal Enugu caps for that period.

Done on this branch:
- `scripts/state_caps.py`: downloads LASERC and EERC files into `raw/state/{laserc,eerc}/` (names `LASERC_IKEDC_2026-10.pdf`, `EERC_EEDC_2026-07.pdf`), parses them (LASERC via `nerc_caps.parse_pdf`, EERC with its own regex; Enugu band carried from the feeder's last NERC order, `band_source=carried_from_nerc_YYYY-MM`, or `?` if unmatched), writes `data/parsed/state_caps_all.csv`, `state_sources.csv`, `state_listed.csv` (what each regulator lists and whether it downloaded), `state_qa.log`.
- Seed files committed: LASERC Oct 2026 (both), EERC Jul to Oct 2026. The first full run hit a DNS outage, so rerun it.
- The LASERC parser was checked: Oct 2026 IE 313 rows, EKEDP 217 rows, 0 unparsed.

To do:
1. Rerun `python scripts/state_caps.py`; expect LASERC Jul to Oct 2026 (8 files) and EERC Jul to Oct 2026 (4). Check row counts, unparsed lines, July EERC name restoration.
2. `scripts/analyze.py`: load `state_caps_all.csv` too, add `regulator` (NERC rows = "NERC") and `band_source` ("printed" for NERC) columns to `caps_long`; build `caps_long`, `feeders.csv`, `band_history_wide.csv` from all rows; keep every summary, ranking, finding and chart NERC-only (filter `regulator == "NERC"` right after building the clean tables; latest month = latest NERC month). Rows with `band_source` not "printed" are excluded from band statistics. Update `docs/DATA_DICTIONARY.md` generation for new columns and the datapackage schema.
3. `data/reference/state_regulators.csv`: add columns `publishes_caps`, `publishes_bands`, `publishes_tariffs`, `checked_on`, `notes` from the table above. Add a short section to `docs/ANALYSIS.md` (state regulators: who publishes what; Lagos and Enugu caps compared with their last NERC caps for the same feeders: compute the median change) and the README.
4. `.github/workflows/refresh.yml`: add `python scripts/state_caps.py` before `analyze.py`; include `raw/state` in the commit; `check_refresh.py` should warn (not fail) when a regulator lists a month we could not download.
5. Tests: state rows parse, regulator values valid, Lagos feeders link to their NERC history (most LASERC Oct 2026 IKEDC feeder ids should also appear in NERC 2025 rows), no state row duplicates a NERC feeder-month.
6. `docs/index.html` (lookup page): show who set the cap (NERC or LASERC or EERC) and, for Enugu, "band as last published by NERC".

## 1. Naira caps

Research result:
- NERC tariff orders: crawl both `https://nerc.gov.ng/resources/?doc_term=&doc_publication=myto&doc_year=&ins=1` (421 results, paginate `/resources/page/N/?...`) and `?doc_term=MYTO&ins=1`; cards are `div.publication` with `h6.title`, date, PDF link. One PDF per DisCo per month. Names vary a lot (`AEDCMYTO2024-1.pdf`, `IE-MYTO-ORDER-MAY-2024.pdf`, `IE_HOLDCO_YSS_September_2026_093.pdf`).
- Class: use "<Band> - Non-MD" (cap orders are for unmetered non-MD customers; R2 no longer exists). Table "Approved Allowed Tariffs (N/kWh)": Table 10 in MYTO 2024 (has the "2023 Allowed" column = rates payable since Dec 2022), Table 2 in 2024/2025 supplementary orders, Table 3 in 2026 HoldCo orders. Later orders repeat earlier periods as columns (Apr 2024 / May to Jun 2024 / Jul 2024 to Sep 2026), so two orders per DisCo cover Dec 2022 to Sep 2026: the Jan 2024 MYTO 2024 order (IE has none: use `2024/04/April-2024-Supplementary-Order-to-MYTO-IKEDC.pdf`, which shows Jan to Mar) and the Sep 2026 HoldCo order.
- Values seen: Band A ~68 to 72 (Dec 2022 to Mar 2024), 225.00 (from 3 Apr 2024), 206.80 (from 6 May 2024), 209.50 (from Jul 2024). Bands B to E frozen at Dec 2022 rates, differing by DisCo (IE B 62.48, C 45.80, D 31.24, E 31.24; AEDC B 63.35, C 51.79, D 33.95, E 33.95 then 32.88 from Jul 2024). Oct and Nov 2022 rates are unverified (Dec 2022 minor review never published): leave blank.
- PDFs: MYTO 2024 and Apr 2024 are pure scans; 2026 HoldCo orders are typeset but text is vector outlines (pypdf gets ~100 chars). Both need render + OCR. On Linux use tesseract (`apt-get install tesseract-ocr`) or `rapidocr-onnxruntime`; render with PyMuPDF at 200 to 300 dpi; find the page with "Approved Allowed Tariffs".
- VAT 7.5 percent (kept by Nigeria Tax Act 2025); no fixed charges since 2016. VAT on residential bills is from secondary sources: state it as an assumption.
- NERC's 2025/26 orders cover only states still under NERC (IE order says Ogun only, AEDC FCT and Nasarawa only).

To do:
1. Build `data/reference/tariffs_non_md.csv`: disco, band, effective_from (YYYY-MM-DD), effective_to, naira_per_kwh, source_order (title), source_url, source_table, verified ("ocr+eye" when a person or model checked the rendered table image). About 30 values per DisCo. A hand-checked seed table cross-checked by OCR is fine and probably better than full automation; save the rendered table page images you checked in `raw/tariff_pages/`.
2. Add `tariff_naira_per_kwh` and `max_bill_naira` (cap x tariff x 1.075, rounded to the naira) to `caps_long` for NERC rows where a tariff exists; LASERC rows use LASERC tariffs where known (Sep 2026 IE values above; EKEDP from `to_EKO_sep2026`), EERC rows use EERC/2025/003. Leave blank, never guess.
3. Show the naira maximum on the lookup page and in `feeders.csv` (`latest_max_bill_naira`). Document the formula and limitations (Non-MD only, lifeline and MD excluded, VAT assumption, Oct to Nov 2022 unknown).
4. Optional: script to discover new tariff orders monthly and alert (issue) when Band A changes.

## 2. Feeder by area

Research agent died before reporting. What we know:
- Our data already carries business unit and injection substation names, which are often area names; the lookup page searches them.
- LASERC tariff order appendices list feeders with streets (Lagos).
- Many DisCos published "Band A feeders and locations" lists in April/May 2024 (Ikeja Electric, Eko, AEDC, IBEDC); news sites republished them (Punch, Nairametrics, BusinessDay, TheCable). Find them, prefer official PDFs.

To do: research sources per DisCo; build `data/reference/feeder_areas.csv` (feeder_id, disco, area_text, source_url, source_date, match_method) by matching published feeder names to our feeder ids (exact squashed name, then fuzzy within DisCo, flag fuzzy); add area text to the lookup page search. Start with Lagos (LASERC appendices) and whichever DisCo lists are official and complete.

## Finish

- Merge to main only when tests pass and docs numbers are recomputed. Update CHANGELOG (0.2.0: new columns), README, ANALYSIS, DATA_DICTIONARY, datapackage.json, the Kaggle package (`scripts/kaggle_package.py` copies data/reference too).
- Do NOT create a release (it mints a permanent Zenodo DOI); leave a note that v0.2.0 is ready and the owner will say when.
- Delete HANDOFF.md in the merge.
