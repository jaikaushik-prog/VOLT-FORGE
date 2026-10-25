# Reference/origin investigation: procedure before numerical analysis

25 October 2026. This is a no-fit investigation of previously opened evidence.
It does not change parameters, install a replacement reference, identify a new
SOC origin or consume unused assessment outcomes.

## Documentation inspected before specifying the calculation

The already-read paper (SSRN 6861858, PDF page order) defines SOC using nominal
4.5 Ah and a fresh cell equilibrated in the charging direction at 4.2 V and
25 degC (pp.9,17). Page 53 uses SOC0=1, h0=-1 and isothermal setpoint conditions
for discharge reproduction; those are simulation assumptions. Page 16 says the
reference branches come from continuous loaded C/30 data and may lack fidelity
for extended rest. Page 14 describes batch screening and different representative
cells for experiments but does not map each released filename to a physical cell
or provide its preceding preparation trace. The README delegates experimental
details to the paper. These are documented definitions, not proof that a released
record's initial state was independently measured.

Use only saved C/30 discharge, GITT discharge and previously used 1C discharge
measurements, existing GITT segmentation and the opened base parameter table.
Paper pages 9,12,14-17,42,53, format documentation and release README are already
used contextual evidence. Do not open other paper outcomes or source members.
All 48 unused P45B members / 40 families, charge table, validation workbook,
nine LG cells, 13 FreeTwinEV records and protected module outcomes remain protected.

## Fixed calculations, without fitting

Recompute nominal charge coordinates for each complete source record using
4.5 Ah with both left-held and trapezoidal current integration. Use exactly two
record-start assumptions, SOC0=1 and SOC0=0.995. This yields four declared
scenarios. The -0.005 shift remains the earlier linked origin/reference-coordinate
sensitivity, not an independently estimated SOC error. No offset, capacity,
origin, curve or initial polarization is selected against voltage. No optimal
SOC shift is computed, even as a diagnostic. Do not invert reference voltage
to infer starting SOC. Do not impose cross-record cell/preparation equivalence.

At each original timestamp, query the published discharge reference at that
scenario's nominal SOC and exactly 25 degC. Report reference minus measured
voltage, sample/time RMSE, bias, extrema and support status. These differences
are **not dynamic prediction errors**: C/30 is loaded, 1C includes substantial
load response, and GITT includes pulses and finite recovery. Preserve complete
records and source lines. Stop on nonfinite input, nonincreasing time, changed
hashes, the existing max(120 s, 10*median dt) acquisition-gap rule, or reference
domain violation. A domain violation stops reference evaluation for that record
and scenario; preserve remaining measured rows with undefined-reference flags,
then continue independent records/scenarios. Do not silently clip or extend.

For all 32 complete GITT pulse/rest pairs, report the final 60, 300 and 600 s
windows of each full rest. A window requires at least three samples, at least
80% of its declared duration, and at least that much actual rest; otherwise
mark it unsupported without extrapolation. For each supported window report
source-line boundaries, sample count/span, measured median, median discharge
reference, residual metrics and ordinary least-squares voltage drift in mV/min.
Also compare the final 300 s median with the preceding 300 s median. Retain the
entire rest; windows are diagnostics, not train/test splits or deleted samples.

No drift threshold certifies equilibrium. A near-zero measured slope could be
limited by resolution, noise, sampling or a slower process. A nonzero slope
shows continued change over that window, but it is not a calibrated uncertainty
bound or a unique mechanism. Do not extrapolate a rest to infinite time.

For context at the used 1C final charge coordinate, report adjacent-sample C/30
loaded interpolation and adjacent-pair GITT finite-rest-median interpolation
under the same scenario's nominal convention. Allow only contiguous decreasing
coordinate brackets; no extension, reversal bridging, missing-point bridging or
voltage-derived alignment. Record exact supporting source lines and keep the
unverified cell/preparation-equivalence assumption visible. These comparisons
cannot establish that the different records describe one physical cell.

## Portable initial-state/reference policy

Implement a separate policy evaluator, not a replacement physical model:

- **Author reproduction:** explicitly requested discharge at nominal 25 degC
  can return SOC=1, h=-1 and zero RC voltages as documented author assumptions.
  Require a record identity. Mark preparation/history unverified and the loaded
  pOCV reference unsuitable for an equilibrium-OCV claim.
- **Declared anchor/history:** require the published anchor definition,
  nominal capacity, a named cell/record, preparation/history source references,
  strictly timed current history from the declared anchor to initial time,
  current polarity and an explicit integration convention. Derive nominal SOC
  from charge only. Require separately declared initial hysteresis/RC states
  and their assumption/model-propagation source before calling the input runnable.
  Source strings and metadata are user declarations, not verified evidence.
  An asserted measured or validated state is rejected as unsupported by this tool.
- **Unknown origin or incomplete history/state:** return missing evidence and
  no usable complete initial state; never substitute a voltage-derived SOC.

Reject unknown fields and voltage-based calibration fields. Validate finite
values, source-time alignment, gap declarations, nominal temperature and
reference support. The evaluator always returns evidence_verified=false; source
identity/calibration and reference compatibility need independent evidence.
Even a declared complete anchor does not establish module accuracy or measured
equilibrium reference support. It is a conditional research input policy.

Export a policy description and exact examples generated from implemented code.
The real three records receive author-reproduction classifications only; no
synthetic metadata is attached to real measurements. A documented-anchor example
uses conspicuously synthetic current/history metadata for software checking.

## Reporting and stop criterion

Freeze this procedure, source allocation, implementation and synthetic tests
before quantifying new windows. Tests cover charge accounting, left/linear
conventions, initial-state field validation, missing versus declared provenance,
voltage-calibration rejection, finite-rest window support, source continuity,
drift/metrics, and reference-domain failure. An independent verifier recomputes
charge coordinates, window statistics, metrics and source preservation. Root's
preservation-aware integration verifier checks the previous release chain.

Plot complete GITT rests chosen by nominal SOC nearest 0.50,0.10,0.04 and the
final pair; show the analysis windows without truncating the rests. Plot all
32 pairs' window/drift diagnostics, plus C/30/reference comparison and the
declared origin/convention sensitivities. Publish all outcomes, including
unsupported interpolations and inconsistent assumptions.

Stop after these declared calculations. If the documented anchor cannot be
connected to each measured record and loaded reference by traceable preparation
and charge history, report the exact missing information. Do not fit a reference
or another dynamic model to erase the mismatch. A policy can be implemented
without claiming its needed real-world evidence already exists. No adoption,
new confirmation access, extra RC, temperature model or lab outreach follows.
Application voltage/excursion requirements remain `requirement not configured`;
affected design decisions remain `insufficient evidence`; experimental module
validation remains `awaiting suitable measurements`.
