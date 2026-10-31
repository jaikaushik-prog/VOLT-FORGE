# VOLT-FORGE V4

V4 repairs the heat calculation, makes the Raspberry Pi 5 backup the visible application, and supports comparison of simulated design alternatives.

## Round 1 corrections, 31 October

The [implementation report](reports/round1_improvements_v1/IMPLEMENTATION.md) records the subsequent qualification, component-compatibility, accounting and interface corrections. Existing fitted models and frozen studies are preserved. New runs carry a changed software identity; the historical study below was not rerun as experimental validation. A revised submission PDF is kept separately from the original.

## Run it

Use Python 3.12.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python scripts/run_editor.py --project workspace/my_project --port 8794
```

Open **http://127.0.0.1:8794**. Choose a new design, then a test type, a load and a starting design.

## The result

**In the frozen study, two LG M50T cells in parallel, with the output at the far cell, were the smallest qualifying simulated candidate among the arrangements tested** for a 25 W, 10-minute Raspberry Pi 5 backup. It passed 33 of 33 required cases at the declared starting charge, temperature and converter assumptions. See [the original recommendation](reports/design_study_v2/RECOMMENDATION.md) and the [subsequent electrical review](reports/round1_review_20261031/ELECTRICAL_REVIEW.md) for corrected board-source interpretation and conditional limits. This is simulation only; board compatibility and measured module accuracy remain unestablished.

## What changed

- **Science:** first-law heat, a versioned LG table, and checks that fail on the V3 formula.
- **Setup:** choose discharge, charge or a custom cycle, then a preset or custom load in amps or watts.
- **Requirements:** every value is labelled sourced, assumed or custom, and edits relabel themselves.
- **Canvas:** the load block shows what the design is tested against.
- **Results:** a four-row verdict, parts and listed cost, wiring warnings and side-by-side trade-offs.
- **Find the smallest design:** rebuilds and tests 1 to 4 cells, keeping refused, unsupported and incomplete cases apart.
- **Protection:** a voltage ceiling and a charging temperature window.
- **AI:** natural creation prompts open a draft, and the AI sees current settings and a bounded trace.

## Evidence

| Item | File |
| --- | --- |
| Study protocol, frozen before running | `configs/round1_design_study_v2.json` |
| Study results | `reports/design_study_v2/` |
| Measured comparison protocol | `configs/measured_comparison_v1.json` |
| Measured results and post-hoc diagnostic | `reports/measured_comparison_v1/` |
| PyBaMM results | `reports/numerical_reference_v2/` |
| Replay receipt, re-audit and independent audit | `reports/v4_release/` |
| Extra checks on the decision, frozen before running | `configs/engineering_checks_v1.json`, `reports/engineering_checks_v1/` |
| Source locators | `configs/source_locators_v1.json` |
| Business case, a hypothesis | `configs/business_case_v1.json` |
| Appendix workbook | `reports/appendix_v1/` |
| Demo video | `reports/demo_v1/` |
| User trial kit, not run yet | `reports/user_trial_v1/` |
| Slide and its data file | `reports/slide_v4/` |

## Limits

Everything here is simulation. The measured comparison missed its pre-declared bands, so temperatures remain unvalidated scenario estimates, not calibrated prediction intervals. V4 does not establish hardware safety, a certified current rating or measured accuracy. See [the re-audit](reports/v4_release/REAUDIT.md) and [Round 1 corrections](reports/round1_improvements_v1/IMPLEMENTATION.md).
