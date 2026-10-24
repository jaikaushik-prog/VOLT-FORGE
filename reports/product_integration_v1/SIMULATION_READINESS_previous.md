# Four-cell electrical simulation readiness

25 October 2026. **The command-line simulation and measurement-comparison backend
works and passes 75 tests. Experimental module validation is awaiting suitable
measurements.** Every supplied scenario returns **requirement not configured**
for the missing load-voltage requirement, and **insufficient evidence** for an
engineering decision. No replacement cell model, optimizer, repair rank,
temperature prediction or experimental battery-performance gain is claimed.

## 1. What now works

`python -m voltforge.simulation` provides four commands:

| Command | Function |
|---|---|
| `configure` | Verify frozen model files; materialize four manual scenarios with fitted parameters, explicit rails, states, temperature assumptions and evidence; hash the declaration before simulation. |
| `simulate` | Run four main cases, 28 one-at-a-time sensitivity scenarios, two paired SOC/reference-origin checks, and 1/0.5/0.25 s integration checks. Save trajectories, losses, energy, coverage and decision status. |
| `compare` | Produce an unranked scenario table and electrical plots; optionally compare a supplied measurement package against one configured main run. |
| `validate` | Preserve original measurement bytes, check the import structure, units, timing, locations, polarity, calibration metadata and current-conservation residuals. |

The [application configuration](configs/module_application_v1.json) specifies
LG M50T NMC cells P7/P17/P19/P13 in position order, a 1s4p same-side-terminal
ladder, 14.55 A for 360 s, and separate resistance values for each of the three
segments on each rail. Initial SOC 0.70 and zero polarization are assumptions,
not measured initial states. Nominal ambient/surface 23 C is an assumed operating
condition supported only by characterization context, not a thermal prediction.
Minimum device voltage, allowed excursion duration and their source are **null**.
The old 3.50 V example and 25 mV proposal are not backend acceptance defaults.

Each [configured scenario](reports/module_simulation_v1/configured/equal_soc.json)
contains the actual extracted, frozen v2 R0/R1/tau/capacity/reference values,
fitting and assessment evidence, assumptions and units. The
[configuration manifest](reports/module_simulation_v1/manifest.json) binds source
model files, scenario inputs and exported C/20 sensitivity data by hash. Source
values, fitted parameters, proposed service and unverified physical assumptions
are labelled separately.

The original `models/coupling.py` is itself protected by the previous preservation
lock. The [versioned extension](src/voltforge/models/coupling_v2.py) reuses its
ladder solver and preserves its held-current state convention. The frozen file
and the v2 cell models remain unchanged. This extends the software backend; it
does not reopen the completed reference/initial-state modelling investigation.

Each trajectory records SOC, polarization, reference voltage, branch current,
cell voltage, both sets of node potentials, each rail drop/current/loss, terminal
power, delivered/received energy, resistor losses, equivalent-capacitor storage,
and numerical conservation residuals. Negative module current charges the module;
internal circulating currents can exist even at zero module current.

## 2. What has been checked mathematically

The model equations use discharge-positive current:

```text
cell voltage = rested-reference(SOC) - polarization - R0 * branch current
dSOC/dt = -branch current / (3600 * capacity_Ah)
dpolarization/dt = (R1 * branch current - polarization) / tau
R0 loss = R0 * current^2
R1 loss = polarization^2 / R1
equivalent polarization capacitance = tau / R1
stored polarization energy = 0.5 * (tau/R1) * polarization^2
rail loss = segment resistance * downstream-current^2
```

The static ladder solves all branch currents and shared rail drops together.
SOC integration and polarization updates use each interval's held branch currents.
Polarization updates and integrated R1 resistor losses are exact under that
assumption. Load changes are integration boundaries. Delivered energy uses
trapezoidal terminal power with the endpoint solution under the **old** load
before a change; a discontinuity is never smeared across the integration interval.

Reference-source work integrates the reference curve along the held-current SOC
trajectory. It is electrical-model bookkeeping, not measured chemical energy:
the reference is not proven equilibrium OCV. The finite-step source-work minus
terminal-energy/loss/storage residual is reported rather than forced to zero.
Calculated equivalent-circuit resistor dissipation is not a prediction of actual
heat partition, surface temperature or core temperature.

The [test record](reports/module_simulation_v1/pytest.xml) has **75 passed, zero
failures or skips**. New tests include closed-form symmetric RC voltage and
energy, arbitrary initial polarization, charging/rest/discharging transitions,
circulating currents, node/drop relationships, source-work/loss/storage accounting,
legacy-coupling equivalence, domain stops, importer failures and an end-to-end
test of all four CLI commands. The synthetic analytical RC comparison is separate
from the generated importer fixture.

For the four 360 s main cases at 0.25 s:

- Maximum KCL residual: 1.8e-15 A; maximum total charge-accounting residual:
  2.1e-10 A s; instantaneous full power-balance residual: below 2.5e-14 W.
