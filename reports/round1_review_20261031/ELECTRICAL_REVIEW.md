# Independent electrical review of VOLT-FORGE V4

Reviewed commit: `c2339a569876da5fc20969ea578a91ae57f33384`, isolated at `tmp/round1_review_20261031/repo`. All source references below are to that checkout. Initial conclusions were recorded in [electrical/INITIAL_NOTES.md](electrical/INITIAL_NOTES.md) before consulting any earlier audit; no earlier audit or another agent's review was consulted. This review does not modify the V4 source, frozen studies, model values, or measured data.

The two-cell result is a useful, defensible **conditional simulation recommendation**. The largest new problems are elsewhere in the product's engineering chain: unknown cell limits can become a sizing pass, and a board is selected by cell count without checking its electrical compatibility. The board recommendation also needs a separate charge-path assessment. The calculation tests passing does not undo the failed measurement comparisons.

## Reproduced findings

Severity here describes the consequence of using the displayed result: **High** means a misleading qualification or component recommendation; **Medium** means an incorrect engineering quantity or unsupported source interpretation. Each finding has a concrete acceptance check, rather than requiring a general rewrite.

### E1 — High: missing cell operating limits can qualify a smallest design

**Confirmed.** `src/voltforge/studio/failure_search.py:47` checks completion, selected targets, thermal availability and first-law closure, then returns `qualifies` at line 54. It never checks whether relevant cell operating limits exist. `src/voltforge/models/custom_cells.py:53` supplies illustrative thermal defaults for a basic custom cell, while line 68 permits an empty operating-limit object. `src/voltforge/studio/design_rules.py:59` produces only a warning about the missing current limit.

**Reproducer:** import a synthetic 2 Ah, 3.7 V, 20 mΩ basic cell with no limits; use one cell at 70% charge and 23 °C; request 8 A for 60 s with a 3.3 V minimum. Actual: completed, 3.54 V, 24.03 °C, first-law closed, `sizing='qualifies'`, plus a `missing_limits` warning. Expected: the selected voltage target may pass, but cell-limit eligibility is **incomplete**. A missing rating is not an unlimited rating. This is a product verdict problem, not evidence that this invented cell is physically unsafe.

**Fix:** retain the calculation and selected-target result, but add an explicit coverage object for relevant charge/discharge current, voltage and temperature limits. Gate sizing qualification on required coverage; distinguish assumed limits from sourced limits. Do not require an unused charge direction for a discharge-only mission unless circulating current actually charges a branch.

**Acceptance:** the fixture above is incomplete; a fully specified version can qualify; a version exceeding an explicit limit fails/refuses; a model without thermal data remains incomplete. Run these through the saved investigation path as well as the helper. Receipt: `missing_limits_sizing` in [receipt.json](electrical/receipt.json).

### E2 — High: parts selection ignores topology, voltage and cell compatibility

**Confirmed software behavior; physical compatibility is not established.** `src/voltforge/studio/parts.py:49` selects converter/protection from the number of cells alone. Its `included_in` handling at line 31 immediately treats protection as included. No topology, port voltage, cell chemistry/dimensions, or output demand enters this choice.

