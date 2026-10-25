# Standalone thermal mathematics works; M50T thermal prediction remains unsupported

26 October 2026. **Keep the LG electrical models and thermal-unavailable editor
behavior unchanged.** A standalone, synthetic-only one-node heat-balance
prototype is implemented and verified. No cell or module thermal parameter was
fitted, selected or adopted. The present evidence is insufficient to predict
our four-cell module's temperatures or make thermal design/safety decisions.

## What was built and checked

The [declared procedure](PROCEDURE.md), [configuration](../../configs/thermal_feasibility_v1.json)
and [source audit](SOURCE_AUDIT.md) precede the demonstration. Parent review
approved synthetic analytical work without an experimental-analysis freeze,
because no new measured outcomes are consumed. Their hashes, source/test hashes
and generated-output hashes are in [run_001/manifest.json](run_001/manifest.json).
The procedure/configuration did not change after the run. Plot review corrected
the rendering of instantaneous boundary heat-flow jumps; numerical outputs and
input assumptions were unchanged. The final plot and implementation are hashed.

The exact equation is

`C_th*dT/dt = Q_prescribed - H*(T - T_ambient)`.

C_th is a positive **lumped heat capacity in J/K**, not specific heat in J/kg/K
or electrical capacity in Ah. H is a nonnegative conductance in W/K. For each
constant-input interval with H>0, the endpoint is

`T(t) = T_ambient + Q/H + (T0 - T_ambient - Q/H)*exp(-H*t/C_th)`.

For H=0, `T(t)=T0+Q*t/C_th`. The implementation evaluates a stable equivalent
form near H=0. Each interval also has an exact heat-flow integral. Temperatures
and cumulative energies stay continuous when prescribed heat or ambient changes;
instantaneous heat-flow rates can jump. A reported transition sample uses the
new interval's inputs. Negative outward boundary heat means the environment is
heating the node. Negative prescribed heat is permitted. Q excludes the H
exchange, so that exchange is not subtracted twice.

Every physical input is mandatory. The CLI rejects missing/unknown fields,
automatic electrical coupling, real-cell attribution, unsupported model labels,
nonfinite or invalid parameters, noncontiguous profiles and excessive reporting
grids. A profile crossing absolute zero stops without clipping. These numerical
domain checks are not a battery operating envelope.

**39 synthetic tests pass.** They cover independent closed-form values, signed
heating/cooling, H=0 and its small-H limit, zero heat/duration, equilibrium,
continuity across input events, energy conservation, independent Simpson
quadrature of boundary heat, reporting-grid invariance, parameter-scale
nonidentifiability, invalid configurations, export/replay and tamper detection.
The [verification receipt](verification.json) replays all 242 exported rows and
checks provenance hashes; it is reproducibility evidence, not an independent
experimental test. No battery measurements are loaded by this implementation.

## Predeclared synthetic demonstration

The arbitrary C_th=100 J/K and H=0.5 W/K are arithmetic examples with **no
established applicability to M50T, P45B or another real cell**. T0=25 degC;
the full prescribed profile is retained:

| Interval (s) | Prescribed heat (W) | Ambient (degC) |
| --- | ---: | ---: |
| 0-120 | +2 | 25 |
| 120-300 | 0 | 25 |
| 300-360 | -1 | 25 |
| 360-480 | 0 | 30 |

| Synthetic output | Result |
| --- | ---: |
| Final lumped-node temperature | 27.2697816066 degC |
| Signed prescribed-source energy | 180.0000000000 J |
| Signed outward boundary energy | -46.9781606552 J |
| Stored-energy increase | 226.9781606552 J |
| Maximum absolute energy residual, both grids | 4.13e-13 J or less |
| 10 s / 2.5 s rows | 49 / 193 |
| Maximum temperature difference at all 49 shared timestamps | 0 degC |

The warmer environment supplies net heat late in the run, so stored energy can
exceed prescribed-source energy without violating conservation. The exact
interval solution makes output-grid density independent of integration accuracy;
this check is not evidence about discretization of a spatial thermal model.
The [inspected plot](run_001/synthetic_heat_balance.png), [series](run_001/series.csv)
and [summary](run_001/summary.json) retain the synthetic label and units.

## What real evidence exists, and what it does not provide