- Reducing the step from 1 s to 0.25 s changes terminal voltage by at most
  **0.00792 mV**, branch current by **0.00238 A**, and delivered energy by
  **2.74e-6 Wh** on common sample times.
- At 0.25 s, the largest final integrated energy-balance residual magnitude is
  **6.04e-7 Wh**. Residual cancellation can make individual cases nonmonotonic
  across steps; all step results are retained. This is not a physical error bound.
- Paired +/-0.02 SOC/reference-origin relabelling leaves the tested baseline
  voltage and branch currents unchanged at stored precision.

See [software verification](reports/module_simulation_v1/software_verification.json).
These checks establish numerical consistency, not experimental accuracy.
The [release verification](reports/module_simulation_v1/release_verification.json)
records file hashes, test counts and the unchanged baseline/archive checks;
reproduce it with `python scripts/verify_simulation_release.py` after the full
demonstration and its JUnit test record have been generated.

If a state would leave SOC/reference support, the integrator stops at the last
supported sample and records the attempted state and first predicted boundary
time. It saves partial results; it never clips SOC or extends the voltage curve.
No reference extrapolation option is supplied. Mathematically supported but
experimentally unverified waveform transfer is explicitly permitted and flagged
for these research scenarios.

## 3. Scenario results and experimental support

The [scenario declaration](configs/module_scenarios_v1.json) and
[plan](SIMULATION_PLAN.md) precede these outputs. Cases appear in declared order,
not in performance rank. Every numerical entry below is a **simulation**.

| Manual case | Peak branch [A] | Minimum terminal [V] | Mean delivered power [W] | Delivered [Wh] | R0 / rail / R1 loss [Wh] |
|---|---:|---:|---:|---:|---:|
| Equal SOC, 14.55 A | 4.6669 | 3.6332 | 53.689 | 5.3689 | 0.1318 / 0.0338 / 0.1000 |
| Prior SOC imbalance | 5.3528 | 3.6337 | 53.697 | 5.3697 | 0.1336 / 0.0315 / 0.1016 |
| Hypothetical 0.5 mOhm rail segments | 4.2345 | 3.6454 | 53.862 | 5.3862 | 0.1313 / 0.0177 / 0.0993 |
| Reduced load, 12 A | 3.8599 | 3.6841 | 44.765 | 4.4765 | 0.0897 / 0.0229 / 0.0680 |

Minimum cell voltage equals minimum terminal voltage in these discharge cases
because position 1 shares the terminal nodes; all node voltages are still
reported. See the [complete comparison](reports/module_simulation_v1/COMPARISON.md),
[machine-readable table](reports/module_simulation_v1/comparison.csv),
[imbalance electrical plot](reports/module_simulation_v1/runs/soc_imbalance/electrical.png)
and [node/power plot](reports/module_simulation_v1/runs/equal_soc/nodes_and_power.png).

Reduced load supplies **1.200 Ah instead of 1.455 Ah**, and about **16.62% less
terminal energy** in this calculation. Its higher voltage and lower losses come
with reduced delivered service; they are not an unconditional improvement.
The rail change is hypothetical until construction, contact resistance, current
carrying capability and temperature behaviour are established. The roughly
12 mV terminal-voltage difference does not establish a real repair advantage.

Experimental evidence is limited to the already-characterized individual cells
and the frozen v2 fit/assessment records. The previous 9.55 mV headline applies
only to its specified single-cell SOC/current/temperature subset; full-record
fresh-cell maxima reached about 97 mV. Those errors are not module error bounds.

Every cell's run summary retains fitting current ranges/dwell spans and
assessment protocol, SOC and temperature ranges separately. It records intervals
by direction and current band, out-of-subset durations, initial assumptions and
temperature evidence. The current/reference curve's mathematical support never
becomes an experimental waveform-support flag. Even the baseline, whose peaks
stay below 4.9 A, returns **unsupported transfer** for every branch.

In the imbalance case P7 stays above 4.9 A for approximately **19.25 s**. The
observed calibration excursions above 4.9 A last about 9.9 s; the sustained
characterization plateau is about 4.85 A for six minutes. An amplitude lying
between observed values does not validate this waveform or duration. Rail and
temperature assumptions create additional unsupported transfer.

## 4. Sensitivity and decisions still unsupported

Seven separate sensitivities apply to every manual scenario: relative initial
SOC +/-2 percentage points, capacity +/-1%, polarization +/-5 mV, and the
previously investigated C/20-shape reference with the same rest anchors.
These are **sensitivity scenarios**, not calibrated confidence intervals or
guaranteed bounds. RC parameters are unchanged. Capacity changes affect charge
integration at a fixed reference coordinate; they are not a re-estimation of
the original capacity/reference calibration.
Each offset or capacity multiplier acts commonly on all four cells. This small
set does not cover all independent per-cell extremes or combinations of the
manual rail/load changes with the imbalance case.

