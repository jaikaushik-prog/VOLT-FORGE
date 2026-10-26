# Test-103 development import and physical feasibility

**Decision: the bounded importer is usable; a physical thermal model is not yet
identifiable from the established definitions. No C, H or heat-source model was
fitted.** This is USED DEVELOPMENT evidence for LG M50T cell 1 test 103. It is
neither independent assessment nor module validation. Four other cell-1 families
and all six cell-2 families remain unopened. Frozen electrical and thermal
prototype code, original measurements and previous receipts are unchanged.

The source is Marzook et al., [dataset 6421061](https://doi.org/10.5281/zenodo.6421061)
and [the accompanying paper](https://doi.org/10.1016/j.est.2022.105217), especially
sections 3.2–3.3 and Figure 3. Local paper/supplement hashes and download URLs are
preserved in the prior intake's `sources.json`. The prospective procedure,
format correction, analysis declaration and implementation snapshots precede
their corresponding full-record computations. `verification.json` pins this
handoff's source, output and implementation bytes.

## Confirmed import and measurement findings

The strict importer opens exactly the three allocated test-103 files. It preserves
all 16 raw thermal columns, both cold junctions, original calendar timestamp
strings, the unlabelled electrical field and the native MAT storage orientation.
Units are seconds/degC in the thermal text and V/mA in the electrical text. The
electrical header has 97 lines and labels `time/s`, but the actual first field is
a calendar timestamp; derived elapsed seconds are explicitly marked derived.
Its fourth numeric-position field is zero throughout, with no established name
or units. Two leading NUL bytes are removed for parsing; legacy CP1252 decoding
handles the temperature-unit row. Original bytes remain untouched.

| Recorded stream | Samples | Span | Timing limitations |
|---|---:|---:|---|
| Thermal | 258,987 | 258,986 s | 440 duplicate timestamps; no reversals; median interval 1 s, maximum 60 s |
| Electrical | 1,048,146 | 249,598.973 s | No duplicates/reversals; intervals 0.001–60.028 s; timezone unknown |

The thermal clock begins at zero. The electrical calendar starts on 20 October
2020 at 13:11:42.142. There is no documented shared start marker, offset or drift
correction. No alignment, interpolation, differentiation, time shift or duplicate
removal is applied. Similar-looking heating and pulse blocks do not establish a
common clock. Electrical plots show labelled one-minute extrema for readability;
analysis and local arrays retain every sample.

The initial header specifies CC/CV charge, then 5 A discharge terminating at
2500 mAh. The first measured positive-current segment rises to approximately
4.2 V; the following approximately −5 A segment integrates to −2.500010 Ah by
trapezoids. This supports **native charge-positive polarity**. Conversion to
the electrical backend's discharge-positive convention would be
`I_discharge_A = -I_native_mA / 1000`; raw arrays are not converted in place.
The configured 1 Ah instrument setting is not measured cell capacity. Neither
nominal 50% SOC nor achieved constant SOC is independently established.

The measured bipolar blocks corroborate the stored approximately eight-hour
program, rather than the paper's generic six-hour description. Each has 57,601
sign changes at approximately 0.5 s spacing, consistent with 1 Hz cycling.

| Block | Median absolute current (A) | Sampled active span (s) | Following sampled rest (s) | Rest coverage |
|---|---:|---:|---:|---|
| 1 | 3.74850 | 28,800.500 | 5,399.986 | Nominal 90 min lies within boundary bracket |
| 2 | 4.99857 | 28,800.499 | 5,399.989 | Nominal 90 min lies within boundary bracket |
| 3 | 6.24864 | 28,800.500 | 5,399.988 | Nominal 90 min lies within boundary bracket |
| 4 | 7.49851 | 28,800.501 | 5,399.991 | Nominal 90 min lies within boundary bracket |
| 5 | 8.74858 | 28,800.501 | 5,399.986 | Nominal 90 min lies within boundary bracket |
| 6 | 9.99845 | 28,800.501 | 3,599.963 | Recording ends; right-censored |

All six active blocks are bounded by recorded rest samples. Onset brackets are
0.002 s and termination brackets 0.038–0.040 s; maximum internal pulse gap is
0.251 s. The first five following rests have outer brackets of 5400.026–5400.031 s
and maximum internal gaps of 60–60.001 s. Thus there are six fully bounded active
blocks and five following rests consistent with the nominal 90-minute program;
continuous observation between samples is not claimed. The last rest is incomplete
relative to that program. The 0.005, 0.010 and 0.020 A diagnostic activity thresholds
all give eight long rest candidates including preparation rests. No record was
dropped to match the paper. These are electrical sequences; synchronized thermal
pulse/rest sequences have not been established.

Raw cap temperature reaches 58.77 degC and the raw cooled base reaches 41.34 degC.
The filename's nominal 20 degC cannot be used as constant cell temperature or as
an independently verified boundary measurement. The experiment is an insulated,
base-cooled fixture, not the proposed four-cell module.

## Tested representation and processing explanations

Five MAT cell labels and the `(5, 258986)` storage shape establish channel axis 0.
The raw README/Figure-3 mapping identifies thermal columns 4–8 as cell cap,
positive-side can, middle, negative-side can and base. For each channel, MAT
`celltemps` equals **raw rows 2 onward plus a constant** within 3.6e−15 degC
pointwise-difference spread. Omitting the last row instead gives 0.12–0.24 degC
spreads. Recovered offsets are 0.162645, 0.210700, 0.281111, 0.362264 and 0.253945
degC. These are observed author-processing transformations, with unknown origin
and uncertainty; no calibration is certified and no correction is applied.
An initial-temperature equalization or calibration correction is a hypothesis,
not an established rationale. This mapping says nothing about the electrical clock.

`SS_T` has 15 rows but only 14 decoded labels. The author label `Amb` occupies the
position corresponding to the first raw cold junction in the documented order;
the label alone does not establish an ambient sensor location. The final raw cold
junction lacks a corresponding author label. `SS_MaxT` and `SS_CST` exactly equal
the labelled cap and base rows respectively: **SS_CST is not treated as ambient**.
`SS_delT` equals their difference to roundoff. `Qnet = SS_Q + Qgain - Qloss`
holds exactly. `SS_CCC = SS_Q/SS_delT` does not hold exactly (maximum residual
0.000144263 in native CCC units); averaging ratios versus taking a ratio of means
is one possible explanation, with processing code needed to distinguish it.

The six `SS_Q/(finH−finC)` ratios equal 0.235659661 in native author heat units/K.
For the paper's rod geometry, Fourier conduction would be
`Qfin = k*A/L*(T6-T7)`, `A = pi*d^2/4`, with diameter 6 mm and TC separation 60 mm.
**If SS_Q is watts and these definitions apply**, the implied conductivity is
500.085 W/(m K). This is a conditional reverse inference about author processing,
not an independently established brass calibration or permission to adopt that
value. The conversion, dimensions actually used and heat units need confirmation.
The three fixed `AltQ/AltdelT` row ratios are also observable, but the declared
tab/tab/insulation temperature-difference order does not match `AltdelT` (maximum
residual 15.59 degC). No alternative row permutation or fitted constant was selected.
No author steady-state averaging windows were searched for or inferred.

Whole-record sampled native charge is 1.584986–1.595998 Ah and signed terminal
work is 70.4659–74.1725 Wh under right/left endpoint conventions (trapezoids:
1.590492 Ah and 72.3192 Wh). These include preparation and are **not heat or SOC
closure**. Per-pulse net charge is small but nonzero (roughly +0.0064 to +0.0127 Ah,
depending on block/convention). Sign-split accounting closes within 2e−13 in Ah
or Wh. Endpoint spread is a numerical sensitivity, not a calibrated error bound;
timing semantics and sensor uncertainty remain additional limitations.

## Why physical fitting remains blocked

A lumped balance `C*dT/dt = Qgen - H*(T-Tboundary)` cannot determine an absolute
heat/capacity/conductance scale when heat input and boundary state are unknown:
scaling C, H and Qgen together leaves its temperature trajectory unchanged.
Even a cooling decay can at best constrain an effective time scale under declared
zero-heat and boundary assumptions; it does not separately identify C and H.
This fixture additionally stores heat in its rod, plates, contacts and insulation,
and the cap-to-base gradients make an arbitrary single temperature an inadequate
unexamined state choice.

Fin heat rejection during a transient is not instantaneous internal electrochemical
heat generation. Terminal `V*I` is primarily electrical energy transfer, while
`I^2 R` or ECM dissipative loss excludes reversible/entropic heat and other paths.
CCC uses cap-to-base temperature difference and is not a node-to-ambient H.
Therefore the known qualitative heating/cooling and author CCC values do not yet
justify fitting a transferable module thermal model.

## Exact evidence needed next

No outreach was sent. Obtain author processing/calibration documentation or an
equivalent documented source addressing:

1. Test-103's mapping to physical setup, the reported electrical-noise fault and
   the supplement's 10/20 degC inconsistency. Six observed pulse blocks alone do
   not certify a fault-free setup.
2. Thermal/electrical acquisition start markers, timezone/clock relation and
   timestamp semantics, including duplicate thermal times and current-transition
   samples. Preserve raw clocks and any author synchronization code.
3. Raw-to-MAT temperature offsets, missing first row, all sensor locations,
   cold-junction compensation, calibration uncertainties and boundary/Peltier
   control measurements.
4. Units and formulas for SS_Q/Qnet/Qgain/Qloss/AltQ/AltdelT/CCC, rod dimensions and
   conductance calibration, TC orientation, exact steady-state windows, and
   uncertainty propagation. Supply processing scripts or one fully worked
   test-103 raw-window calculation.
5. For a physical transient fit: a justified independent heat scale and boundary
   history, and enough fixture/contact information to separate cell storage from
   fixture storage. If this archive cannot provide them, a different documented
   public transient/calorimetric dataset or a controlled measurement is needed.

Once definitions are resolved, declare a bounded test-103-only processing replay
and an identifiability procedure before any fit. Keep reserves closed until that
procedure and the allowed calibration are frozen. Additional computation on the
same unexplained channels cannot replace the missing physical information.

## Checks and reproducibility

`tests_002.xml`: 24 synthetic checks passed. They cover exact channel/order/unit
parsing, HDF5 references/orientation, forbidden-member rejection before access,
timestamp preservation, analytical signed charge/work, sampled boundaries,
censored rests, fixed algebra, complete import/replay and tamper detection.
The first test run is retained: one synthetic fixture put a nominal 60 s span
just below the diagnostic boundary through binary rounding; exact representable
fixture endpoints fixed that test without changing real-data classification.
Import attempt 001 and its failure remain recorded; attempt 002 corrected the
calendar/four-field electrical layout; attempts 003–004 added declared diagnostics
and replay. No failed receipt was overwritten.

Final real-data replay reproduces the complete diagnostic report and every array
exactly and verifies nine output hashes. The three displayed plots were inspected
for readable axes, units and DEVELOPMENT/source labels. See `REPRODUCE.md` for
commands, output meaning and the local-array boundary. These checks establish
software/data-handling consistency, not thermal prediction accuracy.

For a student: we can now read the experiment faithfully and show what was actually
measured. We cannot yet turn its heating curve into a trustworthy module temperature
prediction because the clocks, heat conversion and fixture calibration are not
defined well enough. The next engineering action is to recover that documentation
or use a better-documented public experiment, while keeping the unseen tests sealed.
