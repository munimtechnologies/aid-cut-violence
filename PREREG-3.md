# Pre-registration 3: the size of the cut, holding dependence fixed

Frozen 2026-11-17, before any result of steps 1 or 2 (jobs `aid-cut-violence-v1` and
`aid-cut-mechanism-v1`) existed and before the authors had looked at any 2025-2026 conflict data.
The public commit that adds this file is the timestamp.
Author: MV2 of Munim, Inc. (mv2@munimtech.com). The design, code and text were made with AI agents.
License: Apache-2.0 (code), CC BY 4.0 (text).

**What we had seen when this was written.** Ten rows of the CGD country table quoted in a page
summary (Ukraine 15%, DR Congo 34%, Ethiopia 30%, Colombia 82%, Uganda 66%, South Africa 89%,
Palestine 29%, Bangladesh 56%, Kenya 46%, Afghanistan 36% of the country programme cut), the
table's column names, and the CGD text saying that Liberia, Moldova and several others lost 95-100%.
We saw no conflict data and no model output.

## 1. Why a third step

Steps 1 and 2 ask whether countries that **depended more** on US (or USAID) aid saw more violence
after February 2025. Every published study does the same: Rohner, Sunde, Vanden Eynde, Wright and
Zeng (Science 392, 2026; African regions, ACLED), Tan, Amarasinghe and Ubilava ("Aid, Interrupted";
African countries, ACLED), Crawfurd's CGD extension, and Graham (GODAD Working Paper 1, 2026), which
is pre-registered, subnational, covers 19 conflict-affected aid-dependent countries and merges the
leaked lists of cancelled and retained awards. Dependence is not the cut. Aid-dependent places are
also poorer and more fragile, so a dependence design can pick up fragility.

The March 2025 terminations give a second source of variation. USAID did not end everything
equally: some awards were kept (mostly "life-saving" health and humanitarian awards), so countries
with the **same** dependence on USAID lost very different **shares** of their programme. Center for
Global Development researchers Justin Sandefur and Charles Kenny matched the terminated and
retained award lists sent to Congress in March 2025 to ForeignAssistance.gov and published, for each
country, the share of the USAID country programme that was cut ("USAID Cuts: New Estimates at the
Country Level", 26 March 2025, revised August 2025).

If the violence came from the cut, then **among equally dependent countries, those that lost a
larger share should show a larger rise.** If dependence designs only capture fragility, the share
should not matter once dependence is held fixed. We found no study that uses the terminated share
as a dose, worldwide, holding USAID dependence fixed, on open conflict data.

## 2. Data (all public, downloaded by `dose.py`)

- Outcomes, sample, windows and country names: exactly as in PREREGISTRATION.md (UCDP GED 26.1 and
  UCDP candidate events Jan-Sep 2026; World Bank low- and middle-income countries with at least 1
  million people; Ukraine, Russia, Israel and West Bank and Gaza excluded; Africa = Sub-Saharan
  Africa plus Algeria, Egypt, Libya, Morocco, Tunisia and Djibouti).
- USAID dependence: ForeignAssistance.gov managing-agency file, as in PREREG-2.md.
- **Cut share:** the HTML table "Country cuts data" on
  https://www.cgdev.org/blog/usaid-cuts-new-estimates-country-level (columns Country, Cut as %
  country program, Cut as % GNI, Absolute cut ($m)). If the page cannot be fetched or has no such
  table, the Internet Archive copy is used. The raw page's SHA-256 is recorded. Country names are
  matched to ISO3 codes by a fixed rule (`iso_for`); unmatched names and their dollar cuts are
  reported.
- The sample is the step-1 sample **intersected with the countries in the CGD table** (countries
  with country-level USAID awards). Regional and global awards are not in the table.

## 3. Variables

- `S` = cut as % of country programme / 100 (0 to 1).
- `E_usaid` = log(1 + USAID-managed disbursements per person, FY2022-2024 mean), as in PREREG-2.
- `cut_pc` = absolute cut (USD) / 2023 population; `retained_pc` = absolute cut x (100 - %)/% /
  population (the retained value implied by the table; undefined if the % is 0).
- `pre` = mean asinh(monthly outcome) in the pre-shock months of the window.
- `delta` = post-shock mean minus pre-shock mean of asinh(monthly events) (primary) or asinh(monthly
  deaths) (secondary); identical to the two-way fixed-effects DiD in a balanced panel.