Exact LG M50T primary literature and a public dataset lead exist. Marzook et al.'s
base cooling coefficient relates heat rejection to **cap-to-base** temperature
difference under a defined fixture. It cannot replace our unknown node-to-ambient
H. See the [primary paper](https://doi.org/10.1016/j.est.2022.105217) and the
parameter-by-parameter [source audit](SOURCE_AUDIT.md).

The [author's public archive](https://zenodo.org/records/6421061) is the next
concrete data lead. Only landing-page metadata was inspected. No archive was
downloaded and no raw outcome was opened. We cannot yet say its transients,
heat estimates, calibration or preparation metadata suffice for identifying
this model. Even adequate fixture data would establish support for that
specified laboratory case, rather than our unspecified module cooling case.

Li et al.'s [M50T distributed model manuscript](https://spiral.imperial.ac.uk/server/api/core/bitstreams/34e87deb-b30b-414b-8002-31cf6f4f839a/content)
explicitly models spatial heat flow and reversible heat. Its constituent
thermal properties are not a directly measured whole-cell heat capacity for
our specimens. We do not transfer them, a similar-chemistry entropy curve,
P45B values, or generic M50 properties into this prototype.

The existing electrical solver separately accounts for R0, R1 and rail resistor
losses, and the fitted RC state's energy. That accounting is useful but does
not identify total electrochemical cell heat, reversible/entropic heat,
reaction/mixing contributions, heat from preparation/history or transfer of
external rail heat into cells. A fitted RC capacitor's circuit energy is not
a demonstrated thermochemical energy store. Neither reference-voltage fidelity
nor electrical conservation closes these physical evidence gaps.

## Identifiability and the next engineering action

Identification is possible **conditionally**, not from our present thermal
inputs. In an ideal one-node experiment, a known calibrated heat input and
time-resolved representative temperature plus ambient can identify C_th and H
when the transient is sufficiently excited. Cooling alone identifies their
ratio H/C_th; steady temperature with known heat identifies H, not C_th.
If heat magnitude is also unknown, multiplying C_th, H and Q by one common
factor gives exactly the same temperature trace. A synthetic test demonstrates
that structural ambiguity. Numerical optimization cannot remove it.

The minimum next evidence package must contain:

1. Exact M50T specimen/batch identity and mass, history/age, SOC definition,
   charge/discharge preparation, rest/thermalization and the temperature range.
2. Calibrated synchronized temperature histories with measurement locations,
   uncertainties and a justified definition of the lumped temperature. Multiple
   locations or equivalent evidence must bound relevant internal gradients.
3. The actual environment/cooling history: air or coolant temperature, airflow,
   contacts, insulation, tab/fixture heat paths, geometry and boundary conditions.
4. An independently known heat input/heat flow, or independently supported
   complete heat-generation model. Electrical I/V by themselves do not certify
   the heat source. Preserve uncertainty and any correlations in derived heat.
5. Complete heating and relaxation/cooling records with sufficient duration,
   repetitions and conditions. Declare fitting and untouched assessment
   sequences before opening their outcomes. Choose an application tolerance
   from a specified decision; none is established by this demonstration.

Next, inspect the public archive's **documentation and file inventory first**,
then predeclare an allocation if its identity, calibration and cooling/heat
definitions are usable. Stop before fitting if these cannot be established.
If the archive lacks identifiable heat or relevant transients, another public
dataset or controlled measurements are required. If it only supports its
base-cooled fixture, explicitly narrow a future demonstration to that fixture;
do not call it validation of our module. No more exploratory electrical fitting
resolves this thermal gap.

The one-node approximation cannot determine core/surface differences, hot spots,
cell-to-cell thermal transfer, thermal runaway or safety. A measured bulk model
may still be inadequate for a decision governed by maximum local temperature.
No electrical-model changes, measured thermal fit, thermal product controls,
automatic coupling, outreach or ranking of designs were introduced. All nine
unused LG cells, 48 unused P45B members / 40 families, 13 FreeTwinEV records and
frozen module outcomes remain untouched by this workstream.

## Reproduce

Run from the repository root in PowerShell. Use a fresh output directory; the
script refuses to overwrite an existing run.

```powershell
& C:\Users\DELL\anaconda3\python.exe -m pytest tests/test_thermal_prototype.py -q
& C:\Users\DELL\anaconda3\python.exe scripts/thermal_prototype.py verify reports/thermal_feasibility_v1/run_001
& C:\Users\DELL\anaconda3\python.exe scripts/thermal_prototype.py run --config configs/thermal_feasibility_v1.json --out reports/thermal_feasibility_v1/reproduction_001
& C:\Users\DELL\anaconda3\python.exe scripts/thermal_prototype.py verify reports/thermal_feasibility_v1/reproduction_001
```

For a student: we can now check how a simple object warms and cools when its heat
input and cooling properties are given. We have not measured those properties
and heat inputs for this battery module. The next step is to qualify the public
M50T thermal data and its test setup, before adding temperature predictions to
the editor.
