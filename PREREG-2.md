# Pre-registration 2: was it USAID's money, and which kind of aid?

Frozen 2026-11-17, before any result of the first analysis (PREREGISTRATION.md, job
`aid-cut-violence-v1`) existed and before any 2025-2026 conflict data was looked at by the authors
of this study. The public commit that adds this file is the timestamp.
Author: MV2 of Munim, Inc. (mv2@munimtech.com). The design, code and text were made with AI agents.
License: Apache-2.0 (code), CC BY 4.0 (text).

**What we had seen when this was written.** To learn the file formats, we read the column headers
of the ForeignAssistance.gov managing-agency and country files, and the first rows of the
managing-agency file (USAID rows for Afghanistan, Angola, Albania and a few other countries early
in the alphabet). Those rows show USAID's FY2025 obligations falling to about zero or below
(de-obligations) and FY2025 disbursements falling by roughly a third to a half. We saw no conflict data and no
result of any model.

## 1. Why a second step

The first analysis asks whether countries that depended more on **US aid in general** saw more
organized violence after February 2025. A positive answer has a well-known weakness: countries that
receive much US aid are also poorer, more fragile and more conflict-prone, so "aid dependence" may
simply stand in for "fragility", and fragile places may have had a bad 2025 for other reasons. The
same weakness applies to every country-level exposure design in this literature.

The shutdown gives a sharp way to test this. In January-February 2025 **USAID** was dismantled and
most of its awards were terminated, while much of the rest of US foreign assistance (Defense and
State security assistance, the Millennium Challenge Corporation, Peace Corps, and parts of State's
own programmes) continued or was cut far less. If the violence came from the cut itself, exposure to
**USAID-managed** money should predict it, and exposure to **other US** money (which marks fragile,
strategically important countries just as well) should predict it much less. If both predict it
equally, the "aid cut caused violence" reading is in trouble at country level.

As far as we can find, no published or working-paper estimate separates USAID-managed aid from
other US aid in this way, uses the realized FY2025 drop in disbursements as a dose, or compares
sectors (humanitarian, health, governance, peace and security) worldwide.

## 2. Data (all public, downloaded by `mechanism.py`)

- Outcomes, sample, windows and country names: exactly as in PREREGISTRATION.md (UCDP GED 26.1 and
  candidate events Jan-Sep 2026; World Bank low- and middle-income countries with at least 1 million
  people; Ukraine, Russia, Israel and West Bank and Gaza excluded; Africa = Sub-Saharan Africa plus
  Algeria, Egypt, Libya, Morocco, Tunisia and Djibouti).
- ForeignAssistance.gov **managing-agency summary**
  (https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_implementing.csv):
  constant-dollar disbursements by managing agency, country and fiscal year. "USAID" = rows whose
  managing-agency acronym is USAID; "other" = every other agency.
- ForeignAssistance.gov **US Government sector summary**
  (https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_usg_sector.csv):
  constant-dollar disbursements by sector category and country. Categories are grouped by a fixed
  rule (`sector_group`): name contains "humanitarian" -> humanitarian; "health" or "population" ->
  health; "democracy", "governance" or "human rights" -> governance; "peace" or "security" -> peace
  and security; everything else -> other. If the file has no column whose name contains "category"
  and "name", or no "Country Code" column, the sector test is **not run** and this is reported.
  The distinct category names and their group are written to the results.

## 3. Exposures

- `E_usaid` = log(1 + USAID-managed disbursements per person), mean of FY2022-2024, constant USD,
  2023 population. `E_other` = the same for all other agencies.
- Realized drop `x` = log(1 + USAID per person, FY2022-24 mean) - log(1 + USAID per person, FY2025).
  FY2025 runs October 2024 to September 2025, so it includes four pre-shock months; this makes the
  drop smaller than the true post-shock drop for every country.
- Placebo exposures use FY2020-2022 instead of FY2022-2024.
- Sector exposures: log(1 + disbursements per person in each group), FY2022-2024 mean.

## 4. Models

