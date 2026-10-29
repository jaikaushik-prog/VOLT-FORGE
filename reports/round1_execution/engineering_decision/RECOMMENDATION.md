# Round 1 engineering decision

Use thicker internal copper links as the preferred candidate for the declared backup study. They reduced peak cell current and increased delivered energy in every tested scenario.

This choice applies to four parallel LG M50T cells supplying 12 A for 10 minutes, starting at 70% charge and 23 °C, with a 3.3 V minimum output target. The study keeps the same cell models, test conditions and preparation in every physical alternative.

| Design | Peak cell current (A) | Peak cell temperature (°C) | Delivered energy (Wh) | Lowest output (V) | Specified copper (g) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original connections | 3.7649 | 25.963 | 7.35257 | 3.6004 | 2.4603 |
| Thicker copper links | 3.4794 | 25.719 | 7.36802 | 3.6079 | 3.4902 |
| Opposite-end collection | 3.1177 | 25.505 | 7.32763 | 3.5876 | 3.7476 |

## Why this candidate

Doubling the internal copper thickness from 0.08 to 0.16 mm reduces nominal peak current by 0.2855 A (7.6%), adds 0.01545 Wh of delivered energy, and adds 1.0299 g of specified copper. Contact resistance and external output routes stay unchanged.

Across 31 paired scenarios, its peak-current change ranges from -0.2970 to -0.0324 A. Delivered-energy gain ranges from 0.01480 to 0.01683 Wh. Every case completed the same requested duty and stayed within the declared simulation targets.

Opposite-end collection shares current more evenly in the nominal preparation. It improves peak current in 30 of 31 scenarios. A +25 mV reference-voltage change in Cell 4 reverses that advantage relative to the baseline. Lower initial charge, differential voltage and a non-rested cell also reverse some rankings between the two alternatives. Its longer negative return adds 90 mm of copper, increases material mass and reduces delivered energy in every tested case.

## What was varied

The paired cases vary initial charge and relaxation, capacity by ±5%, DC and relaxation resistance by ±10%, reference voltage by ±25 mV, room temperature, contacts, heat capacity, cooling and the fraction of connection heat entering cells. One case combines lower charge, lower capacity, higher resistance and non-rested preparation. These are declared scenarios; they do not establish manufacturing distributions or exhaustive worst cases. The parameter variations primarily target the two end cells; arbitrary combinations remain untested.

## Calculation evidence

The study contains 93 matched experiments and 93 half-step repeats. Every refinement check passed its predeclared numerical resolution. The largest temperature difference was 0.0002687 °C; the largest energy difference was 0.00000580 Wh. All three nominal ZIP exports independently reproduced their 1,201 saved samples.

Fifteen independent synthetic electrical cases compared the production solver against native PyBaMM Thevenin and closed-form solutions, covering discharge, charge, rest, zero/one/three relaxation branches and non-rested states. A separate state-dependent two-cell SciPy ODE reference checks coupled temperature feedback. Accounting residuals and step refinement serve different checks; small residuals alone do not prove numerical convergence.

## Temperature evidence and the hardware decision

The new LG model uses 58.5 J/K from the exact-M50T whole-cell reference in [Steinhardt et al. (2021)](https://doi.org/10.1016/j.est.2021.103065). Cooling uses the separately recorded 0.1524918708 W/K effective fixture estimate. That estimate uses measured changing chamber temperature and independently supplied heat capacity; it no longer infers heat capacity and cooling from one time constant. Earlier and later rests yield different estimates, and sensor offset and residual heating remain confounded. The tested cooling range carries that sensitivity into the design comparison.

The sub-degree temperature differences between designs are model predictions. Neither the fitted cooling residual nor the small numerical error is an independent temperature-accuracy interval. Before a hardware change, measure initial cell voltages/charge, joint resistance and actual fixture cooling, and qualify conductor current capacity, insulation and packaging. The current evidence supports this conditional design comparison and reproducible experiment; it does not establish a hardware safety rating.

## Reproduce

The source study directory contains `protocol.json`, `comparison.json`, `comparison.csv`, the three nominal experiment ZIPs and their replay results. Each ZIP contains `report.html`, parameters, solver source and `replay.py`. The JSON alongside this note records every input artifact hash used to derive this recommendation. No raw or reserved observations are opened by the summarizer.
