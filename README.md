# aid-cut-violence

**Did the 2025 USAID shutdown raise organized violence worldwide, or only in Africa? And was it
the cut itself, or just aid dependence standing in for fragility?**

An open, pre-registered test by MV2 of Munim, Inc. The design, code and text were made with AI agents.
Code: Apache-2.0. Text and results: CC BY 4.0.

## Why

In early 2025 the US froze foreign assistance and shut down most USAID programmes. A May 2026 study
in *Science* (Rohner, Sunde, Vanden Eynde, Wright and Zeng, "Aiding peace or conflict? The impact
of USAID cuts on violence", doi:10.1126/science.aed6802) found that conflict rose more in African
regions that had received more US aid. Working papers by Tan, Amarasinghe and Ubilava, Lee Crawfurd
at CGD, and Jimmy Graham (GODAD Working Paper 1, 19 conflict-affected countries) also found rises.
Most use ACLED data, which cannot be freely redistributed, and none tests the whole world, though
the finding has been reported as global.

This project asks the question **for every low- and middle-income country**, with **only open
data** (UCDP GED 26.1 and UCDP candidate events to September 2026, ForeignAssistance.gov, World
Bank, CGD's published country table, VIEWS's archived forecasts), and with the design and
predictions **fixed in public before the data is opened**.

## Step 1: worldwide test ([PREREGISTRATION.md](PREREGISTRATION.md))

`aidcut.py`: a country-month difference-in-differences of UCDP events and deaths on exposure =
log(1 + US aid per person, FY2022-2024), globally, for Africa and for the rest of the world, in the
primary (to Dec 2025), extended (to Sep 2026) and placebo (fake shock in Feb 2023) windows, with
randomization-inference p-values, clustered errors, event studies and robustness checks.

## Step 2: was it USAID's money, and which kind? ([PREREG-2.md](PREREG-2.md))

`mechanism.py`: USAID-managed versus all other US aid (which mostly continued), the realized FY2025
drop as a dose (IV), sectors, and a placebo.

## Step 3: the size of the cut, holding dependence fixed ([PREREG-3.md](PREREG-3.md))

Countries that depended equally on USAID lost very different **shares** of their USAID programme in
March 2025 (from about 15% to 100%, by CGD's count), because some "life-saving" awards were kept.
`dose.py` asks whether, **among equally USAID-dependent countries, a larger cut share predicts a
larger rise in violence**. It permutes the share within terciles of dependence, adds a
pre-violence control for crisis selection, contrasts cut and retained dollars, and runs a placebo.
If the share does not matter, country-level dependence designs (including our step 1) may be
picking up fragility.

## Step 4: did violence beat a forecast made before the cut? ([PREREG-4.md](PREREG-4.md))

VIEWS (Uppsala University and PRIO) keeps every monthly conflict forecast it has published. Its
January 2025 run used conflict data through January 2025 and no aid data, so its forecasts for the
rest of 2025 are a counterfactual **fixed before the shutdown**: trends already under way are in
it, and an effect of the cut is not. `forecast.py` asks whether 2025 state-based deaths beat that
forecast by more in USAID-dependent countries than 2024 deaths beat the January 2024 forecast.
Placebos use the 2023 and 2022 runs. As far as we know, this is the first use of archived
conflict forecasts as the counterfactual for the aid cut.

```
python -m unittest -v
python aidcut.py --data-dir data --out-dir out
python mechanism.py --data-dir data --out-dir out
python dose.py --data-dir data --out-dir out
python forecast.py --data-dir data --out-dir out
```

## Status

- 2026-11-17: step 1 pre-registration and code published; first run queued.
- 2026-11-17: step 2 (PREREG-2.md, mechanism.py) pre-registered and queued, before step 1 results.
- 2026-11-17: step 3 (PREREG-3.md, dose.py) pre-registered and queued, before any result of steps 1-2.
- 2026-11-17: step 4 (PREREG-4.md, forecast.py) pre-registered and queued, before any result of
  steps 1-3.
- Results and the grading of every prediction will be added as RESULTS.md to RESULTS-4.md,
  including the ones that fail.

## Limits

UCDP covers organized violence with deaths, not protests or riots. Exposure and cut shares are
country-level and observational, not a randomized cut. Other donors cut aid in 2025 too. The cut
shares come from leaked March 2025 award lists as matched by CGD. VIEWS forecasts state-based
deaths only. Each pre-registration lists its own known threats. This is research, not policy
advice.

Contact: MV2, Munim, Inc., mv2@munimtech.com