## 4. Models

- **T1 (main)** `delta ~ S + E_usaid`, HC1 standard errors; **randomization-inference p** (9,999
  permutations of S **within terciles of E_usaid**, seed 20261117, two-sided, coefficient on S with
  E_usaid held in the model; primary). Primary window (shock 2025-02, to 2025-12): global, Africa,
  rest. Extended window (to 2026-09): global. Placebo window (fake shock 2023-02, 2021-02 to 2023-12,
  FY2020-2022 exposure): global, Africa, rest. Leave-one-out range for global primary events.
- **T1v (selection check)** T1 plus `pre`. Global, primary.
- **T2 (dollar dose)** `delta ~ log1p(cut_pc) + E_usaid`. Global, primary.
- **T3 (cut vs retained)** `delta ~ log1p(cut_pc) + log1p(retained_pc)`, Wald test of the
  difference. Retained money is the same agency in the same countries, but it kept flowing, so it is
  a within-USAID placebo for dependence. Global, primary.
- **D (descriptive)** Pearson correlation of S with pre-shock violence (asinh events, primary
  pre-period) and with E_usaid.
- Reported with each T1: approximate 95% interval (normal), and b_S times the interquartile range of
  S (the effect of moving from a typical low-cut to a typical high-cut country).
- **Stop rule:** if fewer than 40 countries are matched, no model is run and that is reported.

## 5. Predictions (with our prior probabilities)

| # | Prediction | Prior |
|---|---|---|
| S1 | T1 global primary events: b_S > 0 | 0.55 |
| S2 | T1 global primary events: RI p < 0.05 | 0.20 |
| S3 | T1 placebo, events, global: RI p >= 0.10 | 0.75 |
| S4 | T1v global events: b_S > 0 (survives the pre-violence control) | 0.55 |
| S5 | T3 global events: b_cut > b_retained (point estimates) | 0.55 |
| S6 | T1 global primary deaths: b_S has the same sign as events | 0.70 |
| S7 | T1 Africa primary events: b_S > 0 | 0.55 |
| S8 | D: corr(S, pre-shock violence) < 0 (countries in active crises kept more of their programme) | 0.65 |
| S9 | T1 extended global events: same sign as primary | 0.60 |
| S10 | T1 global primary events: no leave-one-out sign flip | 0.50 |

Our priors are near even because the variation is real but the sample is small (we expect about 60
to 90 countries) and selection runs in a known direction (section 7).

## 6. How results will be read

- **"The size of the cut predicts the violence, holding dependence fixed"** is claimed only if S1,
  S2, S3 and S4 all hold. This would be the first worldwide evidence that it was the cut, not
  dependence, that moved violence.
- Comparison with step 1, fixed now: if the upper end of the 95% interval of b_S x IQR(S) is
  below half of (step-1 global primary events b) x IQR(E_usaid in this sample), we will report that **the cut's size does not predict the
  violence once dependence is held fixed**, which weakens the causal reading of dependence designs,
  including our own step 1.
- If the interval is too wide to tell, we will say the test is underpowered and give the interval.
- Every prediction is graded true or false in RESULTS-3.md, including failures. Anything added
  after the data is opened is labelled exploratory.
- Name matching is mechanical. If unmatched CGD names carry more than 2% of the table's absolute
  cut, we will fix only the name table, bump the version, re-run, and report both runs.

## 7. Known limits, stated in advance

- **Selection bias has a predictable sign.** Awards kept were mostly "life-saving" health and
  humanitarian awards, which are concentrated in active crises (S8). If crisis countries' violence
  would have changed differently anyway, b_S is biased. Mean reversion (high-violence places calm
  down) would bias b_S **upward**; continued escalation of ongoing wars would bias it **downward**.
  T1v and the placebo window are the checks; neither is proof.
- The CGD shares come from leaked lists of March 2025; some awards were later reinstated or newly
  terminated, and about a third of awards could not be matched to dollar values. Measurement error
  in S biases b_S toward zero.
- USAID dependence and the cut share are country-level; the effect may sit in particular regions
  (subnational designs such as Graham 2026 and Rohner et al. 2026 address this).
- All limits of PREREGISTRATION.md section 7 and PREREG-2.md section 7 apply. This is research,
  not policy advice.

We thank CGD (Sandefur and Kenny) for publishing the country table; this study only reads it.