All models are cross-sections of `delta_i` = (mean post-shock outcome) - (mean pre-shock outcome),
which in a balanced panel is identical to the two-way fixed-effects difference-in-differences
(PREREGISTRATION.md, section 4). Outcomes: asinh(events) (primary) and asinh(deaths) (secondary).

- **A1** `delta ~ E_usaid`: randomization-inference p (9,999 permutations, seed 20261117, two-sided;
  primary) and HC1 p. Global, Africa, rest; primary window; global extended window; leave-one-out
  range for global events.
- **A2 (agency test)** `delta ~ E_usaid + E_other`, HC1 standard errors; Wald test of
  b_usaid - b_other. Global, Africa, rest; primary window; global extended window.
- **B (dose response)** first stage `x ~ E_usaid` (HC1 F); just-identified IV of `delta` on `x`
  instrumented by `E_usaid` (HC1 SE); also plain OLS of `delta` on `x` for comparison. Global,
  Africa, rest; primary window. The first stage is partly mechanical (x contains E_usaid); its job
  is to check that the money really fell most where USAID gave most, and the IV puts the reduced
  form on a per-unit-of-realized-cut scale.
- **C (sector test)** `delta ~ humanitarian + health + governance + peace_security + other`, HC1.
  Global, primary window.
- **D (placebo)** A1 and A2 with a fake shock in February 2023 (window 2021-02 to 2023-12) and
  FY2020-2022 exposures. Global and Africa.

## 5. Predictions (with our prior probabilities)

| # | Prediction | Prior |
|---|---|---|
| M1 | A1 global primary events: b_usaid > 0 | 0.70 |
| M2 | A1 global primary events: RI p < 0.05 | 0.35 |
| M3 | A2 global primary events: b_usaid > b_other (point estimates) | 0.65 |
| M4 | A2 global primary events: b_usaid - b_other > 0 with p < 0.05 | 0.20 |
| M5 | B global: first-stage slope > 0 with F > 10 | 0.90 |
| M6 | B global events: IV estimate > 0 | 0.65 |
| M7 | A1 rest-of-world primary events: b_usaid > 0 | 0.55 |
| M8 | C global events: governance coefficient > 0 | 0.55 |
| M9 | C global events: governance coefficient is the largest of the five | 0.30 |
| M10 | D1 placebo, events, global and Africa: RI p >= 0.10 in both | 0.75 |
| M11 | A1 global primary: deaths b has the same sign as events b | 0.75 |
| M12 | A1 extended global events: b > 0 and at least half the primary b | 0.55 |

Reasoning behind M8-M9: governance, democracy and conflict-prevention programmes (for example
community stabilization and transition-initiative work) were terminated almost entirely, while some
life-saving humanitarian and health aid continued under waivers. We hold this weakly.

## 6. How results will be read

- "The violence tracks USAID's money specifically" is claimed only if M1 and M2 hold, M3 holds, and
  the placebo M10 passes. With M4 as well, it is called strong evidence.
- If b_other is as large as b_usaid or larger, we will say that country-level aid-exposure designs
  cannot separate the cut from fragility, and that this weakens the causal reading of our own first
  analysis (and of country-level designs generally); subnational designs are then the way forward.
- The sector test is underpowered (about 125 countries, five correlated regressors). A single
  significant sector is reported as suggestive, not as a mechanism.
- Every prediction is graded true or false in RESULTS-2.md, including failures. Anything added
  after the data is opened is labelled exploratory.

## 7. Known limits, stated in advance

- Managing agency is how ForeignAssistance.gov records who ran the money; some USAID-managed
  programmes moved to State in mid-2025, and some "other" aid was also frozen. Both blur the contrast
  and bias b_usaid - b_other towards zero.
- FY2025 disbursement data may still be revised; the realized drop is measured as served on the
  download date (SHA-256 recorded).
- All limits of PREREGISTRATION.md section 7 apply (UCDP is organized violence with deaths only;
  candidate data for 2026; other donors also cut; country level is coarse; observational design).
