# Deterministic development diagnostics after format discovery

Declared before calculating the comparisons/blocks below. Full-record import 002
established the dimensions, labels and raw ranges; no physical model was fitted.
The following diagnostics complete the original prospective import procedure.

- Thermal header names/order must match all 16 observed raw channels exactly.
  MAT celltemplabels identify the five cell temperatures. Their first storage
  axis has five entries and the second has one fewer entry than the raw rows.
  Report BOTH possible one-row omissions (first or last raw row), without
  searching larger shifts. For each, report pointwise-difference spread and
  median offset. Do not modify either series or infer inter-instrument alignment.
- Classify electrical activity with |I|>0.01 A; zero-current/rest candidates
  require at least 60 seconds of sampled span. Also report the number of long
  rests using 0.005 and 0.020 A thresholds. These are declared diagnostic
  tolerances, not instrument specifications or model calibration.
- Report every contiguous active/rest region; preserve small regions separately.
  A bipolar active region with at least 100 sign changes is a pulse-block
  candidate. Report exact first/last sample times, outer bracketing sample
  times, maximum internal gap, positive/negative sample counts and sign-change
  intervals. No electrical sequence is discarded to match the paper.
- Integrate native current and V*I using left, right and trapezoid endpoint
  conventions, retaining their spread. Split signed charge/terminal work into
  positive and negative contributions. This is sampled electrical accounting,
  not total internal heat or electrochemical state closure.
- Test fixed, label-defined author-field relationships: SS_MaxT versus cap
  temperature, SS_CST versus cooled-base temperature, SS_delT versus cap minus
  base, SS_CCC versus SS_Q/SS_delT, and Qnet versus SS_Q+Qgain-Qloss.
  Test fin hot-minus-cold temperature against SS_Q by reporting per-column
  implied ratios, not by fitting a coefficient or changing a scale.
- Compare each row of AltdelT against the documented positive-tab,
  negative-tab and insulation temperature differences in that declared order.
  Report mismatch rather than permuting rows to improve agreement. Ratios
  AltQ/AltdelT remain author-processing inferences, not calibrated conductances.
- A rod conductivity implied by SS_Q/(T6-T7) and paper geometry d=0.006 m,
  sensor separation L=0.060 m is explicitly labelled an inferred processing
  constant. It does not prove calibration or transient heat-generation accuracy.
- Retain all thermal duplicate times and gaps. Do not differentiate or resample
  thermal series, optimize clocks, search averaging windows, fit C/H/Q or use
  any unopened experiment. All plots carry USED DEVELOPMENT labels.
