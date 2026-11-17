# Pre-registration: did the 2025 USAID shutdown raise organized violence worldwide?

Frozen 2026-11-17, before any 2025-2026 conflict data or exposure data was downloaded or
looked at by the authors of this study. The public commit that adds this file is the timestamp.
Author: MV2 of Munim, Inc. (mv2@munimtech.com). The design, code and text were made with AI agents.
License: Apache-2.0 (code), CC BY 4.0 (text).

## 1. Question

In late January 2025 the US government froze foreign assistance and issued stop-work orders to
USAID programmes worldwide; most USAID awards were terminated in the following weeks. Did
organized violence rise more after February 2025 in countries that had depended more on US aid,
and is that true outside Africa as well as inside it?

## 2. What is already known, and what is new here

- Wright, Rohner and co-authors, *Science* 392, eaed6802 (May 2026), "Aiding peace or conflict?
  The impact of USAID cuts on violence": 870 African subnational regions, ACLED events,
  geocoded US aid (GODAD, 2017-2020), March 2024 to November 2025. More US aid before the cut
  meant more conflict after it (about +12% conflict events in their headline estimate; +9%
  battle deaths in the top-exposure quartile). Africa only.
- Tan, Amarasinghe and Ubilava, "Aid, Interrupted" (working paper): country-level
  difference-in-differences, Africa, ACLED, about +5% conflict events. Lee Crawfurd (CGD)
  replicated and extended it at subnational level, again in Africa with ACLED.
- Nicolini and Sabatini (SSRN, May 2026) study economic outcomes (night lights, IPC), not violence.

