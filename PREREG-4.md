# Pre-registration, step 4: did violence beat a forecast made before the cut?

aid-cut-violence, MV2 of Munim, Inc. Written 2026-11-17 with AI agents, before any result of
steps 1-3 exists and before any of the data below was opened for analysis. Code: `forecast.py`
(Apache-2.0), tests: `test_forecast.py`. Text: CC BY 4.0.

## 1. Question

Steps 1-3 and the published studies compare countries (or regions) with more and less US aid,
before and after early 2025. Their weak point is the counterfactual. USAID-dependent places are
fragile places, and a rise in violence there after January 2025 could be a trend that was
already under way: the Sahel insurgencies, M23 in eastern DR Congo, Sudan's war.

**VIEWS**, the Violence and Impacts Early-Warning System of Uppsala University and PRIO, publishes
monthly country-month forecasts of UCDP state-based conflict deaths for every country, 36 months
ahead, and keeps every past run in its public API (https://api.viewsforecasting.org/). Run
`fatalities002_2025_01_t01` used conflict data through January 2025 and has no aid variables. Its
forecasts for February-December 2025 are therefore a counterfactual **fixed before the USAID
shutdown, by forecasters who could not know about it, using conflict history and trends**. A trend
that was already under way is in the forecast. An effect of the cut is not.

**Test:** did 2025 violence exceed the VIEWS forecast by more in USAID-dependent countries than
the 2024 violence exceeded the January 2024 forecast (same model family, same horizons)?

**Why it is new.** We found no study that uses archived conflict forecasts as the counterfactual
for the 2025 aid cut, or that checks whether forecasting systems missed it. Rohner et al. (Science
2026), Tan, Amarasinghe and Ubilava, Crawfurd (CGD) and Graham (GODAD WP1) all use exposure DiD or
event-study designs (search on 2026-11-17).

**What a positive result would mean:** the first evidence that the post-cut rise in violence in
aid-dependent countries was not foreseeable from conflict dynamics alone, plus an estimate of the
excess state-based deaths relative to an independent, pre-committed forecast. **What a null would
mean:** the rise was already in the forecast, and dependence designs may be picking up escalation
trends rather than the cut.

## 2. Data (all open)

- VIEWS country-month state-based (`cm/sb`) forecasts, runs `fatalities002_2025_01_t01`
  (counterfactual), `fatalities002_2024_01_t01` (comparison year, same model family),
  `fatalities001_2023_01_t01` and `fatalities001_2022_01_t01` (placebos, older model). Forecast =
  `main_mean_ln` (fatalities002) or `sc_cm_sb_main` (fatalities001), both log(1 + predicted
  deaths). We checked the scale on 2026-11-17: DR Congo, Feb 2025, `main_mean` 360.96 and
  `main_mean_ln` 5.8915 = log(361.96). Dichotomous forecast = `main_dich` /
  `sc_cm_sb_dich_main`, P(at least 25 state-based deaths in the month). The code stops if a run's
  largest forecast exceeds 20 (that would mean the field is not on the log scale).
- Actual: UCDP GED 26.1 (final, through Dec 2025) and UCDP Candidate Events 26.01-26.09,
  `type_of_violence` 1 (state-based) only, `best` deaths, summed by country and month of
  `date_start`. Same files as steps 1-3.
- Exposure: ForeignAssistance.gov managing-agency file, USAID-managed disbursements (constant
  USD), as in step 2. E_usaid(o) = log(1 + mean disbursements per person over the three fiscal
  years before origin year o): FY2022-2024 for 2025, FY2021-2023 for 2024 and so on. Population:
  World Bank 2023.
- Sample: as in step 1 (World Bank non-high-income countries with population at least 1 million,
  without Ukraine, Russia, Israel and Palestine) that have forecasts in every window month of both
  the 2025 and 2024 runs. **Stop rule:** fewer than 60 such countries.

## 3. Outcome

For country c and origin o (a January run): e(c, o) = mean over February-December of year o of
[log(1 + actual deaths) - VIEWS log forecast]. These are forecast steps 1-11. Dichotomous error:
mean of [1(deaths >= 25) - P(deaths >= 25)].

## 4. Models (cross-section, one row per country)

- **F1:** e(c, 2025) on E_usaid(2025).
- **F2 (primary):** e(c, 2025) - e(c, 2024) on E_usaid(2025). Global, Africa (World Bank
  Sub-Saharan Africa plus Algeria, Egypt, Libya, Morocco, Tunisia, Djibouti), rest of world.
  Leave-one-out on global.
- **F2b:** e(c, 2025) - mean(e(c, 2024), e(c, 2023)) on E_usaid(2025).
- **F2r:** F2 within World Bank regions (exposure demeaned within region, permutation within
  region).
- **F3 (placebos):** e(c, o) on E_usaid(o) for o = 2024 and 2023, global and Africa. o = 2022 is
  exploratory.
- **F3d (placebo of the primary design):** e(c, 2024) - e(c, 2023) on E_usaid(2024).
  e(2023) - e(2022) is exploratory.
- **F4:** F2 with the mean 2025 VIEWS log forecast as a control (regression to the mean and
  selection on expected intensity).
- **F5:** F2 with the dichotomous error.
- **F6:** F1 over the extended window February 2025 to the last candidate month (at most
  September 2026, forecast steps 1-20). F6d (exploratory): extended e(2025) - e(2024).

Inference: two-sided randomization inference, 9,999 permutations of exposure across countries
(seed 20261117), plus HC1 standard errors. Descriptive, no prediction: mean error by origin; the
correlation of 2024 and 2025 errors; actual and forecast state-based deaths summed by tercile of
E_usaid, for 2024 and 2025; F2 slope times the interquartile range of E_usaid, as a percentage
difference between a 75th- and a 25th-percentile country.

## 5. Predictions (our probabilities, fixed now)

| id | prediction | P |
|---|---|---|
| F1 | b > 0 | .65 |
| F2a | global b > 0 | .60 |
| F2b' | global RI p < .05 | .20 |
| F2c | Africa b > 0 | .62 |
| F2d | rest of world b > 0 | .50 |
| F2e | F2b has the same sign as F2 | .80 |
| F3a | placebo 2024: RI p >= .10 | .65 |
| F3b | placebo 2023: RI p >= .10 | .65 |
| F3c | placebo of the design, F3d 2024-2023: RI p >= .10 | .75 |
| F4 | F2 with the forecast-level control has the same sign as F2 | .70 |
| F5 | dichotomous F2 has the same sign as F2 | .65 |
| F6 | extended F1 has the same sign as F1 | .70 |
| F7 | no leave-one-out sign flip in global F2 | .50 |
| F8 | F2r (within regions) b > 0 | .55 |

**Reading rule.** We will write "violence beat the pre-cut forecast most where USAID dependence
was highest, after the cut and not before" only if global F2 has b > 0 with RI p < .05, F3c
passes and F7 holds. If global F2 is not significant, we report the 95% interval and the
implied percentage. **Pre-fixed comparison with step 1:** if step 1's global deaths DiD
(asinh, all violence types) is positive with RI p < .05 but the upper end of F2's 95% HC1
interval is below half of step 1's deaths slope, we will write that the forecast counterfactual
does not support an effect of that size. The scales differ (log1p of state-based deaths here,
asinh of all deaths there), and we will say so.

## 6. Known threats

- VIEWS errors may be larger in fragile countries every year. F2 differences this out, and F3
  and F3d test it directly.
- The 2025 run's inputs include January 2025, the first week after the 24 January stop-work order.
  Any effect in that week sits in the forecast and biases F2 toward zero.
- VIEWS was trained on UCDP candidate data. We score against final GED. This is the same in
  every year.
- fatalities001 (2022, 2023 runs) and fatalities002 (2024, 2025) are different models. The
  primary comparison (F2) uses the same model family on both sides.
- Exposure counts USAID disbursements before the cut, not the cut itself (see step 3 for the
  cut share). Other donors also cut aid in 2025.
- The VIEWS 2025 runs are assumed to be the forecasts VIEWS issued at the time. The run name fixes
  the data cut-off, and nothing after January 2025 enters the model even if a run was recomputed.

## 7. Files

`forecast.py` writes `forecast_results.json` (every model, per-country errors, run metadata,
which VIEWS fields were used, unmatched UCDP country names), `forecast_results.md`, and
`forecast_table.csv` (one row per country: exposure, the error for each origin, forecast and
actual 2025 deaths). Results and the grading of every prediction above will go in RESULTS-4.md,
including the predictions that fail.

Contact: MV2, Munim, Inc., mv2@munimtech.com
