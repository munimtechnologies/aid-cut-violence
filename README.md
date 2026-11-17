# aid-cut-violence

**Did the 2025 USAID shutdown raise organized violence worldwide, or only in Africa?**

An open, pre-registered test by MV2 of Munim, Inc. The design, code and text were made with AI agents.
Code: Apache-2.0. Text and results: CC BY 4.0.

## Why

In early 2025 the US froze foreign assistance and shut down most USAID programmes. A May 2026 study
in *Science* (Wright, Rohner et al., "Aiding peace or conflict? The impact of USAID cuts on
violence", doi:10.1126/science.aed6802) found that conflict rose more in African regions that had
received more US aid. Working papers by Tan, Amarasinghe and Ubilava, and Lee Crawfurd at CGD, found
about +5% conflict events, also in Africa. All three use ACLED data, which cannot be freely
redistributed, and none looks outside Africa, though the finding has been reported as global.

This project asks the same question **for every low- and middle-income country**, with **only open
data** (UCDP GED 26.1 and UCDP candidate events to September 2026, ForeignAssistance.gov, World
Bank), and with the design and predictions **fixed in public before the data is opened**:
see [PREREGISTRATION.md](PREREGISTRATION.md).

## What it does

`aidcut.py` (Python standard library only):

1. downloads UCDP GED 26.1, the UCDP 2026 candidate events, the ForeignAssistance.gov country
   summary and World Bank population and metadata, and records each file's SHA-256;
2. builds a balanced country-month panel of UCDP events and deaths (all violence types and each type);
3. computes exposure = log(1 + US aid per person, FY2022-2024 mean disbursements);
4. estimates the difference-in-differences with country and month fixed effects, globally, for
   Africa and for the rest of the world, in the primary (to Dec 2025), extended (to Sep 2026) and
   placebo (fake shock in Feb 2023) windows;
5. reports randomization-inference p-values (9,999 permutations), country-clustered standard
   errors, quarterly event studies with pre-trend tests, robustness checks and leave-one-out ranges;
6. writes `results.json`, `results.md` and `country_table.csv`.

```
python -m unittest -v
python aidcut.py --data-dir data --out-dir out
```

## Status

- 2026-11-17: pre-registration and code published; first run queued. Results and the grading of
  each prediction will be added as RESULTS.md, including the ones that fail.

## Limits

UCDP covers organized violence with deaths, not protests or riots. Exposure measures dependence on
all US foreign assistance, not the size of each country's cut. Other donors cut aid in 2025 too.
The full list is in PREREGISTRATION.md, section 7. This is research, not policy advice.

Contact: MV2, Munim, Inc., mv2@munimtech.com
