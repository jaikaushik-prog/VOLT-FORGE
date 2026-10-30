# VOLT-FORGE V4

V4 repairs the heat calculation, makes the Raspberry Pi 5 backup the visible application, and turns the tool into something that finds a better design.

## Run it

Use Python 3.12.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python scripts/run_editor.py --project workspace/my_project --port 8794
```

Open **http://127.0.0.1:8794**. Choose a new design, then a test type, a load and a starting design.

## The result

**Two LG M50T cells in parallel, with the output at the far cell, are the smallest qualifying design among the parallel arrangements tested** for a 25 W, 10-minute Raspberry Pi 5 backup. It passed 33 of 33 required cases. See [the recommendation](reports/design_study_v2/RECOMMENDATION.md). This is simulation only.

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

Everything here is simulation. The measured comparison missed its pre-declared bands, so temperatures are a range, not a prediction. V4 does not establish hardware safety, a certified current rating or measured accuracy. See [the re-audit](reports/v4_release/REAUDIT.md).