**Reproducer:** two LG M50T cells in series, 70% charge, 23 °C, 1 A for 1 s. Actual port voltage: **7.7653 V**; the returned parts list selects **Geekworm X1205 2-cell UPS HAT** and included battery protection; design warnings are empty. The same lookup also applies to arbitrary custom cells. Expected: this schematic cannot inherit a compatible battery-side board/protection assignment merely because it contains two cells. Geekworm lists the X1205 for its 3.7 V 21700 battery arrangement, and does not document the drawn series pack as supported. [Official X1205 documentation](https://wiki.geekworm.com/X1205)

**Fix:** separate a priced candidate from a compatible selected component. Require explicit battery voltage/topology, cell form/chemistry, maximum battery current and charger compatibility. If those attributes are unknown, retain the price as a reference and mark compatibility/protection unassessed; do not silently include a working protection solution. One- and three-cell cases also need this treatment because they currently fall back to the four-slot X1206.

**Acceptance:** 2S, mixed topologies, non-21700 custom cells, excessive power, and unsupported cell counts return unknown/incompatible status and do not imply fitted protection. A supported 1S2P selection retains the X1205 price with its unresolved limits shown. Receipt: `count_only_parts`.

### E3 — Medium: the proposed board has an unassessed charge path, and its 95% figure is attributed to the wrong power path

**Confirmed source/location and model behavior; actual board operating point is conditional.** `reports/design_study_v2/RECOMMENDATION.md:33`, its generator `scripts/write_recommendation.py:45`, and `src/voltforge/studio/loads.py:40` place the board's efficiency claim beside the backup calculation. On Geekworm's page, 95% appears under **Power Input**, alongside the **9–18 V step-down converter**, not as a measured battery-to-Pi boost curve. The same page advertises charging up to 3 A. Neither is a measured operating point for this design. [Official X1205 product features](https://geekworm.com/products/x1205)

The deployed LG rule is 1.455 A charge current per cell at 23 °C (`src/voltforge/models/cell_catalogue.py:139`). Two perfectly sharing cells at the board's advertised 3 A would each receive 1.5 A, **3.1% above that rule**. A 3 A, 23 °C, two-cell charge probe correctly refuses with that limit. Unequal sharing reduces the permissible total further. This does not prove the board actually charges at 3 A in the intended configuration, and does not overturn the discharge study; it proves that the advertised maximum is not automatically compatible with its modeled cell limits.

**Fix:** call 85/90/95% explicit backup-efficiency scenarios, without using the input-converter claim as their evidence. Add a separate board charge/protection compatibility row: actual charge setpoint/tolerance, branch sharing, termination behavior, sensed temperature, and controlled shutdown threshold. At equal sharing, 2.91 A is the deployed 23 °C aggregate ceiling; it is not a recommended setpoint without margin. The documented 2.4 V board cutoff is below the model's 2.5 V cell cutoff and below the mission's 3.3 V floor; those are three different conditions. The maker's charger-chip thermal shutdown also does not establish a cell-temperature charging window. [Official cutoff and temperature FAQ](https://wiki.geekworm.com/X1205)

**Acceptance:** a reviewable board specification maps backup input current, charger output current, cell current, and each cutoff to its actual sense node. Unknown settings remain unknown; a simulated ideal 7 A-per-cell/3.3 V/45 °C switch is not substituted for hardware limits. Receipt: `board_three_amp_charging`.

### E4 — Medium: charging Ah is multiplied by series count

**Confirmed.** `src/voltforge/studio/temperature_engine.py:320` calculates `charge_gained_Ah=-charges.sum()/3600`; `src/voltforge/studio/report.py:104` displays it as “Charge gained.” Summing cell coulombs gives aggregate cell-Ah, not charge received at the pack terminals.

**Reproducer:** two identical cells in series, charging at 1 A for 600 s. Actual: **0.333333 Ah**. Expected pack-input charge: **0.166667 Ah**; each cell independently gains that amount. The supplied result is twice the pack value. This does not affect the correctly integrated terminal-energy quantity.

**Fix:** integrate negative external terminal current for gross pack charge received; report net charge and per-cell changes separately where useful. If retaining the present sum, label it explicitly as aggregate cell-Ah and do not present it as pack charge.

**Acceptance:** 1S, 2S, 2P, and 2S2P at the same terminal current/time have the same pack-input Ah; per-cell Ah differs according to topology. Mixed charge/discharge cycles distinguish gross received Ah from net change. Receipt: `series_charge_ah`.

### E5 — Medium: an unknown ideal-wire current is displayed as zero

**Confirmed.** Zero-ohm links are contracted by the circuit solve, and row currents correctly remain `None` (`src/voltforge/studio/temperature_engine.py:169`). The link summary then applies `value or 0` at line 329 and reports a calculated zero peak current.

**Reproducer:** identical two-cell parallel ladder, both output terminals at cell 1, zero-ohm links, 2 A load. Each cell delivers 1 A. Both links must carry cell 2's 1 A in this simple tree, but the rows contain `null` currents and the link checks show **0 A** for both. Zero resistance implies zero resistive loss, not zero current.

**Fix:** preserve unknown current/density as null with a reason, or recover ideal-link current where unique. Do not invent a unique current for loops of ideal wires where it is indeterminate.

**Acceptance:** the simple ladder reports 1 A or explicitly unknown; ideal-wire loops remain unknown unless additional impedance fixes the distribution; finite-resistance links retain their calculated current. Receipt: `ideal_link_unknown_as_zero`.

## What the two-cell recommendation does and does not establish

The requirement chain is readable: a 5 V/5 A Pi supply envelope motivates **25 W**; the 600 s mission requires **4.1667 Wh at the load**, or **4.6296 Wh at the converter input** at constant 90% efficiency. The official Pi page supports its supply recommendation, not a measured gateway draw. [Raspberry Pi 5 specifications](https://www.raspberrypi.com/products/raspberry-pi-5/)

`src/voltforge/studio/loads.py:29` converts that envelope to **8.4175 A at the battery port**, not 5 A at each cell. At equal sharing, two cells carry 4.2088 A each. The recommendation reports a 5.33 A worst required branch value for the opposite-output layout, distinct from the board's 6 A **5.1 V output** specification. The latter cannot be used as a 6 A battery-current rating.

| Claim | Assessment and usable wording |
| --- | --- |
| Two cells are the smallest qualifying design among the tested parallel arrangements | **Defensible under the frozen protocol.** Required tiers, model, initial charge, 23 °C conditions, current approximation and limits must accompany it. One cell was refused under the deployed conservative limit, rather than shown to be physically incapable under every possible cell/temperature/converter choice. |
| The 8.42 A case covers 25 W | **Conditional.** While input voltage is at least 3.3 V and efficiency at least 90%, `25/(eta*V)` is no greater than 8.42 A. This is an upper bound on demanded pack current, not a proof that every nonlinear mismatch/thermal response is ordered. The saved nominal 48-step, three-iteration check peaks at 7.8099 A and supports that one case; it is not a live constant-power converter simulation of every mismatch case (`scripts/run_engineering_checks.py:102`, `reports/engineering_checks_v1/result.json:248`). |
| Two cells halve cost and mass compared with four | **Defensible for listed cells only:** INR 4,824 to INR 2,412 and 280 g to 140 g. The listed LG cells were out of stock; the catalogue already records that. Copper is an indicative material rate, currencies remain separate, and board/assembly/availability costs do not reduce by the same fraction. Do not turn historical listed prices into a live purchasable BOM. |
| Opposite-end output is better | **Conditional refinement.** The study reports a smaller worst required current and also 35/81 paired current increases; preserve both. Same-end also qualifies. A fixed board's actual traces, contacts and spring resistance have not been shown equivalent to the drawn copper links. |
| Three cells survive losing a cell | **Narrow to a candidate N-1 design.** `RECOMMENDATION.md:34` itself says the tests cover weak cells rather than lost cells. Deleting one ideal cell is different from an open shared ladder segment, shorted cell or high-resistance contact. Test each declared fault topology before claiming survival. |
| Temperatures are a useful sensitivity range | **Defensible as scenario outputs, not a measured prediction interval.** The range has no stated probability or coverage. Halved/doubled thermal parameters and entropy variants help assess the chosen decision but do not identify a new enclosure's heat transfer. |

The study's required tiers vary mismatch, thermal assumptions and efficiency separately, with a few declared combinations. The randomized combined electrical cases and the 12 A stress mission are explicitly reported-only (`configs/round1_design_study_v2.json:50`). Thus “all required cases passed” is precise; “all plausible uncertainties jointly passed” is not. If stronger robustness language is needed, freeze a small joint matrix of weak cells, lower efficiency, warm ambient, reduced cooling and aged contacts before running it. Preserve the existing frozen study.

## Numerical consistency, accuracy and thermal identifiability

Eight inspected, local tests passed: three variable-resistance charge/discharge cases, a non-rested charge reversal, reversible/conductor heat bookkeeping, a mutation that makes the old heat formula fail, persistent circulating current after external disconnection, and a pending disconnect that must not be reported as actuated after an early stop. The independent synthetic ordering probe also preserved terminal voltage exactly. These are worthwhile software/model-consistency controls.

The V4 energy path separately accounts for cell polarization work, ohmic loss, conductor heat deposited in cells, conductor/output-route loss outside cells, reversible heat and ambient exchange. First-law closure therefore checks that the chosen equations agree numerically. It does **not** establish that lookup voltage, polarization, entropy, cooling, or the lumped cell temperature match the actual hardware. A separate model using the same constitutive assumptions is also a numerical reference, not a lab validation.

The saved measurement result is unambiguous: **all 12 cases fail both the declared voltage and temperature bands while all 12 first-law checks close** (`reports/measured_comparison_v1/final/result.json:33`, repeated for each case). No raw measurement or reserved outcome was reopened here. Current-sharing checks also miss their declared busiest-cell criterion (`reports/engineering_checks_v1/result.json:6`). Preserve these misses beside any improved visual or software-test claim.

The LG thermal defaults declare 58.5 J/K from literature and 0.15249 W/K from exposed fixture cooling, and their own provenance acknowledges that equilibrium offset/internal heat and individual contacts are not separately identified. A cooling transient primarily constrains time scale `C/G`; the chosen literature C and measured ambient make the fitted G conditional. Source shell-temperature sensing is not identical to a single core/whole-cell model state. Cell-to-cell thermal coupling, board heating, enclosure airflow and contact heating transfer remain assembly assumptions.

The extra error-budget result compares **0.17022 V** optimistic error with **0.19668 V** simulated margin, leaving only **0.02646 V** after that subtraction. This is useful diagnostic arithmetic, not a guaranteed bound transferred from a 4P fixture to the proposed 2P assembly. Likewise, multiplying one scenario's rise by the largest observed ratio **2.268** gives 42.45 °C, but that ratio is not an established envelope across new geometry, current, SOC or cooling. These are conditional sensitivity arguments; label them that way. No tuning from these failed comparisons is recommended.

## Reproduction and limits of this review

Commands were run with `C:/Users/DELL/anaconda3/python.exe`. Python 3.12.3 and the six checked direct/test versions match the requested numerical stack: NumPy 1.26.4, SciPy 1.13.1, pandas 2.2.2, matplotlib 3.9.2, openpyxl 3.1.5 and pytest 7.4.4. Fourteen transitive packages differ from the full macOS lock (including contourpy, packaging, pillow, pluggy, python-dateutil and tzdata). This is **exploratory reproduction on Windows**, not a sealed full-lock replay. No runtime/dependency installation was performed.

The direct probe command was:

```powershell
& C:\Users\DELL\anaconda3\python.exe C:\Users\DELL\Desktop\volt-forge\reports\round1_review_20261031\electrical\reproduce_electrical.py --repo C:\Users\DELL\Desktop\volt-forge\tmp\round1_review_20261031\repo --out C:\Users\DELL\Desktop\volt-forge\reports\round1_review_20261031\electrical\receipt.json
```

The script refuses to overwrite a receipt; use a fresh `--out` path when repeating it. Inputs and actual outputs are stored in [receipt.json](electrical/receipt.json). The inspected pytest selection and result are recorded in [selected_tests.txt](electrical/selected_tests.txt): **8 passed in 9.80 s**. Test selection: `tests/test_first_law.py::{test_budgets_close_when_branch_resistance_falls_with_charge,test_budgets_close_through_charge_reversal_and_a_non_rested_start,test_budget_keeps_reversible_heat_and_conductor_heat_on_their_own_terms,test_first_law_check_fails_on_the_v3_resistor_heat_form}` and `tests/test_virtual_protection.py::{test_external_disconnect_does_not_erase_internal_parallel_current,test_delayed_action_after_model_stop_is_not_reported_as_actuated}`, with third-party pytest plugin autoload and pytest caching disabled.

Exact test invocation, from the isolated V4 checkout (the transcript was saved separately):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& C:\Users\DELL\anaconda3\python.exe -m pytest -q -p no:cacheprovider tests/test_first_law.py::test_budgets_close_when_branch_resistance_falls_with_charge tests/test_first_law.py::test_budgets_close_through_charge_reversal_and_a_non_rested_start tests/test_first_law.py::test_budget_keeps_reversible_heat_and_conductor_heat_on_their_own_terms tests/test_first_law.py::test_first_law_check_fails_on_the_v3_resistor_heat_form tests/test_virtual_protection.py::test_external_disconnect_does_not_erase_internal_parallel_current tests/test_virtual_protection.py::test_delayed_action_after_model_stop_is_not_reported_as_actuated
```

Only these fresh review artifacts were written. No full measured pipeline, full study rerun, model adjustment, reserved-data inspection, network AI call, or external message was performed.

## Reusable electrical reviewer prompts

**Power-system engineer:** “Trace the requirement from device power and mission duration through converter input voltage/efficiency to pack and individual-cell currents. Identify where a source applies to a different voltage rail or direction. Audit cold/hot starts, low SOC, load steps, equalization current, cutoff sense nodes, charger limits and failed contacts. Use the pinned model and frozen outputs; do not tune or reopen reserved records. For each issue provide exact input, expected/actual behavior, severity, source basis, minimal correction and an acceptance check. Preserve conditional simulation conclusions that are supported.”

**Electrothermal verification engineer:** “Separate conservation, convergence, constitutive-model validity and measurement agreement. Inspect charge/energy balance through reversal, rest, series/parallel topology, ideal wires and protection events. Explain which thermal parameters are identified and which are assumed; test invariance and unknown-versus-zero semantics using synthetic fixtures. A closed first law is not measured accuracy. Report falsifiable results and the runtime used; do not change model values from assessment outcomes.”

**Component and protection reviewer:** “Audit the BOM as an electrical system. Treat cell count, series/parallel topology, chemistry, geometry, voltage range, charge/discharge limits, cutoff locations and thermal sensing as separate compatibility fields. Keep historical price, live availability and compatibility separate. Verify manufacturer claims at their original power path. Do not turn missing thresholds or untested board settings into passes, and do not equate an ideal simulated disconnect with certified hardware.”
