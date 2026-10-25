# Bounded low-SOC reference and relaxation diagnosis

Declared before opening either newly allocated experimental record. This stage
diagnoses the shared 1C end-of-discharge miss. It does not fit, replace or extend
the frozen published P45B model or the LG v2 model.

## Access allocation

Release exactly two complete 25 degC development families already proposed at
intake: `MOLICEL_P45B_025degC_Co30_Dch.csv` and
`MOLICEL_P45B_025degC_GITT_Dch.csv`. Each has only experimental time/current/
voltage/temperature columns. Keep all source bytes, names, units and line numbers.
Reuse the already-opened base parameter table and the sealed 1C primary trace.
The other 48 archive members (40 filename families), charge-optimized table and
author validation workbook stay unopened. All protected LG and FreeTwinEV
records remain protected. These characterization records may have contributed
to the authors' fit; they are development evidence, not fresh validation.

## Charge coordinate and sampling

Retain charge-positive source current. Compute both trapezoidal and left-held
cumulative current, with nominal 4.5 Ah and assumed SOC=1 at the first recorded
sample. Primary diagnostic coordinate is trapezoidal; the prior 1C run remains
unchanged and uses its saved SOC. This coordinate choice is declared from the
previous author-comparison finding, not selected from these outcomes.
Never fit an initial state, capacity, time shift or voltage offset. State that
cross-record cell/preparation equivalence is unverified.

Validate finite experimental values and strictly increasing timestamps. Do not
sort, delete or repair measurements. Report time-interval distributions. Mark an
interval longer than max(120 s, 10 times median interval) as a possible acquisition
gap. The 120 s floor accommodates the documented C/30 schedule of up to one
minute; it is a diagnostic rule, not proof of complete acquisition. Do not bridge
a flagged gap in charge integration or error weighting. SOC becomes unknown
beyond the first such gap; preserve later voltages and times without reinitializing.

Classify each sample using rest abs(I)<=0.05 A, discharge I<-0.05 A, charge I>0.05 A.
Keep every contiguous segment and split at possible gaps. No merging short rests,
discarding pulses or random timestamp splits. Segment durations are observed
last-minus-first timestamps; report adjacent transition timing separately.

## Predeclared diagnostics

1. Inventory full duration, current/temperature ranges, direction segments,
   integrated charge, source endpoints and first observed 2.5 V discharge crossing.
   The latter is a characterization-protocol reference, not a device requirement.
2. Query the unchanged 25 degC **discharge** reference at each known nominal SOC
   strictly inside its table support. Flag temperature deviations over 1.5 degC
   and unsupported SOC; no lookup extension or clipping. Compare the table
   reference with measured C/30 loaded voltage. This is a reference-consistency
   diagnostic, not a dynamic terminal-voltage prediction or equilibrium-OCV error.
3. For every GITT rest, report duration, last raw voltage, median of the last
   60 s, and least-squares voltage slope over that window when at least three
   samples span at least 30 s. A flat slope is not a proof of equilibrium. Compare
   the late-rest median with the published discharge/charge reference branches
   at the segment's last nominal SOC, recording all assumptions.
4. For every contiguous discharge followed by rest, report last loaded voltage,
   first rest voltage, late-rest median, adjacent sample separation, and voltage
   recovery. Compute an apparent transition resistance only when abs(delta I)
   >=0.1 A and the adjacent samples are at most 1 s apart. This includes whatever
   dynamics fall within that sampling interval; it is not an identified R0.
   Compare it descriptively with table R0. Do not fit RC time constants.
5. Compare the loaded C/30 trace and long-rest GITT endpoints (rest duration
   >=600 s) with the saved 1C trace at the **same assumed nominal SOC**. For C/30
   interpolation, use only adjacent discharge samples with known decreasing SOC
   and no flagged gap. For GITT endpoints use only adjacent sequence endpoints
   with decreasing known SOC and no omitted intervening pulse/rest pair. Do not
   extrapolate, smooth, invert the voltage curve or align by endpoint capacity.
   Summarize the 1C endpoint comparison only when it is bracketed; otherwise
   report unsupported overlap. Cross-record differences are descriptive because
   cell identity and preparation equivalence are not established.
6. For pulse/rest pairs, report the unchanged table's R0 and R1+R2 at the loaded
   endpoint and compare `abs(I_end)*(R0+R1+R2)` with observed loaded-to-late-rest
   recovery. The expression is a steady-current diagnostic scale, not a full
   transient prediction or a measured resistance. Give pulse/rest durations and
   lookup tau1/tau2 so transient limitations remain visible.

Use the already declared SOC bins (<0, 0-0.2, 0.2-0.8, 0.8-1, >1). Report sample
and adjacent-interval time-weighted reference residual RMSE/bias/max, counts and
covered durations. Never label these as terminal prediction accuracy. Preserve
whole-sequence outputs even if only low-SOC points are highlighted on a plot.
Temperature channels are evidence only; no temperature law or thermal model.

## Decision and stopping rule

Separate confirmed patterns, tested explanations and unresolved causes. A
comparison at an assumed shared SOC cannot independently identify reference,
capacity, initial SOC, cell variability and rate dependence. Do not rescale any
record to make its endpoint capacity match another. Do not change model
complexity or choose a replacement model from this diagnostic stage.

Deliver a reproducible analysis command, meaningful synthetic integration checks,
source-referenced plots, machine-readable sample/segment/pair outputs, a compact
decision and preservation receipt. Keep the original model error visible.
Device voltage/excursion requirements remain unset; module validation and the
Q_sim_W meaning remain unresolved separately. Stop after the two-record diagnosis.
Any subsequent model revision or fresh assessment needs its own declared procedure.