Relative SOC changes hold the reference fixed. Paired origin shifts move both
SOC and reference labels together and are reported separately as coordinate
checks, not additional physical uncertainty. No joint distribution or independent
combination of SOC, capacity and reference errors is assumed.

Across nominal and one-at-a-time cases, baseline minimum terminal voltage spans
**3.6109-3.6552 V**. Imbalance peak current spans **5.3107-5.3993 A**, with
**17.5-21.25 s** above 4.9 A. Thus the imbalance coverage concern persists across
the declared sensitivities. The signs of the reported manual-case contrasts do
not change in this small set. That does not establish robustness to unexamined
states, thermal histories, model-form error or actual interconnect uncertainty.
The reduced-load case always delivers less energy than its matched baseline
(approximately **0.887-0.898 Wh less**).

See [sensitivity plot](reports/module_simulation_v1/sensitivity_scenarios.png),
[all cases](reports/module_simulation_v1/sensitivity_comparison.csv), and
[matched contrasts](reports/module_simulation_v1/sensitivity_contrasts.json).
No score combines these quantities into an optimum or repair rank.

The missing load/device minimum voltage and permitted excursion duration produce
**requirement not configured**, not a pass. Even if a user later supplies a sourced
requirement, this version only reports a finite-step simulated excursion screen;
it cannot grant experimental acceptance. The simulation stops remain distinct
from coverage warnings. None of this resolves the independent disagreement
between module and summed branch current measurements. Both uncertain sources
remain unchanged.

## 5. Real-data validation and minimum next evidence

The [measurement import specification](MEASUREMENT_IMPORT_SPEC.md) documents all
15 required current/voltage/temperature channels, original source rows, separate
channel timestamps when needed, units, polarity, defined node locations, sensor
IDs, preparation history and calibration/synchronization metadata. The importer
keeps original bytes, calculates current-sum residuals and reports missing
evidence. It never rescales a channel to enforce conservation or shifts it to
improve prediction error.

The [synthetic ingestion record](reports/module_simulation_v1/synthetic_ingestion/validation.json)
and [synthetic comparison](reports/module_simulation_v1/synthetic_comparison/comparison.json)
demonstrate the workflow. A generated fixture adds a known +10 mV to simulated
voltage readings; the comparison recovers -10 mV prediction-minus-fixture bias.
This tests plumbing only. Its explicit synthetic label leaves experimental
validation at **awaiting suitable measurements**. No protected module outcome
was opened to demonstrate import.

Minimum external evidence remains:

1. The actual load or converter input-voltage requirement, allowable excursion
   duration and consequence of false clearance, with a documented source.
2. Traceable module and branch-current calibration/conversion, sensor-position
   mapping, timing/filtering evidence and an independent current reference that
   can resolve the existing discrepancy. The existing author packet remains unsent.
3. Suitable synchronized measurements at the modeled electrical nodes, measured
   rail/contact resistances, temperature observations, and documented initial
   charge/rest preparation for the intended waveform and relevant imbalance.
4. A sourced uncertainty budget and a prospective allocation of complete
   measurement sequences before using new outcomes for fitting or acceptance.

The [lab brief](reports/reference_initial_state_v1/LAB_REQUEST.md) remains prepared
and unsent. All nine unused characterization cells and frozen module assessment
outcomes remain preserved. The 112 protected original/v1/v2 artifacts, frozen
investigation procedure and original archive retain their hashes. No repository
publication or frontend/optimizer work was performed.

## Reproduce the demonstration

From `C:\Users\DELL\Desktop\volt-forge`, with the existing Anaconda environment:

```powershell
$env:PYTHONPATH = 'src'
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation configure
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation simulate
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation compare
& C:\Users\DELL\anaconda3\python.exe scripts\make_module_fixture.py
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation validate --measurements tests/fixtures/module_synthetic --out reports/module_simulation_v1/synthetic_ingestion
& C:\Users\DELL\anaconda3\python.exe -m voltforge.simulation compare --measurements tests/fixtures/module_synthetic --out reports/module_simulation_v1/synthetic_comparison
& C:\Users\DELL\anaconda3\python.exe -m pytest -q --junitxml=reports/module_simulation_v1/pytest.xml
& C:\Users\DELL\anaconda3\python.exe scripts\verify_simulation_release.py
```

Use `python` instead of the absolute interpreter path in an environment installed
from the existing pinned requirements. First configuration needs the official
archive solely to export the four already-used C/20 sensitivity curves. Later
simulation and comparison use configured artifacts without decoding raw records.
The main-only run option is `simulate --main-only`. It regenerates main runs and
time-step checks; previously produced sensitivity files remain on disk. Use a
new `--workspace` and versioned inputs for a changed declaration. `configure`
refuses a silently changed declaration in an existing workspace.

For a student: the backend now calculates how the four cells share current,
how their voltages change, and how much electrical energy reaches the load or
is dissipated in the circuit model. It also tells us where evidence is missing.
We still need a real, calibrated module test and the load's voltage requirement
before deciding that this module can do the intended job.