Public coverage has described the result as global ("Shutting Down USAID Led to a Rise in Global
Violence", TIME, 2026-05-15), but every causal estimate we found is for Africa, and all use ACLED,
whose terms restrict redistribution. As far as we can find, this is the first test that:

1. covers every low- and middle-income country, so the African result can be compared directly
   with Asia, the Middle East, Latin America and Europe;
2. uses only openly licensed data (UCDP GED, CC BY 4.0), so anyone can rerun it end to end;
3. follows the outcome for up to 20 months after the cut (to September 2026);
4. fixes its predictions publicly before the data is opened.

What a striking result would look like: if the effect holds outside Africa, the evidence would
support a worldwide claim that until now has rested on African data. If it holds only in Africa,
the headlines need correcting and the next question becomes why. Either answer matters for how aid
cuts are debated in 2026-2027 budget fights.

## 3. Data (all public, downloaded by `aidcut.py`)

| Role | Source | URL |
|---|---|---|
| Outcome, 2021-2025 | UCDP Georeferenced Event Dataset 26.1 (final) | https://ucdp.uu.se/downloads/ged/ged261-csv.zip |
| Outcome, Jan-Sep 2026 | UCDP Candidate Events 26.01-26.09 | https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_01_26_09.csv |
| Exposure | ForeignAssistance.gov country summary (as served on the download day; SHA-256 recorded in results) | https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_country.csv |
| Population | World Bank SP.POP.TOTL, 2023 | api.worldbank.org |
| Region, income group | World Bank country metadata | api.worldbank.org |

## 4. Design

- **Unit:** country-month. Event country is UCDP's `country` field, mapped to ISO3 by a fixed
  name table (`ged_iso3`). Unmatched names are reported; if they hold more than 1% of events the
  results are provisional and the table is fixed in the next version.
- **Sample:** World Bank low- and middle-income countries (all income groups except HIC) with 2023
  population of at least 1 million. **Excluded from the primary sample:** Ukraine, Russia, Israel
  and the West Bank and Gaza, because their 2025 violence was driven by inter-state war and
  ceasefire diplomacy and their US assistance is mostly security assistance that the freeze did
  not stop. They are put back in robustness check `incl_wars`.
- **Africa:** World Bank Sub-Saharan Africa plus Algeria, Egypt, Libya, Morocco, Tunisia, Djibouti.
  **Rest:** every other country in the sample.
- **Exposure E:** log(1 + US foreign-assistance disbursements per person), the mean of fiscal years
  2022, 2023 and 2024 in constant US dollars, divided by 2023 population. Countries with no record
  have E = 0.
- **Outcomes** (from UCDP `best` estimates, all three violence types unless stated):
  `events` (asinh of the number of events), `deaths` (asinh of best-estimate deaths),
  `any_event` (0/1), and asinh event counts by type: `ev_state`, `ev_nonstate`, `ev_onesided`.
- **Windows:**
  - primary: 2023-02 to 2025-12 (24 months before, 11 after), shock month 2025-02, GED final data only;
  - extended: 2023-02 to 2026-09 (20 months after), 2026 months from candidate data;
  - placebo: 2021-02 to 2023-12 with a fake shock in 2023-02, the same shape as the primary window.
  January 2025 (stop-work orders from 24 January) counts as pre-period, which is conservative.
- **Estimator:** y_it = a_i + g_t + b (E_i x Post_t) + e_it, with country and month fixed effects,
  balanced panel. In a balanced panel b equals the cross-country slope of (post mean - pre mean)
  on E; the code computes both and checks they agree.
- **Inference:** (1) randomization inference: permute E across countries, 9,999 draws, seed
  20261117, two-sided; this is the primary p-value. (2) Country-clustered CR1 standard errors with
  t(G-1) p-values.
- **Event study:** quarter-sized bins relative to 2025-02 (bin 0 = Feb-Apr 2025), reference bin -1
  (Nov 2024-Jan 2025); joint F test that all earlier pre-period bins are zero.
- **Robustness** (primary window, global sample, events and deaths): include the excluded war
  countries; obligations instead of disbursements; binary top-quartile exposure (among countries
  with E > 0); World Bank region x month fixed effects; drop Sudan; leave-one-country-out range;
  Africa-minus-rest difference.

## 5. Predictions (made before seeing any of the data, with our prior probabilities)

| # | Prediction | Prior |
|---|---|---|
| P1 | Global, primary, events: b > 0 | 0.70 |
| P2 | Global, primary, events: RI p < 0.05 | 0.40 |
| P3 | Africa, primary, events: b > 0 (direction of the published African studies) | 0.80 |
| P4a | Rest of world, primary, events: b > 0 | 0.55 |
| P4b | Rest-of-world b is smaller than Africa b | 0.65 |
| P5 | Placebo (fake 2023 shock), events, global and Africa: RI p >= 0.10 in both | 0.75 |
| P6 | Event study, global, primary: pre-trend F test p >= 0.05 | 0.70 |
| P7 | Extended window, global, events: b > 0 and at least half the primary b (persistence) | 0.55 |
| P8 | Global, primary: deaths b has the same sign as events b | 0.75 |
| P9 | Global, primary, events: no single country's removal flips the sign of b | 0.60 |

## 6. How results will be read

- "The cut was followed by more organized violence worldwide" is claimed only if the global
  primary events estimate is positive with RI p < 0.05 **and** the pre-trend test (P6) and the
  placebo (P5) both pass.
- If Africa is positive and significant but the rest of the world is not, the result is reported
  as Africa-specific, with the rest-of-world estimate and its confidence interval.
- A null result is reported as a null, with the smallest effect the design could have detected.
- Every prediction is graded true or false in RESULTS.md, including the ones that fail. No outcome,
  window or sample is added after the data is opened without being labelled exploratory.

## 7. Known limits, stated in advance

- UCDP records only organized violence with deaths (no protests or riots, unlike ACLED), so the
  outcome is narrower than in the published studies.
- 2026 months come from candidate data, which UCDP revises; the change from final to candidate data
  in January 2026 is common to all countries, but could bias results if revisions track exposure.
- Exposure is all US foreign assistance (State, USAID, DoD, MCC and others), not USAID alone, and
  some programmes (parts of PEPFAR and emergency food aid) resumed. It measures dependence on US
  aid, not the size of each country's cut.
- Other donors (the UK, Germany, France, the Netherlands) also cut aid in 2025, and their cuts
  correlate with US exposure. The estimate is therefore about dependence on Western aid as it fell
  in 2025, not about USAID alone.
- Country level is coarse. A large conflict that was already escalating in January 2025 (for
  example the M23 offensive in eastern DR Congo, which took Goma on 27 January 2025) can drive the
  estimate; the leave-one-out range and the drop-Sudan check are there to show this.
- This is observational evidence. It can show whether the African finding generalizes; it cannot
  by itself prove a mechanism.
